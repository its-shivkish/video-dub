import asyncio
import os
import uuid
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, HttpUrl

from config import config
from transcribe import process_video_transcription
from translate import translate_transcription, SUPPORTED_LANGUAGES
from tts import TTSService, VOICE_PRESETS
from video_processing import VideoProcessor, dubbing_pipeline


# Validate configuration at startup
config.validate()

app = FastAPI(title="Video Dubbing Studio", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class VideoRequest(BaseModel):
    url: HttpUrl

class TranslateRequest(BaseModel):
    url: HttpUrl
    target_language: str

class DubRequest(BaseModel):
    url: HttpUrl
    target_language: str
    voice_option: str = "clone"  # "clone" or voice_id
    voice_style: str = "natural"  # natural, dramatic, calm, energetic

class TranscriptionResponse(BaseModel):
    success: bool
    transcription: Optional[str] = None
    error: Optional[str] = None
    video_title: Optional[str] = None
    duration: Optional[float] = None

class TranslationResponse(BaseModel):
    success: bool
    original_transcription: Optional[str] = None
    translated_text: Optional[str] = None
    target_language: Optional[str] = None
    error: Optional[str] = None
    video_title: Optional[str] = None
    duration: Optional[float] = None

class DubbingResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None
    video_url: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None

class VoiceOptionsResponse(BaseModel):
    voices: dict

class LanguagesResponse(BaseModel):
    languages: dict

class HealthResponse(BaseModel):
    status: str
    message: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", message="Video transcription service is running")

@app.get("/languages", response_model=LanguagesResponse)
async def get_supported_languages():
    """Get list of supported languages for translation"""
    return LanguagesResponse(languages=SUPPORTED_LANGUAGES)

@app.get("/voices", response_model=VoiceOptionsResponse)
async def get_voice_options():
    """Get available voice options for dubbing"""
    try:
        tts_service = TTSService()
        voices = await tts_service.get_voice_options()
        return VoiceOptionsResponse(voices=voices)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch voice options: {str(e)}")

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_video(video_request: VideoRequest):
    """
    Download a YouTube video and transcribe it using Deepgram
    """
    try:
        result = await process_video_transcription(str(video_request.url))
        return TranscriptionResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from transcription module
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.post("/translate", response_model=TranslationResponse)
async def translate_video(translate_request: TranslateRequest):
    """
    Download a YouTube video, transcribe it, and translate to target language
    """
    try:
        # First transcribe the video
        transcription_result = await process_video_transcription(str(translate_request.url))
        
        if not transcription_result["success"]:
            return TranslationResponse(
                success=False,
                error="Transcription failed"
            )
        
        original_text = transcription_result["transcription"]
        
        # Then translate the transcription
        translated_text = await translate_transcription(
            original_text, 
            translate_request.target_language
        )
        
        return TranslationResponse(
            success=True,
            original_transcription=original_text,
            translated_text=translated_text,
            target_language=translate_request.target_language,
            video_title=transcription_result.get("video_title"),
            duration=transcription_result.get("duration")
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

@app.post("/dub", response_model=DubbingResponse)
async def dub_video(dub_request: DubRequest):
    """
    Create a fully dubbed video with voice synthesis
    """
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        await dubbing_pipeline.create_session(session_id)
        
        # Start dubbing process in background
        asyncio.create_task(process_dubbing(session_id, dub_request))
        
        return DubbingResponse(
            success=True,
            session_id=session_id,
            status="processing",
            progress=0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dubbing initiation failed: {str(e)}")

@app.get("/dub/status/{session_id}", response_model=DubbingResponse)
async def get_dubbing_status(session_id: str):
    """Get status of dubbing process"""
    session = dubbing_pipeline.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    response = DubbingResponse(
        success=True,
        session_id=session_id,
        status=session["status"],
        progress=session["progress"]
    )
    
    if session["status"] == "completed":
        response.video_url = f"/video/{session_id}"
        response.download_url = f"/download/{session_id}"
    elif session["status"] == "failed":
        response.error = session.get("error", "Unknown error occurred")
    
    return response

@app.get("/video/{session_id}")
async def stream_video(session_id: str):
    """Stream dubbed video for viewing"""
    session = dubbing_pipeline.get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=404, detail="Video not found or not ready")
    
    video_path = session.get("dubbed_video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        headers={"Content-Disposition": "inline"}
    )

@app.get("/download/{session_id}")
async def download_video(session_id: str):
    """Download dubbed video file"""
    session = dubbing_pipeline.get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=404, detail="Video not found or not ready")
    
    dubbed_video_path = session.get("dubbed_video_path")
    if not dubbed_video_path or not os.path.exists(dubbed_video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(
        dubbed_video_path,
        media_type="video/mp4",
        filename=f"dubbed_video_{session_id}.mp4"
    )


async def process_dubbing(session_id: str, dub_request: DubRequest):
    """Background task to process video dubbing"""
    session = dubbing_pipeline.get_session(session_id)
    
    try:
        session["status"] = "transcribing"
        session["progress"] = 10
        print(f"[DUBBING {session_id}] Starting transcription...")
        print(f"[DUBBING {session_id}] Temp files will be stored in: {config.get_temp_dir(session_id)}")
        
        # Step 1: Transcribe video
        transcription_result = await process_video_transcription(str(dub_request.url), session_id)
        if not transcription_result["success"]:
            session["status"] = "failed"
            session["error"] = "Transcription failed"
            print(f"[DUBBING {session_id}] Transcription failed")
            return
        
        session["progress"] = 30
        session["status"] = "translating"
        print(f"[DUBBING {session_id}] Starting translation...")
        
        # Step 2: Translate text
        translated_text = await translate_transcription(
            transcription_result["transcription"],
            dub_request.target_language
        )
        print(f"[DUBBING {session_id}] Translation completed. Text length: {len(translated_text)}")
        
        session["progress"] = 50
        session["status"] = "generating_voice"
        print(f"[DUBBING {session_id}] Starting voice generation...")
        
        # Step 3: Generate dubbed audio
        tts_service = TTSService()
        video_processor = VideoProcessor(session_id)
        
        # Extract audio for voice cloning (if needed)
        original_audio_path = transcription_result.get("audio_path")
        print(f"[DUBBING {session_id}] Original audio path: {original_audio_path}")
        
        # Get voice settings
        voice_settings = VOICE_PRESETS.get(dub_request.voice_style, VOICE_PRESETS["natural"])
        print(f"[DUBBING {session_id}] Voice option: {dub_request.voice_option}, Style: {dub_request.voice_style}")
        
        try:
            dubbed_audio_path = await tts_service.create_dubbed_audio(
                transcription_result["transcription_data"],
                translated_text,
                original_audio_path,
                dub_request.voice_option,
                voice_settings,
                session_id
            )
            print(f"[DUBBING {session_id}] Voice generation completed: {dubbed_audio_path}")
        except Exception as tts_error:
            print(f"[DUBBING {session_id}] TTS ERROR: {str(tts_error)}")
            raise tts_error
        
        session["progress"] = 80
        session["status"] = "combining_video"
        print(f"[DUBBING {session_id}] Starting video combination...")
        
        # Step 4: Combine with original video
        original_video_path = transcription_result.get("video_path")
        print(f"[DUBBING {session_id}] Original video path: {original_video_path}")
        
        try:
            dubbed_video_path = await video_processor.combine_video_with_dubbed_audio(
                original_video_path,
                dubbed_audio_path,
                transcription_result["transcription_data"]
            )
            print(f"[DUBBING {session_id}] Video combination completed: {dubbed_video_path}")
        except Exception as video_error:
            print(f"[DUBBING {session_id}] VIDEO COMBINATION ERROR: {str(video_error)}")
            raise video_error
        
        session["dubbed_video_path"] = dubbed_video_path
        session["progress"] = 100
        session["status"] = "completed"
        print(f"[DUBBING {session_id}] Dubbing completed successfully!")
        
    except Exception as e:
        error_msg = str(e)
        print(f"[DUBBING {session_id}] PIPELINE ERROR: {error_msg}")
        session["status"] = "failed"
        session["error"] = error_msg


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT) 
