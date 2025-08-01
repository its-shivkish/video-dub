import httpx
from typing import Dict, Any, Protocol
from fastapi import HTTPException
from googletrans import Translator
import asyncio


class TranslationProvider(Protocol):
    """Protocol for translation providers - allows easy swapping of APIs"""
    
    async def translate_text(self, text: str, target_language: str) -> str:
        """Translate text to target language"""
        ...


class GoogleTranslateFreeTranslator:
    """Free Google Translate implementation using googletrans library"""
    
    def __init__(self, api_key: str = None):
        # No API key needed for free service
        self.translator = Translator()
    
    async def translate_text(self, text: str, target_language: str) -> str:
        """
        Translate text using free Google Translate service
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'es', 'fr', 'de')
        
        Returns:
            Translated text
        """
        try:
            # Run the blocking translation in a thread pool to make it async
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.translator.translate(text, dest=target_language)
            )
            
            return result.text
            
        except Exception as e:
            # Fallback to placeholder if translation fails
            language_name = SUPPORTED_LANGUAGES.get(target_language, target_language)
            print(f"Translation failed: {e}, using fallback")
            return f"[Translation service unavailable - {language_name}] {text}"



class GoogleTranslateProvider:
    """Alternative Google Translate implementation (placeholder for future use)"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def translate_text(self, text: str, target_language: str) -> str:
        """Google Translate implementation - not implemented yet"""
        raise HTTPException(status_code=501, detail="Google Translate not implemented yet")


# Supported languages mapping
SUPPORTED_LANGUAGES = {
    "es": "Spanish",
    "fr": "French", 
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
    "nl": "Dutch",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "tr": "Turkish",
    "he": "Hebrew",
    "th": "Thai",
    "vi": "Vietnamese"
}


def get_translator(provider: str = "google_free") -> TranslationProvider:
    """
    Factory function to get translation provider
    
    Args:
        provider: Provider name ('google_free', 'google', etc.)
    
    Returns:
        Translation provider instance
    """
    if provider == "google_free":
        return GoogleTranslateFreeTranslator()
    elif provider == "google":
        return GoogleTranslateProvider("api_key_placeholder")
    else:
        raise ValueError(f"Unsupported translation provider: {provider}")


async def translate_transcription(text: str, target_language: str, provider: str = "google_free") -> str:
    """
    Translate transcribed text to target language
    
    Args:
        text: Transcribed text to translate
        target_language: Language code (e.g., 'es', 'fr', 'de')
        provider: Translation provider to use
    
    Returns:
        Translated text
    """
    if target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported language: {target_language}. Supported: {list(SUPPORTED_LANGUAGES.keys())}"
        )
    
    translator = get_translator(provider)
    return await translator.translate_text(text, target_language) 
