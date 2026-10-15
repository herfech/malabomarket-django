"""
Reglas de negocio de planes, cobros y caducidad. Toda la lógica que cambia
dinero o visibilidad vive aquí (no en las vistas), para poder probarla
y para que el panel de oficina, el admin y los comandos hagan lo mismo.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.listings.models import Listing

from .models import AuditLog, Payment, PlanConfig, ReceiptSequence


class BusinessError(Exception):
    """Error de regla de negocio con mensaje apto para mostrar al usuario."""


def active_plans():
    return list(PlanConfig.objects.filter(is_active=True).order_by("price"))


def get_plan(code):
    try:
        return PlanConfig.objects.get(code=code, is_active=True)
    except PlanConfig.DoesNotExist:
        raise BusinessError("El plan elegido no está disponible.")


def log(user, action, listing=None, payment=None, detail=""):
    AuditLog.objects.create(
        user=user if getattr(user, "pk", None) else None,
        user_label=getattr(user, "email", "") or "sistema",
        action=action,
        listing_id_ref=getattr(listing, "pk", None),
        payment_id_ref=getattr(payment, "pk", None),
        detail=detail[:300],
    )


def next_receipt_number(now=None):
    """R-2026-000001. Se llama dentro de una transacción; bloquea la fila del año."""
    year = (now or timezone.now()).year
    seq, _ = ReceiptSequence.objects.select_for_update().get_or_create(year=year)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"R-{year}-{seq.last_number:06d}"


def activate_listing(listing, plan, now=None):
    """Deja el anuncio visible según el plan: fecha de caducidad y destacado."""
    now = now or timezone.now()
    expires = now + timedelta(days=plan.duration_days)
    listing.plan = plan.code
    listing.status = Listing.Status.ACTIVO
    listing.expires_at = expires
    listing.is_premium = plan.is_featured
    listing.premium_until = expires if plan.is_featured else None
    listing.payment_status = Listing.PaymentStatus.NO_APLICA if plan.is_free else Listing.PaymentStatus.PAGADO
    listing.save()


def _snapshot(listing, plan, method):
    return Payment(
        listing=listing, plan_code=plan.code, plan_name=plan.name, duration_days=plan.duration_days,
        amount=plan.price, method=method,
    )


@transaction.atomic
def start_listing_with_plan(listing, plan, by_user=None):
    """
    Plan elegido al publicar desde una cuenta de cliente.
    - Gratis: se activa al momento.
    - De pago: queda en borrador con un pago pendiente que la oficina confirmará.
    Devuelve el Payment pendiente o None.
    """
    if plan.is_free:
        activate_listing(listing, plan)
        log(by_user, "anuncio_publicado", listing, detail=f"plan {plan.code}")
        return None
    listing.plan = plan.code
    listing.status = Listing.Status.BORRADOR
    listing.payment_status = Listing.PaymentStatus.PENDIENTE
    listing.is_premium = False
    listing.save()
    payment = _snapshot(listing, plan, Payment.Method.EFECTIVO)
    payment.save()
    log(by_user, "pago_pendiente_creado", listing, payment, f"plan {plan.code}, {plan.price} XAF")
    return payment


@transaction.atomic
def confirm_payment(payment, by_user, notes=""):
    """La oficina confirma que cobró en efectivo: recibo numerado + anuncio activo."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status != Payment.Status.PENDIENTE:
        raise BusinessError("Este pago ya no está pendiente.")
    now = timezone.now()
    payment.status = Payment.Status.PAGADO
    payment.receipt_number = next_receipt_number(now)
    payment.paid_at = now
    payment.received_by = by_user
    if notes:
        payment.notes = notes[:200]
    payment.save()
    plan = PlanConfig.objects.filter(code=payment.plan_code).first()
    if plan is None:  # el plan pudo borrarse: usamos lo guardado en el pago
        plan = PlanConfig(code=payment.plan_code, name=payment.plan_name, duration_days=payment.duration_days,
                          price=payment.amount, is_featured=payment.plan_code != "basico")
    activate_listing(payment.listing, plan, now)
    log(by_user, "pago_confirmado", payment.listing, payment, f"{payment.receipt_number}, {payment.amount} XAF")
    return payment


@transaction.atomic
def register_cash_payment(listing, plan, by_user, notes=""):
    """Cobro directo en oficina (sin pasar por pendiente) para un anuncio ya creado."""
    if plan.is_free:
        activate_listing(listing, plan)
        log(by_user, "anuncio_renovado", listing, detail=f"plan {plan.code} (gratis)")
        return None
    payment = _snapshot(listing, plan, Payment.Method.EFECTIVO)
    payment.save()
    return confirm_payment(payment, by_user, notes)


@transaction.atomic
def void_payment(payment, by_user, reason):
    """Anula un cobro (solo administrador). El nº de recibo no se reutiliza; el anuncio se suspende."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status != Payment.Status.PAGADO:
        raise BusinessError("Solo se puede anular un pago cobrado.")
    if not reason.strip():
        raise BusinessError("Indica el motivo de la anulación.")
    payment.status = Payment.Status.ANULADO
    payment.voided_at = timezone.now()
    payment.voided_by = by_user
    payment.void_reason = reason.strip()[:200]
    payment.save()
    listing = payment.listing
    listing.status = Listing.Status.SUSPENDIDO
    listing.is_premium = False
    listing.premium_until = None
    listing.payment_status = Listing.PaymentStatus.PENDIENTE
    listing.save()
    log(by_user, "pago_anulado", listing, payment, f"{payment.receipt_number}: {payment.void_reason}")
    return payment


def set_listing_status(listing, status, by_user):
    allowed = {Listing.Status.ACTIVO, Listing.Status.SUSPENDIDO, Listing.Status.VENDIDO, Listing.Status.ALQUILADO}
    if status not in allowed:
        raise BusinessError("Estado no permitido.")
    if status == Listing.Status.ACTIVO and listing.payment_status == Listing.PaymentStatus.PENDIENTE:
        raise BusinessError("No se puede activar: tiene un pago pendiente.")
    old = listing.status
    listing.status = status
    listing.save(update_fields=["status", "updated_at"])
    log(by_user, "estado_cambiado", listing, detail=f"{old} -> {status}")


def expire_due_listings(now=None):
    """Marca como expirados los anuncios vencidos y les quita el destacado. Devuelve cuántos."""
    now = now or timezone.now()
    qs = Listing.objects.filter(status=Listing.Status.ACTIVO, expires_at__isnull=False, expires_at__lte=now)
    ids = list(qs.values_list("pk", flat=True))
    if ids:
        Listing.objects.filter(pk__in=ids).update(status=Listing.Status.EXPIRADO, is_premium=False, premium_until=None)
        for pk in ids:
            AuditLog.objects.create(user=None, user_label="sistema", action="anuncio_expirado", listing_id_ref=pk)
    return len(ids)
