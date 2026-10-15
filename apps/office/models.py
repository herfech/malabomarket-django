from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class PlanConfig(models.Model):
    """
    Precio y duración de cada plan. Es una tabla (no constantes) para que
    cada comprador del software ponga sus propios precios desde el admin.
    El código del plan es el mismo que usa Listing.plan.
    """

    code = models.CharField(_("código"), max_length=10, unique=True, choices=[
        ("basico", _("Básico")), ("destacado", _("Destacado")), ("premium", _("Premium")),
    ])
    name = models.CharField(_("nombre"), max_length=40)
    description = models.CharField(_("descripción"), max_length=160, blank=True)
    price = models.DecimalField(_("precio"), max_digits=12, decimal_places=2, default=0)
    duration_days = models.PositiveSmallIntegerField(_("duración (días)"), default=30)
    is_featured = models.BooleanField(
        _("destaca el anuncio"), default=False,
        help_text=_("Los anuncios con este plan salen primero en los listados."),
    )
    is_active = models.BooleanField(_("activo"), default=True)

    class Meta:
        verbose_name = _("plan")
        verbose_name_plural = _("planes")
        ordering = ["price"]

    def __str__(self):
        return self.name

    @property
    def is_free(self):
        return self.price <= 0


class ReceiptSequence(models.Model):
    """Contador de recibos por año: garantiza numeración correlativa sin saltos ni repeticiones."""

    year = models.PositiveSmallIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.year}: {self.last_number}"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        EFECTIVO = "efectivo", _("Efectivo")
        TARJETA = "tarjeta", _("Tarjeta")

    class Status(models.TextChoices):
        PENDIENTE = "pendiente", _("Pendiente")
        PAGADO = "pagado", _("Pagado")
        ANULADO = "anulado", _("Anulado")

    listing = models.ForeignKey("listings.Listing", verbose_name=_("anuncio"), on_delete=models.PROTECT, related_name="payments")
    plan_code = models.CharField(_("plan"), max_length=10)
    plan_name = models.CharField(_("nombre del plan"), max_length=40)
    duration_days = models.PositiveSmallIntegerField(_("duración (días)"))
    amount = models.DecimalField(_("importe"), max_digits=12, decimal_places=2)
    currency = models.CharField(_("moneda"), max_length=8, default="XAF")
    method = models.CharField(_("método"), max_length=10, choices=Method.choices, default=Method.EFECTIVO)
    status = models.CharField(_("estado"), max_length=10, choices=Status.choices, default=Status.PENDIENTE)

    receipt_number = models.CharField(_("nº de recibo"), max_length=20, unique=True, null=True, blank=True)
    paid_at = models.DateTimeField(_("cobrado el"), null=True, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("cobrado por"), null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payments_received",
    )
    voided_at = models.DateTimeField(_("anulado el"), null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("anulado por"), null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payments_voided",
    )
    void_reason = models.CharField(_("motivo de anulación"), max_length=200, blank=True)
    notes = models.CharField(_("notas"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("pago")
        verbose_name_plural = _("pagos")
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(check=models.Q(amount__gte=0), name="payment_amount_gte_0")]

    def __str__(self):
        return self.receipt_number or f"Pago #{self.pk} (pendiente)"

    @property
    def client_name(self):
        return self.listing.display_contact_name


class AuditLog(models.Model):
    """Registro de acciones sensibles. Solo se escribe desde el código, nunca se edita."""

    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries")
    user_label = models.CharField(max_length=254, blank=True)  # se conserva aunque se borre el usuario
    action = models.CharField(max_length=40)
    listing_id_ref = models.PositiveIntegerField(null=True, blank=True)
    payment_id_ref = models.PositiveIntegerField(null=True, blank=True)
    detail = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registro de auditoría"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.user_label} {self.action}"
