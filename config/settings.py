"""Read-only settings; installation is an explicit management command."""

from config.environment import BASE_DIR, env
from runtime.installation import read_installation, resolve_data_dir

DATA_DIR = resolve_data_dir()
INSTALLATION = read_installation(DATA_DIR)
SECRET_KEY = env.str("SECRET_KEY", default=INSTALLATION.get("secret_key", ""))
DEBUG = env.bool("DEBUG")
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
INSTALLED_APPS = [
    "django.contrib.contenttypes", "apps.core", "apps.products",
    "apps.measurements", "apps.orders", "apps.printing", "apps.configuration",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "apps.core.context_processors.runtime_mode",
        "apps.core.context_processors.application_identity",
        "apps.orders.context_processors.attendance_layout",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": DATA_DIR / "db.sqlite3",
    "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 5},
}}
LANGUAGE_CODE = "pt-br"
TIME_ZONE = env.str("TIME_ZONE")
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SECURE_CONTENT_TYPE_NOSNIFF = True
CSRF_COOKIE_SAMESITE = "Strict"
X_FRAME_OPTIONS = "DENY"
