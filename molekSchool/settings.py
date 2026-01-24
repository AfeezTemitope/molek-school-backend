"""
Django Settings for MOLEK School Backend
Enhanced with caching, indexing configuration, and optimizations
"""
from pathlib import Path
from decouple import config
from datetime import timedelta
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# SECURITY SETTINGS
# ==============================================================================
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
DJANGO_ENV = config("DJANGO_ENV", default="production")

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "molek-school-backend-production.up.railway.app",
    "molek-school-web-portal-front-end.vercel.app",
    "molek-admin.vercel.app",
    "molek.netlify.app",
    "admin.molekschool.com",
    "molekschool.com",
    "www.molekschool.com",
    "molek-school-backend.onrender.com",
]

# ==============================================================================
# CORS & CSRF SETTINGS
# ==============================================================================
CSRF_TRUSTED_ORIGINS = [
    "https://admin.molekschool.com",
    "https://molekschool.com",
    "https://www.molekschool.com",
    "https://molek-admin.vercel.app",
    "https://molek-school-backend-production.up.railway.app",
    "https://molek-school-web-portal-front-end.vercel.app",
    "https://molek.netlify.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + ["X-CSRFToken", "authorization"]
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"

LOGIN_REDIRECT_URL = "/admin/"

# ==============================================================================
# INSTALLED APPS
# ==============================================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Local apps
    "users",
    "content",
    "gallery",
    
    # Third-party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
]

# ==============================================================================
# MIDDLEWARE
# ==============================================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

ROOT_URLCONF = "molekSchool.urls"

# ==============================================================================
# TEMPLATES
# ==============================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "molekSchool.wsgi.application"

# ==============================================================================
# DATABASE
# ==============================================================================
DB_ENGINE = config("DB_ENGINE", default="django.db.backends.sqlite3")

if "sqlite" in DB_ENGINE:
    # SQLite configuration (local development)
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": BASE_DIR / config("DB_NAME", default="db.sqlite3"),
        }
    }
else:
    # PostgreSQL configuration (production)
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST"),
            "PORT": config("DB_PORT"),
            # Connection pooling optimization (PostgreSQL only)
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "connect_timeout": 10,
            },
        }
    }

# ==============================================================================
# PASSWORD VALIDATION
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ==============================================================================
# INTERNATIONALIZATION
# ==============================================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# ==============================================================================
# STATIC FILES
# ==============================================================================
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ==============================================================================
# MEDIA FILES (Cloudinary)
# ==============================================================================
MEDIA_URL = "/media/"
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

# ==============================================================================
# AUTH
# ==============================================================================
AUTH_USER_MODEL = "users.UserProfile"

# ==============================================================================
# REST FRAMEWORK
# ==============================================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    # Throttling to prevent abuse
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}

# ==============================================================================
# JWT SETTINGS
# ==============================================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ==============================================================================
# CLOUDINARY
# ==============================================================================
import cloudinary
import cloudinary.uploader
import cloudinary.api

cloudinary.config(
    cloud_name=config("CLOUD_NAME"),
    api_key=config("API_KEY"),
    api_secret=config("API_SECRET"),
    secure=True,
)

# ==============================================================================
# CACHING CONFIGURATION
# ==============================================================================
# Cache timeout constants (in seconds)
CACHE_TIMEOUT_STATIC = 3600      # 1 hour - Class levels, rarely changes
CACHE_TIMEOUT_ACADEMIC = 1800    # 30 minutes - Sessions, terms, subjects
CACHE_TIMEOUT_STUDENT = 300      # 5 minutes - Student data
CACHE_TIMEOUT_SCORE = 120        # 2 minutes - Scores/results (changes during upload)
CACHE_TIMEOUT_SHORT = 60         # 1 minute - Very dynamic data

# Cache configuration
if DJANGO_ENV == "production":
    # For production, use Redis if available, otherwise use database cache
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache_table",
            "TIMEOUT": CACHE_TIMEOUT_ACADEMIC,  # Default timeout
            "OPTIONS": {
                "MAX_ENTRIES": 1000,
                "CULL_FREQUENCY": 3,  # Remove 1/3 of entries when max reached
            }
        }
    }
else:
    # For development, use local memory cache
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
            "TIMEOUT": CACHE_TIMEOUT_ACADEMIC,
            "OPTIONS": {
                "MAX_ENTRIES": 1000,
            }
        }
    }

# Cache key prefixes for different data types
CACHE_KEY_PREFIX = "molek"

# ==============================================================================
# LOGGING
# ==============================================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING" if not DEBUG else "DEBUG",  # Show SQL in debug mode
            "propagate": False,
        },
        "users": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ==============================================================================
# DEFAULT AUTO FIELD
# ==============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"