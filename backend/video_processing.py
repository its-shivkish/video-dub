import os
import tempfile
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

import ffmpeg
from fastapi import HTTPException

from config import config


class VideoProcessor:
    """Handle video processing and audio synchronization using FFmpeg"""
    
    def __init__(self, session_id: str = None):
        if session_id:
            self.temp_dir = config.get_temp_dir(session_id)
            os.makedirs(self.temp_dir, exist_ok=True)
            print(f"[VIDEO_PROCESSOR {session_id}] Using temp dir: {self.temp_dir}")
        else:
            self.temp_dir = tempfile.mkdtemp()
            print(f"[VIDEO_PROCESSOR] Using temp dir: {self.temp_dir}")
    
    async def combine_video_with_dubbed_audio(
        self,
        original_video_path: str,
        dubbed_audio_path: str,
        transcription_data: Dict[str, Any]
    ) -> str:
        """
        Combine original video with dubbed audio, maintaining synchronization
        
        Args:
            original_video_path: Path to original video file
            dubbed_audio_path: Path to dubbed audio file
            transcription_data: Timing data for synchronization
            
        Returns:
            Path to final dubbed video file
        """
        try:
            print(f"[VIDEO_PROCESSOR] Starting video combination...")
            print(f"[VIDEO_PROCESSOR] Original video: {original_video_path}")
            print(f"[VIDEO_PROCESSOR] Dubbed audio: {dubbed_audio_path}")
            print(f"[VIDEO_PROCESSOR] Video exists: {os.path.exists(original_video_path)}")
            print(f"[VIDEO_PROCESSOR] Audio exists: {os.path.exists(dubbed_audio_path)}")
            
            output_path = os.path.join(self.temp_dir, "dubbed_video.mp4")
            print(f"[VIDEO_PROCESSOR] Output path: {output_path}")
            
            # Get video duration from transcription data or video file
            duration = transcription_data.get("duration", None)
            print(f"[VIDEO_PROCESSOR] Duration from transcription: {duration}")
            
            # Use FFmpeg to combine video and audio
            video_input = ffmpeg.input(original_video_path)
            audio_input = ffmpeg.input(dubbed_audio_path)
            
            # Create output with original video and new audio - explicit method
            stream = ffmpeg.output(
                video_input['v:0'],  # Video stream from original (first video stream)
                audio_input['a:0'],  # Audio stream from dubbed audio (first audio stream)
                output_path,
                vcodec='copy',  # Copy video without re-encoding
                acodec='aac'    # Encode audio as AAC
            )
            
            # Add flags explicitly
            stream = stream.overwrite_output()  # Equivalent to -y flag
            stream = stream.global_args('-shortest')  # Match shortest stream duration
            
            # Show the FFmpeg command that will be executed
            ffmpeg_cmd = ffmpeg.compile(stream)
            print(f"[VIDEO_PROCESSOR] FFmpeg command: {' '.join(ffmpeg_cmd)}")
            
            # Run FFmpeg command asynchronously
            process = await asyncio.create_subprocess_exec(
                *ffmpeg.compile(stream),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
                print(f"FFmpeg error (return code {process.returncode}): {error_msg}")
                raise HTTPException(status_code=500, detail=f"FFmpeg failed: {error_msg}")
            
            if not os.path.exists(output_path):
                raise HTTPException(status_code=500, detail="Video processing failed - output file not created")
            
            print(f"Video combination successful: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"[VIDEO_PROCESSOR] Error in combine_video_with_dubbed_audio: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Video processing failed: {str(e)}")
    
    async def extract_audio_segment(
        self,
        video_path: str,
        start_time: float = 0,
        duration: Optional[float] = None
    ) -> str:
        """
        Extract audio segment from video for voice cloning
        
        Args:
            video_path: Path to video file
            start_time: Start time in seconds
            duration: Duration in seconds (None for entire video)
            
        Returns:
            Path to extracted audio file
        """
        try:
            audio_output_path = os.path.join(self.temp_dir, "extracted_audio.wav")
            
            input_video = ffmpeg.input(video_path, ss=start_time)
            
            if duration:
                input_video = ffmpeg.input(video_path, ss=start_time, t=duration)
            
            # Extract audio as WAV for better quality
            output = ffmpeg.output(
                input_video['a'],
                audio_output_path,
                acodec='pcm_s16le',  # Uncompressed audio for voice cloning
                ar=22050,            # 22kHz sample rate (good for voice cloning)
                ac=1,                # Mono audio
                y=True
            )
            
            # Run FFmpeg command
            await asyncio.create_subprocess_exec(
                *ffmpeg.compile(output),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            if not os.path.exists(audio_output_path):
                raise HTTPException(status_code=500, detail="Audio extraction failed")
            
            return audio_output_path
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")
    
    def cleanup(self):
        """Clean up temporary files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)


class DubbingPipeline:
    """Complete video dubbing pipeline"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create new dubbing session"""
        self.sessions[session_id] = {
            "status": "created",
            "progress": 0,
            "original_video_path": None,
            "dubbed_video_path": None,
            "created_at": asyncio.get_event_loop().time()
        }
        return self.sessions[session_id]
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.sessions.get(session_id)
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up sessions older than max_age_hours"""
        current_time = asyncio.get_event_loop().time()
        cutoff_time = current_time - (max_age_hours * 3600)
        
        expired_sessions = [
            session_id for session_id, data in self.sessions.items()
            if data.get("created_at", 0) < cutoff_time
        ]
        
        for session_id in expired_sessions:
            session_data = self.sessions.pop(session_id, {})
            # Clean up video files
            for path_key in ["original_video_path", "dubbed_video_path"]:
                path = session_data.get(path_key)
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass


# Global dubbing pipeline instance
dubbing_pipeline = DubbingPipeline() 
