import logging
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from fastapi.testclient import TestClient
from main import app
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Override settings for testing
settings.META_VERIFY_TOKEN = "test_token_123"
settings.META_PAGE_ACCESS_TOKEN = "test_page_token"

client = TestClient(app)

def test_webhook_verification():
    """Test the GET /webhook/meta endpoint for verification."""
    logger.info("Testing Webhook Verification...")
    
    # Simulate Meta's verification request
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "test_token_123",
        "hub.challenge": "123456789"
    }
    
    try:
        response = client.get("/webhook/meta", params=params)
        
        if response.status_code == 200 and response.text == "123456789":
            logger.info("✅ Verification SUCCESS: Server returned correct challenge.")
        else:
            logger.error(f"❌ Verification FAILED: Status {response.status_code}, Body: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Connection Error: {e}")

def test_failure_verification():
    """Test verification failure with wrong token."""
    logger.info("\nTesting Webhook Verification Failure...")
    
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "WRONG_TOKEN",
        "hub.challenge": "123456789"
    }
    
    response = client.get("/webhook/meta", params=params)
    if response.status_code == 403:
        logger.info("✅ Failure Test SUCCESS: Server rejected wrong token.")
    else:
        logger.error(f"❌ Failure Test FAILED: Status {response.status_code}")

def test_incoming_message():
    """Test the POST /webhook/meta endpoint with a mock message."""
    logger.info("\nTesting Incoming Message...")
    
    # Simulate a page messaging event
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "12345",
                "time": 123456789,
                "messaging": [
                    {
                        "sender": {"id": "user_123"},
                        "recipient": {"id": "page_123"},
                        "timestamp": 123456789,
                        "message": {
                            "mid": "mid.12345",
                            "text": "Hello, clear skin please!"
                        }
                    }
                ]
            }
        ]
    }
    
    # We mock the AIService to avoid real OpenAI calls/errors and graph API calls
    # but for now, let's just let it run. The reply will fail (log error) but endpoint should return 200.
    
    try:
        response = client.post("/webhook/meta", json=payload)
        
        if response.status_code == 200:
            logger.info("✅ Webhook POST SUCCESS: Server accepted the event.")
        else:
            logger.error(f"❌ Webhook POST FAILED: Status {response.status_code}, Body: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    test_webhook_verification()
    test_failure_verification()
    test_incoming_message()
