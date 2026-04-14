"""
Voice Routes - Real-time WebSocket streaming for Twilio voice calls
Handles Twilio <-> Deepgram <-> AI <-> ElevenLabs pipeline with barge-in support.
"""

import asyncio
import base64
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ai_service import ai_service
from app.services.db_service import db_service
from app.services.deepgram_service import create_deepgram_service
from app.services.elevenlabs_service import create_elevenlabs_service

router = APIRouter(prefix="/ws", tags=["Voice"])


class VoiceCallSession:
    """
    Manages a single voice call session with concurrent audio streams.
    Handles the full pipeline: Twilio -> Deepgram -> AI -> ElevenLabs -> Twilio
    """
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.stream_sid: Optional[str] = None
        self.call_sid: Optional[str] = None
        self.conversation_id: str = ""
        
        # Services
        self.deepgram = create_deepgram_service()
        self.elevenlabs = create_elevenlabs_service()
        
        # Conversation state
        self.conversation_history: list[dict] = []
        self.current_transcript = ""
        
        # Barge-in control
        self.is_bot_speaking = False
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self._stop_playback = False
        
    async def start(self):
        """Initialize the session and connect to services."""
        # Connect to Deepgram with callbacks
        await self.deepgram.connect(
            on_transcript=self._on_transcript,
            on_speech_final=self._on_speech_final
        )
        
        # Start the audio sender task
        asyncio.create_task(self._audio_sender())
        
        print(f"[VOICE] Voice session started")
    
    async def handle_twilio_message(self, message: dict):
        """
        Process incoming Twilio WebSocket messages.
        
        Message types:
        - connected: WebSocket connection established
        - start: Media stream started (contains streamSid)
        - media: Audio payload (base64 encoded mulaw)
        - stop: Stream ended
        """
        event_type = message.get("event")
        
        if event_type == "connected":
            print("[CALL] Twilio: WebSocket connected")
            
        elif event_type == "start":
            self.stream_sid = message.get("start", {}).get("streamSid")
            self.call_sid = message.get("start", {}).get("callSid")
            print(f"[CALL] Twilio: Stream started - {self.stream_sid}")

            self.conversation_id = db_service.create_conversation(
                channel="voice",
                external_id=self.call_sid or "",
                metadata={"stream_sid": self.stream_sid},
            )
            
            # Send greeting
            await self._send_ai_response(
                "Assalam o Alaikum! Sabeel Homeo Clinic mein aapka swagat hai. "
                "Main aapki kaise madad kar sakti hoon?"
            )
            
        elif event_type == "media":
            # Check for barge-in
            if self.is_bot_speaking:
                # Human is speaking while bot is talking - barge-in!
                await self._handle_barge_in()
            
            # Forward audio to Deepgram
            payload = message.get("media", {}).get("payload", "")
            if payload:
                audio_bytes = base64.b64decode(payload)
                await self.deepgram.send_audio(audio_bytes)
                
        elif event_type == "stop":
            print("[CALL] Twilio: Stream stopped")
            await self.cleanup()
    
    async def _on_transcript(self, transcript: str, is_final: bool):
        """Callback for interim transcripts from Deepgram."""
        self.current_transcript = transcript
    
    async def _on_speech_final(self, transcript: str):
        """
        Callback when Deepgram detects end of sentence.
        Triggers AI response generation.
        """
        if not transcript.strip():
            return
        
        print(f"👤 User: {transcript}")
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": transcript
        })
        db_service.add_message(self.conversation_id, "user", transcript)
        
        # Generate AI response
        response = await ai_service.generate_response_async(
            self.conversation_history,
            is_voice=True,
            channel="voice",
            user_contact=self.call_sid or "",
            conversation_id=self.conversation_id,
        )
        
        print(f"🤖 AI: {response}")
        
        # Add to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        db_service.add_message(self.conversation_id, "assistant", response)
        
        # Send response audio
        await self._send_ai_response(response)
    
    async def _send_ai_response(self, text: str):
        """
        Stream AI response as audio to Twilio.
        Uses ElevenLabs WebSocket for real-time TTS.
        """
        self.is_bot_speaking = True
        self._stop_playback = False
        
        try:
            async for audio_chunk in self.elevenlabs.stream_text_to_speech(
                text,
                output_format="ulaw_8000"
            ):
                if self._stop_playback:
                    break
                    
                # Queue audio for sending
                await self.audio_queue.put(audio_chunk)
            
            # Signal end of response
            await self.audio_queue.put(None)
            
        except Exception as e:
            print(f"❌ TTS streaming error: {e}")
        finally:
            self.is_bot_speaking = False
    
    async def _audio_sender(self):
        """
        Async task that sends queued audio chunks to Twilio.
        Runs continuously until session ends.
        """
        while True:
            try:
                audio_chunk = await self.audio_queue.get()
                
                if audio_chunk is None:
                    continue
                
                if self._stop_playback:
                    # Clear the queue on barge-in
                    while not self.audio_queue.empty():
                        try:
                            self.audio_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    continue
                
                # Send to Twilio
                await self._send_audio_to_twilio(audio_chunk)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Audio sender error: {e}")
    
    async def _send_audio_to_twilio(self, audio_bytes: bytes):
        """Send audio payload to Twilio WebSocket."""
        if not self.stream_sid:
            return
        
        try:
            payload = base64.b64encode(audio_bytes).decode("utf-8")
            
            message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": payload
                }
            }
            
            await self.websocket.send_json(message)
            
        except Exception as e:
            print(f"❌ Twilio send error: {e}")
    
    async def _handle_barge_in(self):
        """
        Handle barge-in (user interrupting the bot).
        Stop TTS and clear audio buffer.
        """
        if self._stop_playback:
            return  # Already handling barge-in
        
        print("🔇 Barge-in detected! Stopping playback...")
        
        self._stop_playback = True
        self.is_bot_speaking = False
        
        # Stop ElevenLabs streaming
        self.elevenlabs.stop_streaming()
        
        # Send clear message to Twilio
        if self.stream_sid:
            try:
                await self.websocket.send_json({
                    "event": "clear",
                    "streamSid": self.stream_sid
                })
            except Exception as e:
                print(f"❌ Clear message error: {e}")
    
    async def cleanup(self):
        """Clean up resources when call ends."""
        await self.deepgram.close()
        print("🎙️ Voice session ended")


@router.websocket("/media-stream")
async def media_stream_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio media streams.
    Handles real-time voice call audio.
    
    Twilio connects here when a call is received.
    Configure your Twilio webhook to point to: wss://your-server/ws/media-stream
    """
    await websocket.accept()
    print("🔗 WebSocket connection accepted")
    
    session = VoiceCallSession(websocket)
    
    try:
        await session.start()
        
        while True:
            # Receive message from Twilio
            data = await websocket.receive_text()
            message = json.loads(data)
            
            await session.handle_twilio_message(message)
            
    except WebSocketDisconnect:
        print("🔗 WebSocket disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
    finally:
        await session.cleanup()
