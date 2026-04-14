import importlib.util
import os
import subprocess
import sys

import requests
from dotenv import load_dotenv

from app.utils.audio_utils import ffmpeg_available

load_dotenv(override=True)


def print_status(message, success=True):
    mark = "[OK]" if success else "[FAIL]"
    print(f"{mark} {message}")


def check_env_var(key, *, required=True):
    val = os.getenv(key, "").strip()
    if val:
        print_status(f"Found {key}")
        return True
    if required:
        print_status(f"Missing {key}", success=False)
        return False
    print_status(f"Optional {key} not set")
    return True


def check_openai():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print_status("Skipping OpenAI API check (OPENAI_API_KEY not set)")
        return True

    print("\nChecking OpenAI API...")
    try:
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if response.status_code == 200:
            print_status("OpenAI API is accessible")
            return True
        print_status(f"OpenAI API failed: {response.status_code}", success=False)
        return False
    except Exception as exc:
        print_status(f"OpenAI connection error: {exc}", success=False)
        return False


def check_elevenlabs():
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        print_status("Skipping ElevenLabs API check (ELEVENLABS_API_KEY not set)")
        return True

    print("\nChecking ElevenLabs API...")
    try:
        response = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key},
            timeout=10,
        )
        if response.status_code == 200:
            print_status("ElevenLabs API is accessible")
            return True
        print_status(f"ElevenLabs API failed: {response.status_code}", success=False)
        return False
    except Exception as exc:
        print_status(f"ElevenLabs connection error: {exc}", success=False)
        return False


def check_ffmpeg():
    print("\nChecking FFmpeg...")
    if ffmpeg_available():
        try:
            result = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                print_status(f"FFmpeg found: {result.stdout.splitlines()[0]}")
                return True
        except Exception:
            pass
    print_status("FFmpeg not found in PATH or not executable", success=False)
    return False


def check_optional_package(package_name):
    found = importlib.util.find_spec(package_name) is not None
    print_status(f"Package {package_name} {'found' if found else 'missing'}", success=found)
    return found


def main():
    print("Starting pre-deployment sanity check...\n")

    print("Checking environment variables...")
    required_vars = [
        "OPENAI_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "ELEVENLABS_API_KEY",
        "DEEPGRAM_API_KEY",
    ]
    all_env_passed = all(check_env_var(var_name) for var_name in required_vars)

    print("\nChecking optional configuration...")
    check_env_var("SUPABASE_URL", required=False)
    check_env_var("SUPABASE_SERVICE_ROLE_KEY", required=False)
    check_env_var("WHATSAPP_API_URL", required=False)
    check_env_var("WHATSAPP_API_KEY", required=False)
    check_env_var("META_PAGE_ACCESS_TOKEN", required=False)

    openai_passed = check_openai()
    elevenlabs_passed = check_elevenlabs()
    ffmpeg_passed = check_ffmpeg()

    print("\nChecking runtime packages...")
    multipart_ok = check_optional_package("multipart")
    aiohttp_ok = check_optional_package("aiohttp")

    print("\n" + "=" * 60)
    all_passed = all([all_env_passed, openai_passed, elevenlabs_passed, ffmpeg_passed, multipart_ok, aiohttp_ok])
    if all_passed:
        print("SYSTEM READY FOR DEPLOYMENT")
        sys.exit(0)

    print("SYSTEM CHECKS FAILED - FIX ISSUES ABOVE")
    sys.exit(1)


if __name__ == "__main__":
    main()
