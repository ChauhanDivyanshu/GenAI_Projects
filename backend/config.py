# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_AI_KEY = os.getenv('GOOGLE_AI_KEY')

    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///meetings.db'
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/meeting_analyzer')

    # Recording Settings
    RECORDING_DIR = 'static/recordings'
    SCREEN_FPS = 15
    AUDIO_SAMPLE_RATE = 44100
    VIDEO_RESOLUTION = (1920, 1080)

    # AI Settings
    WHISPER_MODEL = 'medium'  # tiny, base, small, medium, large
    CHEATING_THRESHOLD = 0.7
    ANSWER_QUALITY_THRESHOLD = 0.6

    # Cheating Detection Thresholds
    EYE_AWAY_THRESHOLD = 3.0      # seconds looking away
    TAB_SWITCH_THRESHOLD = 2       # number of tab switches
    FACE_ABSENCE_THRESHOLD = 5.0   # seconds face not visible
    MULTIPLE_FACE_ALERT = True

    # Report Settings
    REPORT_FORMAT = 'pdf'  # pdf, html, json

    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
