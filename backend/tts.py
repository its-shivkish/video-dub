import os
import tempfile
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

import httpx
from fastapi import HTTPException

from config import config


class ElevenLabsTTS:
    """ElevenLabs Text-to-Speech implementation"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = config.ELEVENLABS_BASE_URL
        
    async def get_available_voices(self) -> List[Dict[str, Any]]:
        """Get list of available pre-built voices"""
        try:
            headers = {"xi-api-key": self.api_key}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/voices",
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("voices", [])
                else:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Failed to fetch voices: {response.text}"
                    )
                    
        except httpx.TimeoutError:
            raise HTTPException(status_code=504, detail="Voice fetch request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Voice fetch failed: {str(e)}")
    
    async def clone_voice_from_audio(self, audio_file_path: str, voice_name: str = "cloned_voice") -> str:
        """
        Clone voice from original audio file
        
        Args:
            audio_file_path: Path to original audio file
            voice_name: Name for the cloned voice
            
        Returns:
            Voice ID of cloned voice
        """
        try:
            headers = {"xi-api-key": self.api_key}
            
            # Read the audio file data first
            with open(audio_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            files = {
                "files": ("audio.wav", audio_data, "audio/wav")
            }
            data = {
                "name": voice_name,
                "description": "Voice cloned from original video"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/voices/add",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("voice_id")
                else:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Voice cloning failed: {response.text}"
                    )
                        
        except httpx.TimeoutError:
            print(f"Voice cloning timeout for file: {audio_file_path}")
            raise HTTPException(status_code=504, detail="Voice cloning request timed out")
        except Exception as e:
            print(f"Voice cloning error: {type(e).__name__}: {str(e)}")
            print(f"Audio file path: {audio_file_path}")
            print(f"Audio file exists: {os.path.exists(audio_file_path)}")
            if os.path.exists(audio_file_path):
                print(f"Audio file size: {os.path.getsize(audio_file_path)} bytes")
            raise HTTPException(status_code=500, detail=f"Voice cloning failed: {str(e)}")
    
    async def synthesize_speech(
        self, 
        text: str, 
        voice_id: str,
        voice_settings: Optional[Dict[str, float]] = None
    ) -> bytes:
        """
        Convert text to speech using specified voice
        
        Args:
            text: Text to convert to speech
            voice_id: ElevenLabs voice ID
            voice_settings: Voice configuration (stability, similarity_boost, speed, etc.)
            
        Returns:
            Audio data as bytes
        """
        try:
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            # Default voice settings
            default_settings = {
                "stability": 0.5,
                "similarity_boost": 0.8,
                "style": 0.0,
                "use_speaker_boost": True
            }
            
            if voice_settings:
                default_settings.update(voice_settings)
            
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": default_settings
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/text-to-speech/{voice_id}",
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    return response.content
                else:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Speech synthesis failed: {response.text}"
                    )
                    
        except httpx.TimeoutError:
            raise HTTPException(status_code=504, detail="Speech synthesis request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {str(e)}")


class TTSService:
    """High-level TTS service with timing synchronization"""
    
    def __init__(self):
        api_key = config.ELEVENLABS_API_KEY
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="ELEVENLABS_API_KEY not found in environment variables"
            )
        self.elevenlabs = ElevenLabsTTS(api_key)
    
    async def get_voice_options(self) -> Dict[str, Any]:
        """Get available voice options for the frontend"""
        try:
            voices = await self.elevenlabs.get_available_voices()
            
            # Filter for good quality voices and organize by category
            organized_voices = {
                "clone": {
                    "id": "clone",
                    "name": "Voice Cloning (Match Original Speaker)",
                    "description": "AI will clone the original speaker's voice",
                    "default": True
                },
                "prebuilt": []
            }
            
            # Add some popular pre-built voices
            for voice in voices:
                if voice.get("category") in ["professional", "conversational"] or len(organized_voices["prebuilt"]) < 10:
                    organized_voices["prebuilt"].append({
                        "id": voice.get("voice_id"),
                        "name": voice.get("name"),
                        "description": voice.get("description", ""),
                        "accent": voice.get("labels", {}).get("accent", ""),
                        "gender": voice.get("labels", {}).get("gender", ""),
                        "age": voice.get("labels", {}).get("age", "")
                    })
            
            return organized_voices
            
        except Exception as e:
            # Return minimal options if API fails
            return {
                "clone": {
                    "id": "clone",
                    "name": "Voice Cloning (Match Original Speaker)",
                    "description": "AI will clone the original speaker's voice",
                    "default": True
                },
                "prebuilt": [
                    {
                        "id": "pNInz6obpgDQGcFmaJgB", # Adam (default voice)
                        "name": "Adam",
                        "description": "American, middle-aged male",
                        "accent": "American",
                        "gender": "Male",
                        "age": "Middle Aged"
                    }
                ]
            }
    
    async def create_dubbed_audio(
        self,
        transcription_data: Dict[str, Any],
        translated_text: str,
        original_audio_path: str,
        voice_option: str = "clone",
        voice_settings: Optional[Dict[str, float]] = None,
        session_id: str = None
    ) -> str:
        """
        Create dubbed audio with proper timing synchronization
        
        Args:
            transcription_data: Timing data from Deepgram
            translated_text: Translated text
            original_audio_path: Path to original audio for voice cloning
            voice_option: Voice ID or "clone" for voice cloning
            voice_settings: Custom voice settings
            
        Returns:
            Path to generated dubbed audio file
        """
        try:
            # Determine voice ID
            if voice_option == "clone":
                # Clone voice from original audio
                voice_id = await self.elevenlabs.clone_voice_from_audio(
                    original_audio_path,
                    "temp_cloned_voice"
                )
            else:
                # Use pre-built voice
                voice_id = voice_option
            
            # Generate speech
            audio_data = await self.elevenlabs.synthesize_speech(
                translated_text,
                voice_id,
                voice_settings
            )
            
            # Save to temporary file
            if session_id:
                temp_dir = config.get_temp_dir(session_id)
                os.makedirs(temp_dir, exist_ok=True)
                print(f"[TTS {session_id}] Using temp dir: {temp_dir}")
            else:
                temp_dir = tempfile.mkdtemp()
                print(f"[TTS] Using temp dir: {temp_dir}")
                
            dubbed_audio_path = os.path.join(temp_dir, "dubbed_audio.mp3")
            
            with open(dubbed_audio_path, 'wb') as f:
                f.write(audio_data)
            
            return dubbed_audio_path
            
        except Exception as e:
            print(f"TTS Error in create_dubbed_audio: {type(e).__name__}: {str(e)}")
            print(f"Voice option: {voice_option}")
            print(f"Audio path exists: {os.path.exists(original_audio_path) if original_audio_path else 'None'}")
            print(f"Translated text length: {len(translated_text)}")
            raise HTTPException(status_code=500, detail=f"Audio dubbing failed: {str(e)}")


# Voice settings presets
VOICE_PRESETS = {
    "natural": {
        "stability": 0.5,
        "similarity_boost": 0.8,
        "style": 0.0,
        "use_speaker_boost": True
    },
    "dramatic": {
        "stability": 0.3,
        "similarity_boost": 0.9,
        "style": 0.2,
        "use_speaker_boost": True
    },
    "calm": {
        "stability": 0.8,
        "similarity_boost": 0.6,
        "style": 0.0,
        "use_speaker_boost": False
    },
    "energetic": {
        "stability": 0.2,
        "similarity_boost": 0.9,
        "style": 0.3,
        "use_speaker_boost": True
    }
} 
