# Video Transcription App

A full-stack web application that allows users to submit YouTube video URLs for automatic transcription using yt-dlp and Deepgram AI.

## Features

- **TypeScript Frontend**: Modern React application with a clean, responsive UI
- **Python Backend**: FastAPI server with async video processing
- **YouTube Integration**: Download videos using yt-dlp
- **AI Transcription**: High-quality transcription using Deepgram's Nova-2 model
- **Real-time Feedback**: Loading states and error handling
- **Expandable Architecture**: Clean separation of concerns for easy feature additions

## Tech Stack

### Frontend

- React 18 with TypeScript
- Axios for API communication
- Modern CSS with gradient backgrounds and smooth animations
- Responsive design

### Backend

- FastAPI (Python)
- yt-dlp for video downloading
- Deepgram SDK for transcription
- Pydantic for data validation
- CORS enabled for frontend communication

## Prerequisites

- Node.js (v16 or higher)
- Python 3.8+
- Deepgram API key ([Get one here](https://deepgram.com/))

## Setup Instructions

### 1. Clone and Navigate

```bash
git clone <your-repo-url>
cd video-dub
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env.example .env
# Edit .env and add your Deepgram API key:
# DEEPGRAM_API_KEY=your_actual_api_key_here
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install
```

## Running the Application

### Start the Backend (Terminal 1)

```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python main.py
```

The backend will start at `http://localhost:8000`

### Start the Frontend (Terminal 2)

```bash
cd frontend
npm start
```

The frontend will start at `http://localhost:3000`

## Usage

1. Open your browser to `http://localhost:3000`
2. Enter a YouTube video URL in the input field
3. Click "Transcribe Video"
4. Wait for the video to be downloaded and transcribed
5. View the transcription results with video metadata

## API Endpoints

### `GET /health`

Health check endpoint

### `POST /transcribe`

Transcribe a YouTube video

**Request Body:**

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

**Response:**

```json
{
  "success": true,
  "transcription": "The transcribed text...",
  "video_title": "Video Title",
  "duration": 123.45
}
```

## Environment Variables

Create a `.env` file in the `backend` directory:

```env
DEEPGRAM_API_KEY=your_deepgram_api_key_here
```

## Architecture

```
video-dub/
├── backend/              # Python FastAPI backend
│   ├── main.py          # Main application file
│   ├── requirements.txt # Python dependencies
│   └── env.example      # Environment variables template
├── frontend/            # React TypeScript frontend
│   ├── src/
│   │   ├── App.tsx      # Main React component
│   │   ├── index.tsx    # React entry point
│   │   └── index.css    # Styles
│   ├── public/
│   │   └── index.html   # HTML template
│   ├── package.json     # Node.js dependencies
│   └── tsconfig.json    # TypeScript configuration
└── README.md           # This file
```

## Future Enhancements

The application is designed to be easily extensible. Some potential features:

- **User Authentication**: Add user accounts and transcription history
- **Multiple Languages**: Support for different transcription languages
- **Export Options**: Save transcriptions as PDF, DOCX, or SRT files
- **Batch Processing**: Upload multiple videos at once
- **Real-time Progress**: WebSocket connection for live progress updates
- **Speaker Diarization**: Identify different speakers in the audio
- **Sentiment Analysis**: Analyze the emotional tone of the transcription
- **Video Timestamps**: Link transcription text to specific video timestamps
- **Audio File Support**: Direct audio file uploads in addition to YouTube URLs

## Troubleshooting

### Common Issues

1. **Deepgram API Key Error**: Ensure your API key is set correctly in the `.env` file
2. **yt-dlp Download Fails**: Some videos may be restricted or require special handling
3. **CORS Issues**: Make sure the backend is running on port 8000 and frontend on port 3000
4. **Dependencies**: Ensure all dependencies are installed correctly

### Development Tips

- Check browser console for frontend errors
- Check terminal output for backend errors
- Use the `/health` endpoint to verify backend connectivity
- Test with shorter videos first to verify the setup

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - feel free to use this project as a starting point for your own applications.
