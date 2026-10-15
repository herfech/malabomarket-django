from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Si corre con Docker Compose, DATABASE_URL apunta al Postgres del propio
# compose (mismo motor que producción). Si corres "python manage.py runserver"
# directo sin Docker, no existe esa variable y cae en SQLite, cero configuración.
if env("DATABASE_URL", default=None):  # noqa: F405
    DATABASES = {"default": env.db("DATABASE_URL")}  # noqa: F405
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }

# En desarrollo, las fotos se guardan en disco local, no en S3/R2.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"  # noqa: F405
STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # los emails se imprimen en la terminal
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}  # noqa: F405 — sin manifiesto: no hace falta collectstatic en desarrollo
