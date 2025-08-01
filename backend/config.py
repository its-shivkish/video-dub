"""Configuration management for Video Dubbing Studio"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration settings loaded from environment variables"""
    
    # API Keys
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    
    # File Storage
    TEMP_DIR_BASE = os.getenv("TEMP_DIR_BASE", "/tmp/video-dub")
    CLEANUP_TEMP_FILES = os.getenv("CLEANUP_TEMP_FILES", "false").lower() == "true"
    
    # Server Settings  
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # API URLs
    DEEPGRAM_BASE_URL = os.getenv("DEEPGRAM_BASE_URL", "https://api.deepgram.com")
    ELEVENLABS_BASE_URL = os.getenv("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io/v1")
    
    @classmethod
    def validate(cls):
        """Validate that all required environment variables are set"""
        missing_vars = []
        
        if not cls.DEEPGRAM_API_KEY:
            missing_vars.append("DEEPGRAM_API_KEY")
        if not cls.ELEVENLABS_API_KEY:
            missing_vars.append("ELEVENLABS_API_KEY")
            
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                f"Please create a .env file based on env.example"
            )
    
    @classmethod
    def get_temp_dir(cls, session_id: str = None) -> str:
        """Get temporary directory path for a session"""
        if session_id:
            return os.path.join(cls.TEMP_DIR_BASE, session_id)
        return cls.TEMP_DIR_BASE

# Global config instance
config = Config() 
