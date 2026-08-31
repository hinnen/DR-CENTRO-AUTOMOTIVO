"""Configurações do projeto DR Centro Automotivo."""

from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("SECRET_KEY", "")
DEBUG = env_bool("DEBUG", False)

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-somente-para-desenvolvimento-local"
    else:
        raise RuntimeError("SECRET_KEY é obrigatória quando DEBUG=False.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")


# Aplicações

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.customers",
    "apps.vehicles",
    "apps.workorders",
    "apps.dashboard",
    "apps.mobile",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "apps.core.middleware.HealthCheckMiddleware",
    "apps.core.middleware.SocialPreviewMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.workshop",
                "apps.core.context_processors.whatsapp_auto_open",
                "apps.core.context_processors.brand_share",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Banco de dados — PostgreSQL em produção.
# DATABASE_URL define o destino; o fallback sqlite existe apenas para
# permitir subir o projeto antes do Postgres estar disponível na máquina.

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"


# Internacionalização

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "d/m/Y H:i"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
DATE_INPUT_FORMATS = ["%d/%m/%Y", "%Y-%m-%d"]
DATETIME_INPUT_FORMATS = ["%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]
USE_THOUSAND_SEPARATOR = True


# Arquivos estáticos e mídia

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))

# O manifesto com hash só existe depois do collectstatic, por isso é
# habilitado explicitamente no deploy e fica desligado em dev e testes.
USE_MANIFEST_STATIC = env_bool("USE_MANIFEST_STATIC", False)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if USE_MANIFEST_STATIC
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

# Limites de upload de fotos (validados também nos forms).
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ALLOWED_IMAGE_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"]


# Segurança

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # HTMX lê o token do cookie quando necessário.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    # Health check interno do Render usa HTTP sem X-Forwarded-Proto — sem isenção o deploy falha.
    SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    if env_bool("USE_X_FORWARDED_PROTO", True):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# E-mail ainda não é usado por nenhuma funcionalidade; a configuração existe
# para que o checklist de deploy passe e o envio funcione quando for preciso.
if DEBUG:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
else:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": os.getenv("EMAIL_HOST", "localhost"),
                "port": int(os.getenv("EMAIL_PORT", "587")),
                "username": os.getenv("EMAIL_HOST_USER", ""),
                "password": os.getenv("EMAIL_HOST_PASSWORD", ""),
                "use_tls": env_bool("EMAIL_USE_TLS", True),
            },
        }
    }

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "nao-responda@localhost")

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"


# Identidade da oficina (exibida no layout)

WORKSHOP_NAME = os.getenv("WORKSHOP_NAME", "DR Centro Automotivo")
# URL pública canônica (WhatsApp/OG). Preferir o domínio .com da oficina.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
OG_IMAGE_VERSION = os.getenv("OG_IMAGE_VERSION", "3")

# OCR de placa (platerec/ONNX). No Starter: ligado sob demanda, sem warmup no boot.
ENABLE_PLATE_OCR = env_bool("ENABLE_PLATE_OCR", DEBUG)
PLATE_OCR_WARMUP = env_bool("PLATE_OCR_WARMUP", False)
# Mantém modelo após 1ª foto (muito mais rápido). Desligar só se memória apertar.
PLATE_OCR_KEEP_LOADED = env_bool("PLATE_OCR_KEEP_LOADED", True)
PLATE_OCR_MAX_SIDE = int(os.getenv("PLATE_OCR_MAX_SIDE", "800"))
PLATE_OCR_THREADS = int(os.getenv("PLATE_OCR_THREADS", "2"))


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "oficina": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO"), "propagate": False},
    },
}
