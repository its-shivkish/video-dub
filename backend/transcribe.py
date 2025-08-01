import os
import tempfile
import shutil
import ffmpeg
from pathlib import Path
from typing import Dict, Any, Optional

import yt_dlp
from deepgram import Deepgram
from fastapi import HTTPException

from config import config


def get_deepgram_client() -> Deepgram:
    """Initialize and return Deepgram client"""
    api_key = config.DEEPGRAM_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="DEEPGRAM_API_KEY not found in environment variables"
        )
    return Deepgram(api_key)


def download_video_audio(video_url: str, temp_dir: str) -> tuple[str, Dict[str, Any]]:
    """
    Download video from YouTube and extract audio
    
    Args:
        video_url: YouTube video URL
        temp_dir: Temporary directory path for downloads
    
    Returns:
        Tuple of (audio_file_path, video_info)
    
    Raises:
        HTTPException: If download fails
    """
    # Configure yt-dlp options with better error handling
    ydl_opts = {
        'format': 'best', 
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': False,
        # Add headers to avoid detection
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        # Retry options
        'retries': 3,
        'fragment_retries': 3,
        # Use cookies if available
        'cookiesfrombrowser': None,
        # Additional options to handle signature extraction issues
        'extractor_args': {
            'youtube': {
                'player_client': ['web'],
                'player_skip': ['configs'],
            }
        },
    }
    
    try:
        # Download video and extract audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            # Find the downloaded file (should be video now)
            video_path = None
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')):
                    video_path = os.path.join(temp_dir, file)
                    break
        
        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=500, detail="Failed to download video")
        
        # For now, use video file as audio source (we'll extract audio during TTS)
        return video_path, info
    
    except yt_dlp.DownloadError as e:
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            raise HTTPException(
                status_code=400, 
                detail="This video is restricted and cannot be downloaded. Please try a different video."
            )
        elif "404" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(
                status_code=404, 
                detail="Video not found. Please check the URL and try again."
            )
        elif "signature extraction failed" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="YouTube signature extraction failed - this video has enhanced protection. Try this working video instead: https://www.youtube.com/watch?v=jNQXAC9IVRw"
            )
        else:
            raise HTTPException(status_code=500, detail=f"YouTube download error: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        if "signature extraction failed" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="YouTube signature extraction failed - this video has enhanced protection. Try this working video instead: https://www.youtube.com/watch?v=jNQXAC9IVRw"
            )
        else:
            raise HTTPException(status_code=500, detail=f"Video download failed: {error_msg}")


async def transcribe_audio_file(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe audio file using Deepgram
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        Dictionary containing transcribed text and timing information
    
    Raises:
        HTTPException: If transcription fails
    """
    try:
        deepgram = get_deepgram_client()
        
        # Determine mimetype based on file extension
        file_ext = Path(audio_path).suffix.lower()
        mimetype_map = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4',
            '.webm': 'audio/webm',
            '.opus': 'audio/opus',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac'
        }
        mimetype = mimetype_map.get(file_ext, 'audio/wav')
        
        with open(audio_path, 'rb') as audio_file:
            buffer_data = audio_file.read()
        
        payload = {
            "buffer": buffer_data,
            "mimetype": mimetype
        }
        
        options = {
            "model": "nova-2",
            "smart_format": True,
            "utterances": True,
            "punctuate": True,
            "diarize": True,
            "words": True,  # Enable word-level timestamps
            "paragraphs": True,  # Enable paragraph-level timestamps
        }
        
        response = await deepgram.transcription.prerecorded(payload, options)
        
        # Extract transcription text and timestamps
        transcription_data = {
            "text": "",
            "words": [],
            "utterances": [],
            "paragraphs": []
        }
        
        if response and "results" in response:
            channels = response["results"].get("channels", [])
            if channels and len(channels) > 0:
                channel = channels[0]
                alternatives = channel.get("alternatives", [])
                if alternatives and len(alternatives) > 0:
                    alternative = alternatives[0]
                    
                    # Get full transcript
                    transcript = alternative.get("transcript", "")
                    if transcript:
                        transcription_data["text"] = transcript
                    
                    # Get word-level timestamps
                    words = alternative.get("words", [])
                    transcription_data["words"] = words
                
                # Get utterance-level timestamps
                utterances = channel.get("utterances", [])
                transcription_data["utterances"] = utterances
                
                # Get paragraph-level timestamps
                paragraphs = channel.get("paragraphs", [])
                transcription_data["paragraphs"] = paragraphs
        
        if not transcription_data["text"].strip():
            raise HTTPException(status_code=500, detail="No transcription was generated")
        
        return transcription_data
    
    except Exception as e:
        if "DEEPGRAM_API_KEY" in str(e):
            raise HTTPException(status_code=500, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


async def process_video_transcription(video_url: str, session_id: str = None) -> Dict[str, Any]:
    """
    Complete video transcription pipeline: download, extract audio, and transcribe
    
    Args:
        video_url: YouTube video URL
        session_id: Optional session ID for creating predictable temp directories
    
    Returns:
        Dictionary containing transcription results
    
    Raises:
        HTTPException: If any step of the process fails
    """
    temp_dir = None
    try:
        # Create predictable temporary directory
        if session_id:
            temp_dir = config.get_temp_dir(session_id)
            os.makedirs(temp_dir, exist_ok=True)
            print(f"[TRANSCRIPTION {session_id}] Using temp dir: {temp_dir}")
        else:
            temp_dir = tempfile.mkdtemp()
            print(f"[TRANSCRIPTION] Using temp dir: {temp_dir}")
        
        # Download video 
        video_path, video_info = download_video_audio(video_url, temp_dir)
        
        # Extract video metadata
        video_title = video_info.get('title', 'Unknown')
        duration = video_info.get('duration', 0)
        
        # Extract audio from video for transcription
        audio_path = os.path.join(temp_dir, "extracted_audio.wav")
        try:
            # Extract audio from video
            (
                ffmpeg
                .input(video_path)
                .output(audio_path, acodec='pcm_s16le', ar=22050, ac=1)
                .overwrite_output()
                .run(quiet=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to extract audio from video: {str(e)}")
        
        # Transcribe audio
        transcription_data = await transcribe_audio_file(audio_path)
        
        return {
            "success": True,
            "transcription": transcription_data["text"],
            "transcription_data": transcription_data,  # Full timing data for dubbing
            "video_title": video_title,
            "duration": duration,
            "audio_path": audio_path,  # Extracted audio for voice cloning
            "video_path": video_path  # Original video file for dubbing
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=f"Transcription process failed: {str(e)}")
    
    finally:
        # Files are kept in /tmp/video-dub/<session_id> for manual cleanup
        print(f"[TRANSCRIPTION] Temp files preserved in: {temp_dir}") 
