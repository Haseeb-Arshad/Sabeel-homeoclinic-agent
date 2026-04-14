import deepgram
import inspect

print("Dir of deepgram:")
print(dir(deepgram))

try:
    from deepgram import LiveTranscriptionEvents
    print("LiveTranscriptionEvents found!")
except ImportError:
    print("LiveTranscriptionEvents NOT found in deepgram module")

# Check if it's in a submodule
try:
    import deepgram.clients
    print("deepgram.clients found")
except ImportError:
    print("deepgram.clients NOT found")
