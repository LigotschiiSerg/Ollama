import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'LOCAL-DEVELOPMENT-ONLY-CHANGE-ME')
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = [x.strip() for x in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if x.strip()]
INSTALLED_APPS = ['django.contrib.messages', 'django.contrib.staticfiles', 'documents']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.debug','django.template.context_processors.request','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3','OPTIONS':{'timeout':30}}}
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Chisinau'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
MEDIA_ROOT = BASE_DIR/'media'
MEDIA_URL = 'media/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
OLLAMA_URL = os.getenv('OLLAMA_URL','http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL','qwen3-vl:4b')
PDF_MAX_BYTES = 20 * 1024 * 1024
PDF_MAX_PAGES = int(os.getenv('PDF_MAX_PAGES','50'))
# Downloading remote URLs is disabled unless hostnames are explicitly authorized.
PDF_ALLOWED_HOSTS = [x.strip().lower() for x in os.getenv('PDF_ALLOWED_HOSTS','').split(',') if x.strip()]
DATA_UPLOAD_MAX_MEMORY_SIZE = PDF_MAX_BYTES + 1024 * 1024
MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'
CSRF_COOKIE_HTTPONLY = True

# Performance controls; page-level model calls remain expensive without GPU.
OLLAMA_TIMEOUT = int(os.getenv('OLLAMA_TIMEOUT', '180'))
OLLAMA_MAX_TOKENS = int(os.getenv('OLLAMA_MAX_TOKENS', '2500'))
PDF_VISION_DPI = int(os.getenv('PDF_VISION_DPI', '110'))
PDF_NATIVE_MIN_CHARS = int(os.getenv('PDF_NATIVE_MIN_CHARS', '120'))
PDF_FORCE_VISION = os.getenv('PDF_FORCE_VISION', '0') == '1'

# docling: table structure + merged cells; ollama: legacy fallback on request only
PDF_ENGINE = os.getenv("PDF_ENGINE", "docling").strip().lower()
