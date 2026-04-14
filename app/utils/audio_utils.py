"""
Audio utilities used by voice and messaging channels.
The common runtime path avoids importing pydub eagerly so Python 3.13 can boot
without the legacy audioop module unless conversion helpers are explicitly used.
"""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import httpx


def _guess_extension(content_type: str, url: str = "") -> str:
    lowered = content_type.lower()
    if "audio/mpeg" in lowered or url.lower().endswith(".mp3"):
        return ".mp3"
    if "audio/wav" in lowered or url.lower().endswith(".wav"):
        return ".wav"
    if "audio/ogg" in lowered or "opus" in lowered or url.lower().endswith(".ogg") or url.lower().endswith(".oga"):
        return ".ogg"
    if "audio/webm" in lowered or url.lower().endswith(".webm"):
        return ".webm"
    return ".bin"


def _load_audio_segment():
    try:
        from pydub import AudioSegment  # type: ignore

        return AudioSegment
    except Exception as exc:
        print(f"[WARNING] Audio conversion helpers unavailable: {exc}")
        return None


async def download_audio(
    url: str,
    output_path: Optional[str] = None,
    *,
    auth: tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Optional[str]:
    """
    Download audio file from URL (Async).
    """
    try:
        async with httpx.AsyncClient(auth=auth, headers=headers) as client:
            response = await client.get(url, timeout=30)
            response.raise_for_status()

        if output_path is None:
            suffix = _guess_extension(response.headers.get("content-type", ""), url)
            fd, output_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)

        with open(output_path, "wb") as file_handle:
            file_handle.write(response.content)

        return output_path
    except Exception as exc:
        print(f"[ERROR] Failed to download audio: {exc}")
        return None


def save_audio_bytes(audio_bytes: bytes, output_path: str) -> bool:
    """Save raw audio bytes to a file."""
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as file_handle:
            file_handle.write(audio_bytes)
        return True
    except Exception as exc:
        print(f"[ERROR] Failed to save audio: {exc}")
        return False


def save_temp_audio_bytes(audio_bytes: bytes, suffix: str = ".ogg") -> Optional[str]:
    """Save audio bytes to a temporary file and return the path."""
    try:
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        if not save_audio_bytes(audio_bytes, temp_path):
            return None
        return temp_path
    except Exception as exc:
        print(f"[ERROR] Failed to save temp audio: {exc}")
        return None


def decode_base64_audio(encoded_audio: str, suffix: str = ".ogg") -> Optional[str]:
    """Decode a base64 payload to a temporary audio file."""
    try:
        payload = encoded_audio.split(",", 1)[-1].strip()
        return save_temp_audio_bytes(base64.b64decode(payload), suffix=suffix)
    except Exception as exc:
        print(f"[ERROR] Failed to decode base64 audio: {exc}")
        return None


def convert_ogg_to_wav(ogg_path: str, wav_path: Optional[str] = None) -> Optional[str]:
    """Convert OGG file to WAV format."""
    AudioSegment = _load_audio_segment()
    if AudioSegment is None:
        return None

    try:
        if wav_path is None:
            wav_path = str(Path(ogg_path).with_suffix(".wav"))

        audio = AudioSegment.from_ogg(ogg_path)
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as exc:
        print(f"[ERROR] OGG to WAV conversion failed: {exc}")
        return None


def convert_to_mp3(input_path: str, mp3_path: Optional[str] = None) -> Optional[str]:
    """Convert audio file to MP3 format."""
    AudioSegment = _load_audio_segment()
    if AudioSegment is None:
        return None

    try:
        if mp3_path is None:
            mp3_path = str(Path(input_path).with_suffix(".mp3"))

        input_format = Path(input_path).suffix.lstrip(".").lower()
        if input_format == "ogg":
            audio = AudioSegment.from_ogg(input_path)
        elif input_format == "wav":
            audio = AudioSegment.from_wav(input_path)
        elif input_format == "mp3":
            audio = AudioSegment.from_mp3(input_path)
        else:
            audio = AudioSegment.from_file(input_path)

        audio.export(mp3_path, format="mp3", bitrate="128k")
        return mp3_path
    except Exception as exc:
        print(f"[ERROR] MP3 conversion failed: {exc}")
        return None


def get_audio_duration(file_path: str) -> Optional[float]:
    """Get duration of an audio file in seconds."""
    AudioSegment = _load_audio_segment()
    if AudioSegment is None:
        return None

    try:
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception as exc:
        print(f"[ERROR] Failed to get audio duration: {exc}")
        return None


def cleanup_temp_file(file_path: str) -> bool:
    """Safely delete a temporary file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as exc:
        print(f"[ERROR] Failed to cleanup file: {exc}")
        return False


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg"))
