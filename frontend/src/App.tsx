import axios from 'axios';
import React, { useEffect, useState } from 'react';

interface TranscriptionResult {
  success: boolean;
  transcription?: string;
  error?: string;
  video_title?: string;
  duration?: number;
}

interface TranslationResult {
  success: boolean;
  original_transcription?: string;
  translated_text?: string;
  target_language?: string;
  error?: string;
  video_title?: string;
  duration?: number;
}

interface DubbingResult {
  success: boolean;
  session_id?: string;
  status?: string;
  progress?: number;
  video_url?: string;
  download_url?: string;
  error?: string;
}

interface Language {
  code: string;
  name: string;
}

interface Voice {
  id: string;
  name: string;
  description: string;
  accent?: string;
  gender?: string;
  age?: string;
}

function App() {
  const [url, setUrl] = useState('https://www.youtube.com/watch?v=jNQXAC9IVRw');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TranscriptionResult | TranslationResult | DubbingResult | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<string>('');
  const [availableLanguages, setAvailableLanguages] = useState<Language[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string>('clone');
  const [voiceStyle, setVoiceStyle] = useState<string>('natural');
  const [availableVoices, setAvailableVoices] = useState<any>(null);
  const [mode, setMode] = useState<'transcribe' | 'translate' | 'dub'>('transcribe');
  
  // Feature flag to disable voice options UI
  const showVoiceOptions = false;

  // Load available languages and voices on component mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch languages
        const languagesResponse = await axios.get('/languages');
        const languages = Object.entries(languagesResponse.data.languages).map(([code, name]) => ({
          code,
          name: name as string
        }));
        setAvailableLanguages(languages);

        // Only fetch voices if feature flag is enabled
        if (showVoiceOptions) {
          const voicesResponse = await axios.get('/voices');
          console.log('Voices fetched:', voicesResponse.data.voices);
          setAvailableVoices(voicesResponse.data.voices);
        }
      } catch (error) {
        console.error('Failed to fetch data:', error);
      }
    };
    
    fetchData();
  }, [showVoiceOptions]);

  // Auto-update mode based on selections - default to dubbing when language is selected
  useEffect(() => {
    if (selectedLanguage) {
      setMode('dub'); // Always dub when language is selected
    } else {
      setMode('transcribe');
    }
  }, [selectedLanguage]);

  // When voice options are disabled, hard-code to voice cloning and natural style
  useEffect(() => {
    if (!showVoiceOptions) {
      setSelectedVoice('clone');
      setVoiceStyle('natural');
    }
  }, [showVoiceOptions]);

  const isValidYouTubeUrl = (url: string): boolean => {
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/;
    return youtubeRegex.test(url);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!url.trim()) {
      setResult({
        success: false,
        error: 'Please enter a YouTube URL'
      });
      return;
    }

    if (!isValidYouTubeUrl(url)) {
      setResult({
        success: false,
        error: 'Please enter a valid YouTube URL'
      });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      if (mode === 'dub') {
        // Dubbing mode
        const response = await axios.post('/dub', { 
          url, 
          target_language: selectedLanguage,
          voice_option: selectedVoice,
          voice_style: voiceStyle
        });
        setResult(response.data);
        
        // Start polling for progress if dubbing started successfully
        if (response.data.success && response.data.session_id) {
          pollDubbingStatus(response.data.session_id);
        }
      } else if (mode === 'translate') {
        // Translate mode
        const response = await axios.post('/translate', { 
          url, 
          target_language: selectedLanguage 
        });
        setResult(response.data);
      } else {
        // Transcribe mode
        const response = await axios.post('/transcribe', { url });
        setResult(response.data);
      }
    } catch (error: any) {
      console.error('Processing error:', error);
      setResult({
        success: false,
        error: error.response?.data?.detail || `Failed to ${mode} video. Please try again.`
      });
    } finally {
      if (mode !== 'dub') {
        setLoading(false);
      }
    }
  };

  const pollDubbingStatus = async (sessionId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`/dub/status/${sessionId}`);
        setResult(response.data);
        
        if (response.data.status === 'completed' || response.data.status === 'failed') {
          clearInterval(pollInterval);
          setLoading(false);
        }
      } catch (error) {
        clearInterval(pollInterval);
        setLoading(false);
        setResult({
          success: false,
          error: 'Failed to get dubbing status'
        });
      }
    }, 2000); // Poll every 2 seconds
  };

  const formatDuration = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const isTranslationResult = (result: any): result is TranslationResult => {
    return result && 'translated_text' in result;
  };

  const isDubbingResult = (result: any): result is DubbingResult => {
    return result && 'session_id' in result;
  };

  const getButtonText = () => {
    if (loading) {
      if (mode === 'dub') {
        const dubbingResult = result as DubbingResult;
        const status = dubbingResult?.status;
        if (status === 'transcribing') return 'Transcribing...';
        if (status === 'translating') return 'Translating...';
        if (status === 'generating_voice') return 'Generating Voice...';
        if (status === 'combining_video') return 'Creating Video...';
        return 'Processing...';
      }
      return 'Processing...';
    }
    
    switch (mode) {
      case 'dub': return 'Dub Video';
      default: return 'Transcribe Video';
    }
  };

  return (
    <div className="container">
      <div className="card">
        <h1 className="title">Video Dubbing Studio</h1>
        <p className="subtitle">
          Enter a YouTube URL and select a target language to create dubbed videos with AI voice synthesis
        </p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="url" className="label">
              YouTube URL
            </label>
            <input
              type="url"
              id="url"
              className="input"
              placeholder="https://www.youtube.com/watch?v=jNQXAC9IVRw"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="language" className="label">
              Target Language
            </label>
            <select
              id="language"
              className="input"
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              disabled={loading}
            >
              <option value="">Select Language to Dub</option>
              {availableLanguages.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
          </div>

          {selectedLanguage && showVoiceOptions && (
            <>
              <div className="form-group">
                <label htmlFor="voice" className="label">
                  Voice Option
                </label>
                                 <select
                   id="voice"
                   className="input"
                   value={selectedVoice}
                   onChange={(e) => setSelectedVoice(e.target.value)}
                   disabled={loading}
                 >
                   {/* Always show clone option as fallback */}
                   <option value="clone">
                     {availableVoices?.clone?.name || "Voice Cloning (Match Original Speaker)"}
                   </option>
                   
                   {/* Show prebuilt voices if available */}
                   {availableVoices?.prebuilt?.length > 0 && 
                     availableVoices.prebuilt.map((voice: Voice) => (
                       <option key={voice.id} value={voice.id}>
                         {voice.name} {voice.gender && voice.accent && `(${voice.gender}, ${voice.accent})`}
                       </option>
                     ))
                   }
                   
                   {/* Debug info */}
                   {!availableVoices && <option disabled>Loading voices...</option>}
                 </select>
              </div>

              <div className="form-group">
                <label htmlFor="style" className="label">
                  Voice Style
                </label>
                <select
                  id="style"
                  className="input"
                  value={voiceStyle}
                  onChange={(e) => setVoiceStyle(e.target.value)}
                  disabled={loading}
                >
                  <option value="natural">Natural</option>
                  <option value="dramatic">Dramatic</option>
                  <option value="calm">Calm</option>
                  <option value="energetic">Energetic</option>
                </select>
              </div>
            </>
          )}

          <button
            type="submit"
            className="button"
            disabled={loading || !url.trim()}
          >
            {loading ? (
              <div className="loading">
                <div className="spinner"></div>
                {getButtonText()}
              </div>
            ) : (
              getButtonText()
            )}
          </button>

          {isDubbingResult(result) && result.progress !== undefined && (
            <div className="progress-container">
              <div className="progress-bar">
                <div 
                  className="progress-fill" 
                  style={{ width: `${result.progress}%` }}
                ></div>
              </div>
              <div className="progress-text">
                {result.progress}% - {result.status}
              </div>
            </div>
          )}
        </form>

        {result && (
          <div className={`result ${result.success && (!isDubbingResult(result) || result.status === 'completed') ? '' : 'error'}`}>
            {result.success && (!isDubbingResult(result) || result.status === 'completed') ? (
              <>
                <div className="result-title">
                  <span className="success-icon">✓</span>
                  {isDubbingResult(result) ? 
                    (result.status === 'completed' ? 'Video Dubbing Complete' : 'Processing...') : 
                   isTranslationResult(result) ? 'Translation Complete' : 'Transcription Complete'}
                </div>
                
                {isDubbingResult(result) && result.status === 'completed' && result.video_url ? (
                  <div className="video-container">
                    <div className="video-player">
                      <h3>Dubbed Video</h3>
                      <video 
                        controls 
                        width="100%" 
                        style={{ maxWidth: '500px' }}
                        src={result.video_url}
                      >
                        Your browser does not support the video tag.
                      </video>
                      <div className="video-actions">
                        <a 
                          href={result.download_url} 
                          download 
                          className="download-button"
                        >
                          Download Dubbed Video
                        </a>
                      </div>
                    </div>
                  </div>
                                 ) : !isDubbingResult(result) && (
                   <>
                     {((!isDubbingResult(result) && result.video_title) || (!isDubbingResult(result) && result.duration)) && (
                       <div className="result-meta">
                         {!isDubbingResult(result) && result.video_title && (
                           <div><strong>Title:</strong> {result.video_title}</div>
                         )}
                         {!isDubbingResult(result) && result.duration && (
                           <div><strong>Duration:</strong> {formatDuration(result.duration)}</div>
                         )}
                         {isTranslationResult(result) && result.target_language && (
                           <div><strong>Language:</strong> {availableLanguages.find(l => l.code === result.target_language)?.name || result.target_language}</div>
                         )}
                       </div>
                     )}
                     
                     {isTranslationResult(result) ? (
                       <>
                         <div className="result-section">
                           <h3>Original Transcription:</h3>
                           <div className="transcription">
                             {result.original_transcription}
                           </div>
                         </div>
                         <div className="result-section">
                           <h3>Translation:</h3>
                           <div className="transcription translated">
                             {result.translated_text}
                           </div>
                         </div>
                       </>
                     ) : !isDubbingResult(result) && (
                       <div className="transcription">
                         {result.transcription}
                       </div>
                     )}
                   </>
                 )}
              </>
            ) : (
              <>
                <div className="result-title">
                  ❌ {isDubbingResult(result) && result.status === 'failed' ? 'Dubbing Failed' : 'Error'}
                </div>
                <div>
                  {isDubbingResult(result) && result.status === 'failed' 
                    ? `Dubbing failed at ${result.progress || 0}%. ${result.error || 'Please try again with a different video or voice option.'}`
                    : result.error
                  }
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App; 
