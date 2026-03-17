"""
Django settings for edtech_project project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url
import warnings

# Suppress noisy FutureWarning from google.api_core about Python EOL
# This doesn't fix the underlying Python version — upgrade Python to 3.11+ to remove permanently.
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module=r"google\.api_core\._python_version_support"
)

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# ALLOWED_HOSTS configuration
# On Render, allow all hosts since it's behind a proxy
if 'RENDER' in os.environ:
    ALLOWED_HOSTS = ['*']
else:
    _default_hosts = 'localhost,127.0.0.1,ed-tech-backend-tzn8.onrender.com,*.onrender.com,127.0.0.1:8000,127.0.0.1:8003'
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', _default_hosts).split(',')
    # Strip whitespace from each host
    ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'question_solver',
    'youtube_summarizer',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ═════════════════════════════════════════════════════════════════════════
# CORS Configuration - Allows Frontend to Access Backend API
# ═════════════════════════════════════════════════════════════════════════
# This fixes: "CORS policy: No 'Access-Control-Allow-Origin' header"

# Development: Allow all origins (localhost, etc.)
# Production: Configure CORS_ALLOWED_ORIGINS with specific domains
if DEBUG or 'RENDER' in os.environ:
    # Allow all origins in development and on Render
    CORS_ALLOW_ALL_ORIGINS = True
else:
    # For production with custom domain, uncomment and configure:
    # CORS_ALLOWED_ORIGINS = [
    #     'https://yourdomain.com',
    #     'https://www.yourdomain.com',
    # ]
    CORS_ALLOW_ALL_ORIGINS = True  # Fallback to allow all

# Allow credentials (cookies, authorization headers)
CORS_ALLOW_CREDENTIALS = True

# Allow all headers that frontend might send
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-user-id',  # Allow custom user ID header (lowercase)
    'X-User-ID',  # Allow custom user ID header (capitalized)
]

# Allow common HTTP methods
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'HEAD',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Cache preflight requests for 24 hours
CORS_PREFLIGHT_MAX_AGE = 86400

# Expose specific headers in response
CORS_EXPOSE_HEADERS = [
    'Content-Type',
    'X-CSRFToken',
]

ROOT_URLCONF = 'edtech_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'edtech_project.wsgi.application'


# Database
DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('SUPABASE_URL')
DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL or f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# File Upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# API Keys from environment
# Use SEARCHAPI_KEY as primary (SearchAPI.io), with SERP_API_KEY as fallback
# Both are set to SearchAPI.io key for production
SEARCHAPI_KEY = os.getenv('SEARCHAPI_KEY') or os.getenv('SERP_API_KEY', '')
SERP_API_KEY = os.getenv('SERP_API_KEY', '')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY', '')
GOOGLE_VISION_API_KEY = os.getenv('GOOGLE_VISION_API_KEY', '')

# Razorpay Payment Gateway Configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
RAZORPAY_ACCOUNT_NUMBER = os.getenv('RAZORPAY_ACCOUNT_NUMBER', '')  # Required for Payouts

# Razorpay Subscription Plan IDs
RAZORPAY_BASIC_PLAN_ID = os.getenv('RAZORPAY_BASIC_PLAN_ID', 'plan_basic_99')
RAZORPAY_PREMIUM_PLAN_ID = os.getenv('RAZORPAY_PREMIUM_PLAN_ID', 'plan_premium_499')

# Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Google OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')
GOOGLE_OAUTH_REDIRECT_URI = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '')
FRONTEND_REDIRECT_URI = os.getenv('FRONTEND_REDIRECT_URI', '')

# JWT Configuration
JWT_SECRET = os.getenv('JWT_SECRET', '')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
REFRESH_TOKEN_EXPIRATION_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRATION_DAYS', 7))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'filters': {
        'ignore_broken_pipe': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': lambda record: 'Broken pipe' not in str(record.msg),
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['ignore_broken_pipe'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'django': {
        'handlers': ['console'],
        'level': 'INFO',
        'propagate': False,
    },
}
