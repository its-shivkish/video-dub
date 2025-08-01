"""
Text-to-Speech Module

Provides ElevenLabs TTS integration for voice cloning and speech synthesis.
Handles voice generation, cloning, and audio processing for video dubbing.
"""

import os
import tempfile
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

import httpx
from fastapi import HTTPException

from config import config


# Constants
REQUEST_TIMEOUT = 60.0
VOICE_FETCH_TIMEOUT = 30.0
DEFAULT_VOICE_NAME = "temp_cloned_voice"
AUDIO_FORMAT = "mp3"


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
                    timeout=VOICE_FETCH_TIMEOUT
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("voices", [])
                else:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Failed to fetch voices: {response.text}"
                    )
                    
        # This is already handled by the generic Exception handler above
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
            print(f"[TTS] Starting voice cloning from {audio_file_path}")
            headers = {"xi-api-key": self.api_key}
            
            # Read and validate audio file
            if not os.path.exists(audio_file_path):
                raise HTTPException(status_code=400, detail=f"Audio file not found: {audio_file_path}")
            
            file_size = os.path.getsize(audio_file_path)
            print(f"[TTS] Audio file size: {file_size} bytes")
            
            if file_size < 1024:  # Less than 1KB
                raise HTTPException(status_code=400, detail="Audio file too small for voice cloning")
            
            # Read the audio file data
            with open(audio_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            files = {
                "files": ("audio.wav", audio_data, "audio/wav")
            }
            data = {
                "name": voice_name,
                "description": "Voice cloned from original video"
            }
            
            print("[TTS] Sending voice cloning request to ElevenLabs...")
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/voices/add",
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=REQUEST_TIMEOUT
                    )
                    
                    print(f"[TTS] Voice cloning response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        voice_id = result.get("voice_id")
                        if not voice_id:
                            raise HTTPException(
                                status_code=500,
                                detail="Voice cloning succeeded but no voice_id in response"
                            )
                        print(f"[TTS] Voice cloning successful. Voice ID: {voice_id}")
                        return voice_id
                    else:
                        # Try to get detailed error message
                        error_detail = "Unknown error"
                        try:
                            error_json = response.json()
                            error_detail = error_json.get("detail", error_json)
                        except:
                            error_detail = response.text or "No error details available"
                        
                        print(f"[TTS] Voice cloning failed with status {response.status_code}")
                        print(f"[TTS] Error details: {error_detail}")
                        
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Voice cloning failed: {error_detail}"
                        )
                except httpx.ReadTimeout:
                    print("[TTS] Voice cloning request timed out")
                    raise HTTPException(status_code=504, detail="Voice cloning request timed out")
                except httpx.ConnectTimeout:
                    print("[TTS] Could not connect to ElevenLabs API")
                    raise HTTPException(status_code=504, detail="Could not connect to voice service")
                except Exception as e:
                    print(f"[TTS] Request error: {type(e).__name__}: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Voice cloning request failed: {str(e)}")
                        
        except HTTPException as he:
            # Re-raise HTTP exceptions with their original status and detail
            raise he
        except Exception as e:
            print(f"[TTS] Unexpected error during voice cloning: {type(e).__name__}: {str(e)}")
            print(f"[TTS] Audio file path: {audio_file_path}")
            print(f"[TTS] Audio file exists: {os.path.exists(audio_file_path)}")
            if os.path.exists(audio_file_path):
                print(f"[TTS] Audio file size: {os.path.getsize(audio_file_path)} bytes")
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
                    timeout=REQUEST_TIMEOUT
                )
                
                if response.status_code == 200:
                    return response.content
                else:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Speech synthesis failed: {response.text}"
                    )
                    
        except Exception as e:
            # Handle timeout and connection errors
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                raise HTTPException(status_code=504, detail="Speech synthesis request timed out")
            else:
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

    async def create_synchronized_dubbed_audio(
        self,
        transcription_data: Dict[str, Any],
        translated_text: str,
        original_audio_path: str,
        voice_option: str = "clone",
        voice_settings: Optional[Dict[str, float]] = None,
        session_id: str = None,
        target_language: str = "en"
    ) -> str:
        """
        Create dubbed audio with utterance-level synchronization to preserve timing and pauses
        
        Args:
            transcription_data: Timing data from Deepgram with utterances
            translated_text: Full translated text
            original_audio_path: Path to original audio for voice cloning
            voice_option: Voice ID or "clone" for voice cloning
            voice_settings: Custom voice settings
            session_id: Session ID for temp directory
            
        Returns:
            Path to generated synchronized dubbed audio file
        """
        try:
            print(f"[TTS {session_id}] Starting synchronized dubbing...")
            
            # Determine voice ID
            try:
                if voice_option == "clone":
                    print(f"[TTS {session_id}] Attempting to clone voice from {original_audio_path}")
                    voice_id = await self.elevenlabs.clone_voice_from_audio(
                        original_audio_path,
                        DEFAULT_VOICE_NAME
                    )
                    print(f"[TTS {session_id}] Voice cloning successful, got voice ID: {voice_id}")
                    
                    # Use stronger similarity settings for cloned voice
                    voice_settings = {
                        "stability": 0.3,  # Lower stability for more expressive speech
                        "similarity_boost": 0.95,  # Higher similarity to match original voice
                        "style": 0.0,  # Neutral style
                        "use_speaker_boost": True
                    }
                else:
                    print(f"[TTS {session_id}] Using pre-built voice: {voice_option}")
                    voice_id = voice_option
                    # Use default voice settings from VOICE_PRESETS
                    voice_settings = VOICE_PRESETS.get("natural", {})
            except Exception as e:
                print(f"[TTS {session_id}] Voice cloning failed: {str(e)}")
                print(f"[TTS {session_id}] Falling back to default voice")
                
                # Select fallback voice based on target language
                if target_language == "hi":  # Hindi
                    voice_id = "pNInz6obpgDQGcFmaJgB"  # Adam - better for Indian languages
                    print(f"[TTS {session_id}] Using Hindi-friendly fallback voice: {voice_id}")
                elif target_language in ["es", "pt"]:  # Spanish/Portuguese  
                    voice_id = "TxGEqnHWrfWFTfGW9XjX"  # Josh - good for Spanish
                    print(f"[TTS {session_id}] Using Spanish/Portuguese fallback voice: {voice_id}")
                else:
                    voice_id = "21m00Tcm4TlvDq8ikWAM"  # Default English voice
                    print(f"[TTS {session_id}] Using default English fallback voice: {voice_id}")
                
                voice_settings = VOICE_PRESETS.get("natural", {})
                print(f"[TTS {session_id}] Using natural voice settings for fallback")
            
            # Get utterances with timing
            utterances = transcription_data.get("utterances", [])
            if not utterances:
                print(f"[TTS {session_id}] No utterances found, trying paragraphs as fallback...")
                
                # Try using paragraphs as utterances
                paragraphs = transcription_data.get("paragraphs", [])
                if paragraphs:
                    print(f"[TTS {session_id}] Found {len(paragraphs)} paragraphs, using as utterances")
                    utterances = []
                    for para in paragraphs:
                        if isinstance(para, dict) and para.get("text"):
                            utterances.append({
                                "start": para.get("start", 0),
                                "end": para.get("end", 0),
                                "transcript": para.get("text", "")
                            })
                
                # If still no utterances, create synthetic ones from the full text
                if not utterances:
                    print(f"[TTS {session_id}] No paragraphs found, creating synthetic utterances from sentences")
                    import re
                    sentences = re.split(r'[.!?]+', transcription_data.get("text", ""))
                    sentences = [s.strip() for s in sentences if s.strip()]
                    
                    if sentences:
                        # Create fake timing (distribute evenly across estimated duration)
                        total_words = len(transcription_data.get("words", []))
                        estimated_duration = total_words * 0.5 if total_words else 30  # 0.5 seconds per word estimate
                        time_per_sentence = estimated_duration / len(sentences)
                        
                        for i, sentence in enumerate(sentences):
                            start_time = i * time_per_sentence
                            end_time = (i + 1) * time_per_sentence
                            utterances.append({
                                "start": start_time,
                                "end": end_time,
                                "transcript": sentence
                            })
                        
                        print(f"[TTS {session_id}] Created {len(utterances)} synthetic utterances")
                
                # Final fallback to full text
                if not utterances:
                    print(f"[TTS {session_id}] No utterances possible, falling back to full text")
                    return await self.create_dubbed_audio(
                        transcription_data, translated_text, original_audio_path, 
                        voice_option, voice_settings, session_id
                    )
            
            print(f"[TTS {session_id}] Processing {len(utterances)} utterances...")
            
            # Import translation function
            from translate import translate_transcription
            
            # Generate TTS for each utterance (translate individually for better accuracy)
            utterance_audio_files = []
            temp_dir = config.get_temp_dir(session_id) if session_id else tempfile.mkdtemp()
            
            for i, utterance in enumerate(utterances):
                start_time = utterance.get("start", 0)
                end_time = utterance.get("end", 0)
                original_text = utterance.get("transcript", "")
                
                # Translate each utterance individually for better accuracy
                try:
                    print(f"[TTS {session_id}] Translating utterance {i+1}: '{original_text[:50]}...'")
                    utterance_translated = await translate_transcription(original_text, target_language)
                    print(f"[TTS {session_id}] Translation result: '{utterance_translated[:50]}...'")
                except Exception as translate_error:
                    print(f"[TTS {session_id}] Translation failed for utterance {i+1}: {str(translate_error)}")
                    utterance_translated = original_text  # Fallback to original
                
                print(f"[TTS {session_id}] Utterance {i+1}: {start_time:.2f}s-{end_time:.2f}s")
                print(f"[TTS {session_id}] Original: '{original_text[:50]}...'")
                print(f"[TTS {session_id}] Translated: '{utterance_translated[:50]}...'")
                
                # Generate TTS for this utterance
                if utterance_translated.strip():
                    audio_data = await self.elevenlabs.synthesize_speech(
                        utterance_translated,
                        voice_id,
                        voice_settings
                    )
                    
                    # Save utterance audio
                    utterance_file = os.path.join(temp_dir, f"utterance_{i}.{AUDIO_FORMAT}")
                    with open(utterance_file, 'wb') as f:
                        f.write(audio_data)
                    
                    utterance_audio_files.append({
                        'file': utterance_file,
                        'start': start_time,
                        'end': end_time,
                        'duration': end_time - start_time
                    })
            
            # Combine utterances with proper timing using FFmpeg
            final_audio_path = await self._combine_utterances_with_timing(
                utterance_audio_files, temp_dir, session_id
            )
            
            print(f"[TTS {session_id}] Synchronized dubbing completed: {final_audio_path}")
            return final_audio_path
            
        except Exception as e:
            print(f"TTS Error in create_synchronized_dubbed_audio: {type(e).__name__}: {str(e)}")
            print(f"Voice option: {voice_option}")
            print(f"Audio path exists: {os.path.exists(original_audio_path) if original_audio_path else 'None'}")
            print(f"Utterances count: {len(transcription_data.get('utterances', []))}")
            raise HTTPException(status_code=500, detail=f"Synchronized audio dubbing failed: {str(e)}")

    async def _combine_utterances_with_timing(
        self, 
        utterance_files: List[Dict], 
        temp_dir: str,
        session_id: str = None
    ) -> str:
        """
        Combine utterance audio files with proper timing and silence gaps
        """
        import ffmpeg
        
        print(f"[TTS {session_id}] Combining {len(utterance_files)} utterances with timing...")
        
        if not utterance_files:
            raise ValueError("No utterance files to combine")
        
        # Sort utterances by start time
        utterance_files.sort(key=lambda x: x['start'])
        
        # Create a list of audio segments with proper timing
        audio_segments = []
        current_time = 0
        
        for i, utterance in enumerate(utterance_files):
            start_time = utterance['start']
            end_time = utterance['end']
            file_path = utterance['file']
            
            # Add silence if there's a gap before this utterance
            if start_time > current_time and start_time - current_time > 0.1:  # Gap > 100ms
                gap_duration = start_time - current_time
                silence_duration = max(0.1, gap_duration)  # At least 100ms silence
                
                silence_file = os.path.join(temp_dir, f"gap_{i}.{AUDIO_FORMAT}")
                try:
                    (
                        ffmpeg
                        .input('anullsrc=channel_layout=mono:sample_rate=44100', f='lavfi', t=silence_duration)
                        .output(silence_file, acodec="libmp3lame", ar="44100")
                        .overwrite_output()
                        .run(quiet=True)
                    )
                    audio_segments.append(silence_file)
                    print(f"[TTS {session_id}] Added {silence_duration:.2f}s silence gap before utterance {i+1}")
                except Exception as e:
                    print(f"[TTS {session_id}] Warning: Could not create silence gap: {str(e)}")
            
            # Add the utterance audio
            audio_segments.append(file_path)
            current_time = end_time
            
            print(f"[TTS {session_id}] Added utterance {i+1}: {start_time:.2f}s-{end_time:.2f}s")
            print(f"[TTS {session_id}] Audio file: {file_path}")
            
            # Verify this is a TTS-generated file, not original audio
            if 'utterance_' in os.path.basename(file_path):
                print(f"[TTS {session_id}] ✓ Confirmed TTS-generated utterance file")
            else:
                print(f"[TTS {session_id}] ⚠️  WARNING: This doesn't look like a TTS file: {file_path}")
        
        print(f"[TTS {session_id}] Total audio segments to concatenate: {len(audio_segments)}")
        for idx, segment in enumerate(audio_segments):
            print(f"[TTS {session_id}]   {idx+1}. {os.path.basename(segment)} ({'silence' if 'gap_' in segment else 'utterance'})")
        
        # Create the final output file
        final_output = os.path.join(temp_dir, f"synchronized_dubbed_audio.{AUDIO_FORMAT}")
        
        if len(audio_segments) == 1:
            # If only one segment, just copy it
            import shutil
            shutil.copy2(audio_segments[0], final_output)
            print(f"[TTS {session_id}] Single audio segment copied: {final_output}")
        else:
            # Concatenate all segments
            try:
                # Create input streams for each audio segment
                input_streams = [ffmpeg.input(segment) for segment in audio_segments]
                
                # Concatenate all streams
                (
                    ffmpeg
                    .concat(*input_streams, v=0, a=1)
                    .output(final_output, acodec="libmp3lame", ar="44100")
                    .overwrite_output()
                    .run(quiet=True)
                )
                print(f"[TTS {session_id}] Successfully concatenated {len(audio_segments)} audio segments")
                
            except ffmpeg.Error as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                print(f"[TTS {session_id}] FFmpeg concatenation error: {error_msg}")
                raise ValueError(f"Failed to concatenate audio segments: {error_msg}")
            except Exception as e:
                print(f"[TTS {session_id}] Error during concatenation: {str(e)}")
                raise ValueError(f"Failed to concatenate audio segments: {str(e)}")
        
        # Verify the output file was created
        if not os.path.exists(final_output):
            raise ValueError(f"Output file was not created: {final_output}")
        
        # Check the duration of the final dubbed audio vs expected duration
        try:
            import subprocess
            result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', final_output],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                actual_duration = float(result.stdout.strip())
                expected_duration = utterance_files[-1]['end'] if utterance_files else 0
                print(f"[TTS {session_id}] Dubbed audio duration: {actual_duration:.2f}s (expected: {expected_duration:.2f}s)")
                
                if actual_duration > expected_duration * 1.5:  # More than 50% longer than expected
                    print(f"[TTS {session_id}] WARNING: Dubbed audio is significantly longer than expected!")
                    print(f"[TTS {session_id}] This might indicate the audio contains extra content")
        except Exception as probe_error:
            print(f"[TTS {session_id}] Could not probe audio duration: {str(probe_error)}")
        
        print(f"[TTS {session_id}] Audio combination successful: {final_output}")
        return final_output


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
