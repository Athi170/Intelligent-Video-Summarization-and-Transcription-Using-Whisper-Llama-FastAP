import subprocess


def extract_audio(video_path, audio_path):

    command = [
        "ffmpeg",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        audio_path,
        "-y"
    ]

    subprocess.run(command, check=True)


def pick_windows(audio, sample_rate=16000, window_seconds=30, max_windows=6, min_rms=0.003):
    """
    Return start indexes of the loudest (most likely speech) 30s windows.
    Language detection on silence, music or intros is what makes Whisper
    guess English, so we only look at windows that actually contain sound.
    """
    import numpy as np

    size = window_seconds * sample_rate
    if len(audio) <= size:
        return [0]

    starts = list(range(0, len(audio) - size + 1, size))
    rms = [float(np.sqrt(np.mean(np.square(audio[s:s + size])))) for s in starts]
    ranked = sorted(zip(rms, starts), reverse=True)
    chosen = [s for r, s in ranked if r >= min_rms][:max_windows]

    return sorted(chosen) or [starts[0]]
