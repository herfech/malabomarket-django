from django.db import models


class TimeStampedModel(models.Model):
    """
    Modelo base abstracto: añade created_at/updated_at a cualquier modelo
    que lo herede, sin duplicar los dos campos en cada app.
    """

    created_at = models.DateTimeField("creado el", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        abstract = True
