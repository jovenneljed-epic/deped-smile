import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Official Philippine Standard Time (PST / PHT = UTC+8)
PHT = timezone(timedelta(hours=8))

def pht_now() -> datetime:
    """Returns current naive datetime in Philippine Standard Time (UTC+8)."""
    return datetime.now(PHT).replace(tzinfo=None)

# Detect Vercel or Serverless Runtime
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
PHOTOS_DIR = DATA_DIR / "student_photos"

# On Vercel, the source directory is read-only; redirect dynamic data to /tmp
if IS_VERCEL:
    WRITABLE_DIR = Path("/tmp/smile_data")
    try:
        WRITABLE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    DB_PATH = WRITABLE_DIR / "smile_records.db"
    PHOTOS_DIR = WRITABLE_DIR / "student_photos"
    try:
        PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    # Seed SQLite into /tmp if not present
    src_db = DATA_DIR / "smile_records.db"
    if not DB_PATH.exists() and src_db.exists():
        try:
            import shutil
            shutil.copy2(src_db, DB_PATH)
        except Exception as e:
            print(f"[!] Note: using fresh DB in /tmp: {e}")
    SCHOOL_SETTINGS_PATH = WRITABLE_DIR / "school_settings.json"
    src_settings = DATA_DIR / "school_settings.json"
    if not SCHOOL_SETTINGS_PATH.exists() and src_settings.exists():
        try:
            import shutil
            shutil.copy2(src_settings, SCHOOL_SETTINGS_PATH)
        except Exception:
            pass
    SMS_SETTINGS_PATH = WRITABLE_DIR / "sms_settings.json"
    src_sms = DATA_DIR / "sms_settings.json"
    if not SMS_SETTINGS_PATH.exists() and src_sms.exists():
        try:
            import shutil
            shutil.copy2(src_sms, SMS_SETTINGS_PATH)
        except Exception:
            pass
else:
    # Ensure local runtime directories exist
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    DB_PATH = DATA_DIR / "smile_records.db"
    SCHOOL_SETTINGS_PATH = DATA_DIR / "school_settings.json"
    SMS_SETTINGS_PATH = DATA_DIR / "sms_settings.json"

# -------------------------------------------------------------
# Enterprise Database Engine Configuration (SQLAlchemy ORM)
# -------------------------------------------------------------
# Options: "SQLITE", "MYSQL", "POSTGRESQL"
DATABASE_TYPE = os.environ.get("DATABASE_TYPE", "SQLITE")

# Database Connection URLs:
# 1. SQLite: Local file database (Zero configuration required)
SQLITE_URL = f"sqlite:///{DB_PATH}"

# 2. MySQL / MariaDB: Standard XAMPP or Campus Network MySQL server
MYSQL_URL = os.environ.get("MYSQL_URL", "mysql+pymysql://root:@localhost:3306/deped_smile")

# 3. PostgreSQL: Campus enterprise or Cloud Supabase / Neon server
POSTGRES_URL = os.environ.get("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/deped_smile")

def get_database_url():
    """Returns the active SQLAlchemy database URL based on configuration or cloud environment."""
    import re
    # Check for direct DATABASE_URL or Vercel's POSTGRES_URL
    env_url = (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "").strip()
    if env_url:
        # Standardize legacy Heroku/Vercel postgres:// protocol to postgresql://
        if env_url.startswith("postgres://"):
            env_url = env_url.replace("postgres://", "postgresql://", 1)

        # Supabase Direct Connection (db.<ref>.supabase.co) only has IPv6 addresses.
        # AWS Lambda / Vercel Serverless run on IPv4 and cannot route to IPv6 directly.
        # Auto-route to the official Supabase Connection Pooler (IPv4 compatible):
        if "db.ukhmrgbkrfawgszltzsr.supabase.co" in env_url:
            env_url = env_url.replace("db.ukhmrgbkrfawgszltzsr.supabase.co:5432", "aws-0-ap-northeast-2.pooler.supabase.com:6543")
            env_url = env_url.replace("db.ukhmrgbkrfawgszltzsr.supabase.co", "aws-0-ap-northeast-2.pooler.supabase.com:6543")
            if "://postgres:" in env_url:
                env_url = env_url.replace("://postgres:", "://postgres.ukhmrgbkrfawgszltzsr:")
        elif ".supabase.co" in env_url:
            region = os.environ.get("SUPABASE_REGION", "ap-northeast-2")
            match = re.search(r'db\.([a-z0-9]+)\.supabase\.co', env_url)
            if match:
                ref = match.group(1)
                env_url = env_url.replace(f"db.{ref}.supabase.co:5432", f"aws-0-{region}.pooler.supabase.com:6543")
                env_url = env_url.replace(f"db.{ref}.supabase.co", f"aws-0-{region}.pooler.supabase.com:6543")
                if "://postgres:" in env_url:
                    env_url = env_url.replace("://postgres:", f"://postgres.{ref}:")

        # Strip all query parameters (sslmode, channel_binding, etc.) because pg8000 handles SSL via ssl_context
        if "?" in env_url:
            env_url = env_url.split("?")[0]

        # Use pg8000 pure-Python driver for maximum stability across Windows, Linux, and Vercel Serverless
        if env_url.startswith("postgresql://"):
            try:
                import pg8000
                env_url = env_url.replace("postgresql://", "postgresql+pg8000://", 1)
            except ImportError:
                pass
        elif env_url.startswith("mysql://") and not env_url.startswith("mysql+pymysql://"):
            env_url = env_url.replace("mysql://", "mysql+pymysql://", 1)

        return env_url

    db_choice = DATABASE_TYPE.upper().strip()
    if db_choice == "MYSQL":
        return MYSQL_URL
    elif db_choice == "POSTGRESQL":
        url = POSTGRES_URL
        if url.startswith("postgresql://"):
            try:
                import pg8000
                url = url.replace("postgresql://", "postgresql+pg8000://", 1)
            except ImportError:
                pass
        return url
    else:
        return f"sqlite:///{DB_PATH}"

DEFAULT_SCHOOL_SETTINGS = {
    "school_name": "Don Montano Central Integrated School",
    "school_short_name": "DMCIS",
    "deped_region": "Region IV-A CALABARZON",
    "school_id": "152008",
    "system_domain": "https://classic-optics-cooperative-therapy.trycloudflare.com"
}

def load_school_settings():
    """Loads persistent school settings or returns defaults."""
    import json
    settings = dict(DEFAULT_SCHOOL_SETTINGS)
    if SCHOOL_SETTINGS_PATH.exists():
        try:
            with open(SCHOOL_SETTINGS_PATH, "r", encoding="utf-8") as f:
                settings.update(json.load(f))
        except Exception as e:
            print(f"[!] Warning reading school_settings.json: {e}")
    return settings

def save_school_settings(new_settings):
    """Persists updated school configuration and updates module globals."""
    import json
    global SCHOOL_NAME, SCHOOL_SHORT_NAME, SYSTEM_DOMAIN
    current = load_school_settings()
    current.update(new_settings)
    with open(SCHOOL_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    SCHOOL_NAME = current.get("school_name", SCHOOL_NAME)
    SCHOOL_SHORT_NAME = current.get("school_short_name", SCHOOL_SHORT_NAME)
    SYSTEM_DOMAIN = current.get("system_domain", SYSTEM_DOMAIN)
    return current

_active_school = load_school_settings()
SCHOOL_NAME = _active_school.get("school_name", "Don Montano Central Integrated School")
SCHOOL_SHORT_NAME = _active_school.get("school_short_name", "DMCIS")
SYSTEM_DOMAIN = _active_school.get("system_domain", "https://classic-optics-cooperative-therapy.trycloudflare.com")


# Comprehensive DepEd K-12 Grade Levels (Kindergarten to Senior High School)
GRADE_LEVELS = [
    "Kindergarten",
    "Grade 1",
    "Grade 2",
    "Grade 3",
    "Grade 4",
    "Grade 5",
    "Grade 6",
    "Grade 7",
    "Grade 8",
    "Grade 9",
    "Grade 10",
    "Grade 11",
    "Grade 12"
]

CURRICULUM_STRANDS = [
    "Early Childhood",
    "Elementary (K-12)",
    "Junior High School",
    "Senior High - STEM",
    "Senior High - ABM",
    "Senior High - HUMSS",
    "Senior High - GAS",
    "Senior High - TVL (ICT)",
    "Senior High - TVL (Home Economics)",
    "Senior High - TVL (Industrial Arts)",
    "Senior High - TVL (Agri-Fishery Arts)"
]

# AI / Computer Vision Model Settings (YuNet + SFace)
YUNET_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

YUNET_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

# Recognition Thresholds
COSINE_SIMILARITY_THRESHOLD = 0.363
DETECTION_CONFIDENCE = 0.55  # Optimized for high sensitivity & fast face-locking in school lighting

# Camera Settings
CAMERA_INDEX = 0          # 0 is usually default webcam, 1 for external USB camera
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# Attendance & Debounce Rules
COOLDOWN_SECONDS = 25     # Responsive 25-second cooldown between arrival (Time-In) and departure (Time-Out)
MIDDAY_SPLIT_HOUR = 12

# SMS Settings Persistence File
SMS_SETTINGS_PATH = DATA_DIR / "sms_settings.json"

# Default SMS Configuration
# Supported Modes: "SEMAPHORE", "TWILIO", "ANDROID_GATEWAY", "PHILSMS", "GSM", "MOCK"
DEFAULT_SMS_SETTINGS = {
    "mode": "MOCK",
    "semaphore_api_key": "",
    "semaphore_sender_name": "SEMAPHORE",
    "twilio_account_sid": "",
    "twilio_auth_token": "",
    "twilio_from_number": "",
    "android_gateway_url": "http://192.168.1.100:8080/send",
    "android_gateway_key": "",
    "philsms_api_key": "",
    "philsms_sender_id": "PhilSMS",
    "gsm_port": "COM3",
    "gsm_baudrate": 9600
}

def load_sms_settings():
    """Loads persistent SMS settings from data/sms_settings.json or returns defaults."""
    import json
    settings = dict(DEFAULT_SMS_SETTINGS)
    if SMS_SETTINGS_PATH.exists():
        try:
            with open(SMS_SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception as e:
            print(f"[!] Warning reading sms_settings.json: {e}")
    return settings

def save_sms_settings(new_settings):
    """Persists updated SMS configuration to data/sms_settings.json and syncs module globals."""
    import json
    current = load_sms_settings()
    current.update(new_settings)
    with open(SMS_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    _sync_sms_globals(current)
    return current

# Initialize active SMS settings
_active_sms = load_sms_settings()

SMS_MODE = _active_sms.get("mode", "MOCK")
SEMAPHORE_API_KEY = _active_sms.get("semaphore_api_key", "")
SEMAPHORE_SENDER_NAME = _active_sms.get("semaphore_sender_name", "SEMAPHORE")
TWILIO_ACCOUNT_SID = _active_sms.get("twilio_account_sid", "")
TWILIO_AUTH_TOKEN = _active_sms.get("twilio_auth_token", "")
TWILIO_FROM_NUMBER = _active_sms.get("twilio_from_number", "")
ANDROID_GATEWAY_URL = _active_sms.get("android_gateway_url", "http://192.168.1.100:8080/send")
ANDROID_GATEWAY_KEY = _active_sms.get("android_gateway_key", "")
PHILSMS_API_KEY = _active_sms.get("philsms_api_key", "")
PHILSMS_SENDER_ID = _active_sms.get("philsms_sender_id", "PhilSMS")
GSM_PORT = _active_sms.get("gsm_port", "COM3")
GSM_BAUDRATE = int(_active_sms.get("gsm_baudrate", 9600))

def _sync_sms_globals(settings):
    """Updates module-level SMS configuration variables."""
    global SMS_MODE, SEMAPHORE_API_KEY, SEMAPHORE_SENDER_NAME
    global TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
    global ANDROID_GATEWAY_URL, ANDROID_GATEWAY_KEY
    global PHILSMS_API_KEY, PHILSMS_SENDER_ID, GSM_PORT, GSM_BAUDRATE
    SMS_MODE = settings.get("mode", "MOCK")
    SEMAPHORE_API_KEY = settings.get("semaphore_api_key", "")
    SEMAPHORE_SENDER_NAME = settings.get("semaphore_sender_name", "SEMAPHORE")
    TWILIO_ACCOUNT_SID = settings.get("twilio_account_sid", "")
    TWILIO_AUTH_TOKEN = settings.get("twilio_auth_token", "")
    TWILIO_FROM_NUMBER = settings.get("twilio_from_number", "")
    ANDROID_GATEWAY_URL = settings.get("android_gateway_url", "http://192.168.1.100:8080/send")
    ANDROID_GATEWAY_KEY = settings.get("android_gateway_key", "")
    PHILSMS_API_KEY = settings.get("philsms_api_key", "")
    PHILSMS_SENDER_ID = settings.get("philsms_sender_id", "PhilSMS")
    GSM_PORT = settings.get("gsm_port", "COM3")
    GSM_BAUDRATE = int(settings.get("gsm_baudrate", 9600))

def get_sms_config():
    """Returns current active SMS configuration dictionary."""
    return load_sms_settings()

# Audio Feedback
ENABLE_AUDIO_CHIME = True

# -------------------------------------------------------------
# W3C Web Push & VAPID Protocol Configuration
# Enables background push alerts even when phone is locked or screen is off
# -------------------------------------------------------------
VAPID_PUBLIC_KEY = os.environ.get(
    "VAPID_PUBLIC_KEY",
    "BAYf8s94I-kyzgkA_YzRuCnOfiG8ZKgJaQYBYuLov9JUxGzA88cZ3sN3bilULTl2TaSZvXF1ZjYPlllllmZjfsw"
)

VAPID_PRIVATE_KEY = os.environ.get(
    "VAPID_PRIVATE_KEY",
    """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg5EhyUVpRWGUwtxYI
Rb3cnZcbgcr6g1cVLjGAuebfVkKhRANCAAQGH/LPeCPpMs4JAP2M0bgpzn4hvGSo
CWkGAWLi6L/SVMRswPPHGd7Dd24pVC05dk2kmb1xdWY2D5ZZZZZmY37M
-----END PRIVATE KEY-----"""
)

VAPID_CLAIMS = {
    "sub": os.environ.get("VAPID_CLAIM_EMAIL", "mailto:deped.smile.alerts@gmail.com")
}

