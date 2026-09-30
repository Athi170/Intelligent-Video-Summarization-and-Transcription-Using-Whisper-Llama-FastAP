from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import uuid
import logging

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
MAX_FILE_SIZE = 100 * 1024 * 1024
SESSION_COOKIE_NAME = "session_token"
# Set AUTH_COOKIE_SECURE=true in .env once the app is served over HTTPS.
COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"

from .utils import extract_audio
from .whisper_service import transcribe_audio
from .ollama_service import generate_summary
from .redis_service import (
    save_result,
    get_result,
    set_status,
    get_status,
    check_redis,
    save_history,
    get_history,
    get_all_video_ids,
    delete_video,
    delete_all_history_records
)
from .auth_service import (
    create_user,
    authenticate_user,
    create_session,
    get_session_user,
    delete_session,
    username_exists,
    SESSION_TTL_SECONDS
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


app = FastAPI(
    title="AI Video Summarization API"
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


class AuthRequest(BaseModel):
    username: str
    password: str


def get_current_user(request: Request) -> str:
    """Dependency that guards an endpoint. Raises 401 if not logged in."""

    token = request.cookies.get(SESSION_COOKIE_NAME)
    username = get_session_user(token)

    if not username:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )

    return username

# Background video processing
def process_video(video_id, video_path, audio_path, language=None):

    try:

        # Step 1: Extract audio
        try:

            set_status(video_id, "extracting_audio")
            extract_audio(video_path, audio_path)
            logger.info("Audio extraction completed")

        except Exception as e:
            raise Exception(
                f"Audio extraction failed: {str(e)}"
            )

        # Step 2: Transcribe audio
        try:

            set_status(video_id, "transcribing")
            transcript, detected_lang = transcribe_audio(audio_path, language=language)
            logger.info(f"Language used: {detected_lang}")
            save_result(f"video:{video_id}:language", detected_lang or "")
            logger.info("Whisper transcription completed")

        except Exception as e:
            raise Exception(
                f"Whisper transcription failed: {str(e)}"
            )

        # Step 3: Generate summary
        try:

            set_status(video_id, "summarizing")
            summary = generate_summary(transcript, detected_lang)
            logger.info("Ollama summary generated")

        except Exception as e:
            raise Exception(
                f"Ollama summarization failed: {str(e)}"
            )

        # Step 4: Save results to Redis
        try:

            save_result(
                f"video:{video_id}:transcript",
                transcript
            )

            save_result(
                f"video:{video_id}:summary",
                summary
            )

            set_status(video_id, "completed")
            save_history(video_id, "completed")

            logger.info(
                f"Video processing completed: {video_id}"
            )

        except Exception as e:
            raise Exception(
                f"Redis storage failed: {str(e)}"
            )

    except Exception as e:

        set_status(video_id, "failed")
        save_history(video_id, "failed")

        logger.error(
            f"Video processing failed: {video_id} - {str(e)}"
        )

    finally:

        if os.path.exists(audio_path):
            os.remove(audio_path)

@app.get("/")
def home():
    return FileResponse("frontend/index.html")

@app.get("/login")
def login_page():
    return FileResponse("frontend/login.html")

@app.get("/register")
def register_page():
    return FileResponse("frontend/register.html")


# ---------- Auth ----------

@app.post("/auth/register")
def register(payload: AuthRequest, response: Response):

    username = payload.username.strip()

    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username must be at least 3 characters."
        )

    if len(payload.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters."
        )

    if not create_user(username, payload.password):
        raise HTTPException(
            status_code=400,
            detail="That username is already taken."
        )

    token = create_session(username)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=SESSION_TTL_SECONDS,
        path="/"
    )

    logger.info(f"New user registered: {username}")

    return {
        "message": "Account created successfully",
        "username": username
    }

@app.post("/auth/login")
def login(payload: AuthRequest, response: Response):

    username = payload.username.strip()

    if not authenticate_user(username, payload.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password."
        )

    token = create_session(username)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=SESSION_TTL_SECONDS,
        path="/"
    )

    logger.info(f"User logged in: {username}")

    return {
        "message": "Login successful",
        "username": username
    }

@app.post("/auth/logout")
def logout(request: Request, response: Response):

    token = request.cookies.get(SESSION_COOKIE_NAME)
    delete_session(token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")

    return {
        "message": "Logged out"
    }

@app.get("/auth/me")
def me(request: Request):

    token = request.cookies.get(SESSION_COOKIE_NAME)
    username = get_session_user(token)

    if not username:
        return JSONResponse(
            status_code=401,
            content={"authenticated": False}
        )

    return {
        "authenticated": True,
        "username": username
    }


@app.post("/summarize")
async def summarize_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form(None),
    current_user: str = Depends(get_current_user)
):

    # Check file extension
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {list(ALLOWED_EXTENSIONS)}"
        )

    # Treat "auto" or an empty value as "let Whisper detect the language"
    if not language or language == "auto":
        language = None

    # Create unique video ID
    video_id = str(uuid.uuid4())

    # Create file paths
    video_path = f"uploads/{video_id}_{file.filename}"
    audio_path = f"temp/{video_id}.wav"

    # Set initial status
    set_status(video_id, "processing")
    save_history(video_id, "processing")

    # Save uploaded video
    try:
        file_size = 0

        with open(video_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)

                if file_size > MAX_FILE_SIZE:
                    raise ValueError(
                        "Video file is too large. Maximum size is 100 MB."
                    )

                buffer.write(chunk)

        logger.info(
            f"Video uploaded successfully: {video_id}"
        )

    except ValueError as e:
        set_status(video_id, "failed")

        if os.path.exists(video_path):
            os.remove(video_path)

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        set_status(video_id, "failed")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save video: {str(e)}"
        )

    # Add video processing to background
    background_tasks.add_task(
        process_video,
        video_id,
        video_path,
        audio_path,
        language
    )

    # Return immediately
    return {
        "video_id": video_id,
        "status": "processing"
    }

@app.get("/summary/{video_id}")
def get_summary(video_id: str, current_user: str = Depends(get_current_user)):

    summary = get_result(f"video:{video_id}:summary")

    if summary is None:
        return {
            "message": "Summary not found"
        }

    return {
        "video_id": video_id,
        "summary": summary
    }

@app.get("/transcript/{video_id}")
def get_transcript(video_id: str, current_user: str = Depends(get_current_user)):

    transcript = get_result(f"video:{video_id}:transcript")

    if transcript is None:
        return {
            "message": "Transcript not found"
        }

    return {
        "video_id": video_id,
        "transcript": transcript,
        "language": get_result(f"video:{video_id}:language")
    }

@app.get("/status/{video_id}")
def get_video_status(video_id: str, current_user: str = Depends(get_current_user)):

    status = get_status(video_id)

    if status is None:
        return {
            "message": "Video status not found"
        }

    return {
        "video_id": video_id,
        "status": status
    }

@app.get("/history/{video_id}")
def get_video_history(video_id: str, current_user: str = Depends(get_current_user)):

    history = get_history(video_id)

    if not history:
        return {
            "message": "Video history not found"
        }

    return history

@app.delete("/history/{video_id}")
def delete_video_history(video_id: str, current_user: str = Depends(get_current_user)):

    history = get_history(video_id)

    if not history:
        raise HTTPException(
            status_code=404,
            detail="Video history not found"
        )

    delete_video(video_id)

    return {
        "message": "Video history deleted successfully",
        "video_id": video_id
    }

@app.get("/history")
def get_all_history(current_user: str = Depends(get_current_user)):

    video_ids = get_all_video_ids()

    history = []

    for video_id in video_ids:

        item = get_history(video_id)

        if item:
            history.append(item)

    return {
        "history": history
    }

@app.delete("/history")
def delete_all_history(current_user: str = Depends(get_current_user)):

    deleted_count = delete_all_history_records()

    return {
        "message": "All video history deleted successfully",
        "deleted_count": deleted_count
    }

@app.get("/video/{video_id}")
def get_video_file(video_id: str, current_user: str = Depends(get_current_user)):

    for filename in os.listdir("uploads"):

        if filename.startswith(video_id + "_"):

            video_path = os.path.join(
                "uploads",
                filename
            )

            return FileResponse(
                video_path
            )

    raise HTTPException(
        status_code=404,
        detail="Video file not found"
    )

@app.get("/health")
def health_check():

    try:
        redis_status = check_redis()

        return {
            "status": "healthy",
            "api": "running",
            "redis": "connected" if redis_status else "disconnected"
        }

    except Exception as e:

        return {
            "status": "unhealthy",
            "api": "running",
            "redis": "disconnected",
            "error": str(e)
        }