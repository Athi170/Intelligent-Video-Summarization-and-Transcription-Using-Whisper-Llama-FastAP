"""
Diagnose language detection on a video/audio file:
    python -m app.check_language path/to/video.mp4
Prints what Whisper hears in each window and the language it would pick.
"""
import sys
import logging
import tempfile
import os

logging.basicConfig(level=logging.INFO, format="%(message)s")

from .utils import extract_audio
from . import whisper_service as ws

if len(sys.argv) < 2:
    sys.exit("Usage: python -m app.check_language <video-or-audio-file>")

wav = os.path.join(tempfile.gettempdir(), "lang_check.wav")
extract_audio(sys.argv[1], wav)
lang, conf = ws.detect_language(wav)
print(f"\nModel: {ws.WHISPER_MODEL} | Allowed: {ws.ALLOWED_LANGUAGES or 'all'}")
print(f"Detected language: {lang} (confidence {conf:.2f})")
os.remove(wav)
