import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

try:
    print("Testing deepgram_service import...")
    from app.services import deepgram_service
    print("✅ SUCCESS: deepgram_service imported")
except ImportError as e:
    print(f"❌ IMPORT ERROR: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ UNEXPECTED ERROR: {e}")
    sys.exit(1)
