from ollama import chat
import os
from dotenv import load_dotenv


# Load variables from .env
load_dotenv()


# Get Ollama model from .env
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu",
    "es": "Spanish", "fr": "French", "de": "German", "zh": "Chinese",
    "ja": "Japanese", "ar": "Arabic",
}


def generate_summary(text, language="en"):

    lang_name = LANGUAGE_NAMES.get(language, language or "English")

    prompt = f"""
    Summarize the following video transcript.
    The transcript is in {lang_name}. Write the summary in {lang_name}.

    Give the output in this format:

    1. Short Summary
    2. Key Points
    3. Important Information

    Transcript:
    {text}
    """

    response = chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]