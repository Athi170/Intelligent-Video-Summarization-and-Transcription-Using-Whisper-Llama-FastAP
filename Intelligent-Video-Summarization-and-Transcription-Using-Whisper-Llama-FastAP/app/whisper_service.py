import os
import logging
import whisper
import torch
from dotenv import load_dotenv

from .utils import pick_windows

load_dotenv()
logger = logging.getLogger(__name__)

device = "cuda" if torch.cuda.is_available() else "cpu"

# large-v3 is the most accurate for Indian languages. Use medium/small on weak hardware.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3")

# Languages the detector may choose from. Restricting this stops confusions such as
# Tamil vs Malayalam or Hindi vs Urdu. Set WHISPER_LANGUAGES= (empty) to allow all.
_default = "en,hi,ta,te,es,fr,de,zh,ja,ar"
ALLOWED_LANGUAGES = [c.strip() for c in os.getenv("WHISPER_LANGUAGES", _default).split(",") if c.strip()]

# A short native-script prompt nudges Whisper to write in the right script.
PROMPTS = {
    "hi": "यह हिंदी में बातचीत है।",
    "ta": "இது தமிழில் நடக்கும் உரையாடல்.",
    "te": "ఇది తెలుగులో జరిగే సంభాషణ.",
    "ar": "هذه محادثة باللغة العربية.",
    "zh": "这是一段普通话对话。",
    "ja": "これは日本語の会話です。",
}

model = whisper.load_model(WHISPER_MODEL, device=device)
logger.info(f"Whisper model loaded: {WHISPER_MODEL} on {device}")

SAMPLE_RATE = 16000
WINDOW = 30 * SAMPLE_RATE


def detect_language(audio_path, max_windows=6):
    """
    Listen to the loudest 30s windows across the whole file, restrict to the
    allowed languages, and average the probabilities. Returns (code, confidence).
    """
    audio = whisper.load_audio(audio_path)
    totals, used = {}, 0

    for start in pick_windows(audio, SAMPLE_RATE, 30, max_windows):
        chunk = whisper.pad_or_trim(audio[start:start + WINDOW])
        mel = whisper.log_mel_spectrogram(chunk, n_mels=model.dims.n_mels).to(model.device)
        _, probs = model.detect_language(mel)

        if ALLOWED_LANGUAGES:
            probs = {k: v for k, v in probs.items() if k in ALLOWED_LANGUAGES}
        norm = sum(probs.values()) or 1.0

        top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:3]
        logger.info(f"Language window @{start // SAMPLE_RATE}s: " + ", ".join(f"{k}={v / norm:.2f}" for k, v in top))

        for k, v in probs.items():
            totals[k] = totals.get(k, 0.0) + v / norm
        used += 1

    if not totals:
        return None, 0.0

    best = max(totals, key=totals.get)
    return best, totals[best] / used


def transcribe_audio(audio_path, language=None):
    """
    language: ISO-639-1 code or None to auto-detect.
    Returns (text, language_code_used).
    """
    if not language:
        language, confidence = detect_language(audio_path)
        logger.info(f"Auto-detected language: {language} (confidence {confidence:.2f})")
    else:
        logger.info(f"Using language chosen by the user: {language}")

    result = model.transcribe(
        audio_path,
        fp16=device == "cuda",
        language=language,
        task="transcribe",
        condition_on_previous_text=False,
        initial_prompt=PROMPTS.get(language),
        no_speech_threshold=0.6,
    )

    return result["text"].strip(), result.get("language", language)
