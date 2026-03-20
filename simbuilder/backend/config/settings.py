"""Django settings optimized for node editor with WebSocket support."""
import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=True)

print(DEBUG)

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']
ROOT_URLCONF = 'backend.config.urls'

INTERNAL_IPS = (
    '127.0.0.1',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
            ],
            "debug": DEBUG,
        },
    },
]

INSTALLED_APPS = [
    'daphne',  # Must be first for WebSocket support
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    "django_vite_hmr",
    'corsheaders',
    'pwa',
    'channels',
    'backend.node_editor',
    'backend.plugins',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ASGI_APPLICATION = 'backend.config.asgi.application'
WSGI_APPLICATION = 'backend.config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

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
# CORS settings for React development server
# Enable CORS for development
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]

# Channels configuration - Disabled for now to fix connection issues
# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels_redis.core.RedisChannelLayer',
#         'CONFIG': {
#             'hosts': [('127.0.0.1', 6379)],
#         },
#     },
# }

# Use in-memory channel layer for development without Redis
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    },
}

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
}

# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files configuration
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "backend" / "collectedstatic"

DJANGO_VITE_ASSETS_PATH = BASE_DIR / "static" / "assets"
DJANGO_VITE_DEV_MODE = config("DJANGO_VITE_DEV_MODE", default=True)
DJANGO_VITE_DEV_SERVER_PORT = config("DJANGO_VITE_DEV_SERVER_PORT", default="5173")

VITE_APP_DIR = os.path.join(BASE_DIR, "frontend")


DJANGO_VITE = {
    "debug": DEBUG, # This will define which mode to serve static file.
    "HOST": "localhost", # This is the hostname of Vite Development Server
    "PORT": 5173, # This is the port of Vite Development Server
    "BASE": VITE_APP_DIR # This is the BASE of Vite Server
}


# Add the build.outDir from vite.config.js to STATICFILES_DIRS
# so that collectstatic can collect your compiled vite assets.
STATICFILES_DIRS = [
    DJANGO_VITE_ASSETS_PATH,
    BASE_DIR / "static"
]

# Vite configuration
VITE_DEV_SERVER_HOST = config("HOST", default="127.0.0.1")

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
