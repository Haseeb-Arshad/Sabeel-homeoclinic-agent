import requests
import json
import time

def simulate_evolution_webhook():
    url = "http://localhost:8000/webhook/evolution"
    
    payload = {
        "event": "messages.upsert",
        "instance": "sabeel_homeo",
        "data": {
            "key": {
                "remoteJid": "923001234567@s.whatsapp.net",
                "fromMe": False,
                "id": "SIMULATED_ID"
            },
            "message": {
                "conversation": "Doctor saab, mujhe thoda bukhaar hai. Kya appointment mil sakti hai?"
            },
            "pushName": "Simulated User"
        }
    }
    
    print(f"🚀 Sending simulated webhook to {url}...")
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"📡 Response Status: {response.status_code}")
        print(f"📡 Response Body: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Webhook accepted. AI processing will happen in the background.")
            print("📝 Check application logs for AI response and send_text calls.")
        else:
            print("❌ Webhook rejected.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    simulate_evolution_webhook()
