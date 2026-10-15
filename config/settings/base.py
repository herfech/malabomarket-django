"""
Configuración base — todo lo que NO cambia entre desarrollo y producción.
Nunca se ejecuta directamente; dev.py y production.py la heredan con `from .base import *`.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# En desarrollo lee variables desde un archivo .env en la raíz del proyecto.
# En producción (Render), las variables ya vienen inyectadas por la
# plataforma — el .env simplemente no existe ahí y esta línea no hace nada.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    # Apps propias
    "apps.core",
    "apps.accounts",
    "apps.listings",
    "apps.office",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # sirve los estáticos sin depender de Nginx
    "django.contrib.sessions.middleware.SessionMiddleware",
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
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

# --- Contraseñas ---
# Argon2 primero: es el algoritmo recomendado hoy (ganador del Password
# Hashing Competition). Los demás quedan como fallback para verificar
# contraseñas antiguas si alguna vez se migran datos de otro sistema.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "Africa/Malabo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "listings:home"
LOGOUT_REDIRECT_URL = "listings:home"


# --- Marca y contacto (marca blanca): cada comprador lo cambia en su .env ---
SITE = {
    "name_first": env("SITE_NAME_FIRST", default="Malabo"),
    "name_second": env("SITE_NAME_SECOND", default="Market"),
    "phone": env("SITE_PHONE", default="+240 222 000 000"),
    "whatsapp": env("SITE_WHATSAPP", default="240222000000"),  # internacional, sin '+'
    "email": env("SITE_EMAIL", default="hola@malabomarket.com"),
    "location": env("SITE_LOCATION", default="Malabo, Guinea Ecuatorial"),
    "tagline": env("SITE_TAGLINE", default="Malabo · Bata · Guinea Ecuatorial"),
    # Colores de marca (hex). Cada comprador puede poner los suyos.
    "color_primary": env("SITE_COLOR_PRIMARY", default="#0B3954"),
    "color_accent": env("SITE_COLOR_ACCENT", default="#F0A91B"),
}

# Pasarela de tarjeta (opcional). Vacío = solo efectivo en oficina. Ver apps/office/gateway.py
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", default="")
