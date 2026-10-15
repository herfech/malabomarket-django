from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.listings.forms import DETAIL_FORM_BY_CATEGORY, ListingForm
from apps.listings.image_processing import process_uploaded_image
from apps.listings.models import Listing, ListingImage

from . import services
from .forms import OfficeClientForm, RegisterPaymentForm
from .models import AuditLog, Payment
from .permissions import admin_required, staff_required

MAX_PHOTOS = 10
CATEGORY_LABELS = dict(Listing.Category.choices)


def _ctx(request, **extra):
    extra["pending_count"] = Payment.objects.filter(status=Payment.Status.PENDIENTE).count()
    return extra


@staff_required
def dashboard(request):
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    pending = Payment.objects.filter(status=Payment.Status.PENDIENTE).select_related("listing")
    collected_today = Payment.objects.filter(status=Payment.Status.PAGADO, paid_at__gte=today).aggregate(
        total=Sum("amount"), n=Count("id"))
    expiring = (
        Listing.objects.filter(status=Listing.Status.ACTIVO, expires_at__gt=now, expires_at__lte=now + timedelta(days=7))
        .select_related("city").order_by("expires_at")[:8]
    )
    return render(request, "office/dashboard.html", _ctx(
        request,
        pending=pending[:8],
        collected_today=collected_today["total"] or 0,
        collected_today_n=collected_today["n"],
        active_count=Listing.objects.public().count(),
        expiring=expiring,
        recent=Listing.objects.filter(is_office_listing=True).select_related("city").order_by("-created_at")[:6],
    ))


@staff_required
def publish_start(request):
    options = [("coche", "Coche", "car"), ("casa", "Casa / Apartamento", "home"), ("terreno", "Terreno", "land")]
    return render(request, "office/publish_start.html", _ctx(request, options=options))


@staff_required
def publish(request, category):
    """Publica un anuncio en nombre de un cliente sin cuenta (Opción 2)."""
    if category not in DETAIL_FORM_BY_CATEGORY:
        raise Http404
    DetailForm = DETAIL_FORM_BY_CATEGORY[category]
    plans = services.active_plans()

    if request.method == "POST":
        listing_form = ListingForm(request.POST)
        detail_form = DetailForm(request.POST)
        client_form = OfficeClientForm(request.POST)
        images = request.FILES.getlist("images")
        plan_code = request.POST.get("plan") or "basico"
        paid_now = request.POST.get("paid_now") == "on"

        error = None
        plan = None
        try:
            plan = services.get_plan(plan_code)
        except services.BusinessError as exc:
            error = str(exc)
        if not images:
            error = error or "Sube al menos una foto."
        elif len(images) > MAX_PHOTOS:
            error = error or f"Máximo {MAX_PHOTOS} fotos."

        if listing_form.is_valid() and detail_form.is_valid() and client_form.is_valid() and not error:
            try:
                processed = [process_uploaded_image(f) for f in images]
            except ValidationError as exc:
                error = exc.message
            else:
                with transaction.atomic():
                    listing = listing_form.save(commit=False)
                    listing.owner = request.user
                    listing.category = category
                    listing.is_office_listing = True
                    listing.contact_name = client_form.cleaned_data["contact_name"]
                    listing.contact_phone = client_form.cleaned_data["contact_phone"]
                    listing.contact_whatsapp = client_form.cleaned_data["contact_whatsapp"] or client_form.cleaned_data["contact_phone"]
                    listing.status = Listing.Status.BORRADOR
                    listing.save()
                    detail = detail_form.save(commit=False)
                    detail.listing = listing
                    detail.save()
                    for pos, img in enumerate(processed):
                        ListingImage.objects.create(listing=listing, image=img, position=pos, is_cover=(pos == 0))

                    services.log(request.user, "anuncio_publicado_en_oficina", listing,
                                 detail=f"cliente {listing.contact_name}, plan {plan.code}")
                    if plan.is_free:
                        services.activate_listing(listing, plan)
                    elif paid_now:
                        payment = services.register_cash_payment(listing, plan, request.user)
                        messages.success(request, f"Anuncio publicado y cobro registrado. Recibo {payment.receipt_number}.")
                        return redirect("office:receipt", pk=payment.pk)
                    else:
                        services.start_listing_with_plan(listing, plan, request.user)
                        messages.success(request, "Anuncio guardado en borrador. Se publicará cuando confirmes el cobro.")
                        return redirect("office:payments")
                messages.success(request, "Anuncio publicado.")
                return redirect("office:listing", pk=listing.pk)

        if error:
            messages.error(request, error)
    else:
        listing_form, detail_form, client_form = ListingForm(), DetailForm(), OfficeClientForm()
        plan_code, paid_now = "basico", True

    return render(request, "office/publish.html", _ctx(
        request, listing_form=listing_form, detail_form=detail_form, client_form=client_form,
        category=category, category_label=CATEGORY_LABELS[category], plans=plans,
        selected_plan=plan_code, paid_now=paid_now, max_photos=MAX_PHOTOS,
    ))


@staff_required
def payments(request):
    status = request.GET.get("estado", "pendiente")
    if status not in dict(Payment.Status.choices):
        status = "pendiente"
    qs = Payment.objects.filter(status=status).select_related("listing", "received_by")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(receipt_number__icontains=q) | Q(listing__title__icontains=q) |
                       Q(listing__contact_name__icontains=q) | Q(listing__owner__email__icontains=q) |
                       Q(listing__owner__full_name__icontains=q))
    page = Paginator(qs.order_by("-created_at"), 25).get_page(request.GET.get("page"))
    return render(request, "office/payments.html", _ctx(request, page=page, status=status, q=q,
                                                       statuses=Payment.Status.choices))


@staff_required
@require_POST
def confirm_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    try:
        payment = services.confirm_payment(payment, request.user, request.POST.get("notes", ""))
    except services.BusinessError as exc:
        messages.error(request, str(exc))
        return redirect("office:payments")
    messages.success(request, f"Cobro confirmado. Recibo {payment.receipt_number}.")
    return redirect("office:receipt", pk=payment.pk)


@admin_required
@require_POST
def void_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    try:
        services.void_payment(payment, request.user, request.POST.get("reason", ""))
        messages.success(request, f"Recibo {payment.receipt_number} anulado y anuncio suspendido.")
    except services.BusinessError as exc:
        messages.error(request, str(exc))
    return redirect("office:receipt", pk=payment.pk)


@staff_required
def receipt(request, pk):
    payment = get_object_or_404(Payment.objects.select_related("listing", "received_by", "voided_by"), pk=pk)
    if payment.status == Payment.Status.PENDIENTE:
        raise Http404  # aún no hay recibo
    return render(request, "office/receipt.html", _ctx(request, payment=payment))


@staff_required
def listings(request):
    qs = Listing.objects.select_related("city", "owner").order_by("-created_at")
    status = request.GET.get("estado", "")
    q = request.GET.get("q", "").strip()
    if status == "expirado":
        qs = qs.filter(Q(status="expirado") | Q(status="activo", expires_at__lte=timezone.now()))
    elif status in dict(Listing.Status.choices):
        qs = qs.filter(status=status)
    if q:
        cond = (Q(title__icontains=q) | Q(contact_name__icontains=q) | Q(contact_phone__icontains=q) |
                Q(owner__email__icontains=q))
        if q.isdigit():
            cond |= Q(pk=int(q))
        qs = qs.filter(cond)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "office/listings.html", _ctx(request, page=page, status=status, q=q,
                                                       statuses=Listing.Status.choices))


@staff_required
def listing_manage(request, pk):
    listing = get_object_or_404(Listing.objects.select_related("city", "owner"), pk=pk)
    plans = services.active_plans()
    form = RegisterPaymentForm(plans, request.POST or None)

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "status":
                services.set_listing_status(listing, request.POST.get("status"), request.user)
                messages.success(request, "Estado actualizado.")
                return redirect("office:listing", pk=pk)
            if action == "renew" and form.is_valid():
                plan = services.get_plan(form.cleaned_data["plan"])
                payment = services.register_cash_payment(listing, plan, request.user, form.cleaned_data["notes"])
                if payment:
                    messages.success(request, f"Cobro registrado. Recibo {payment.receipt_number}.")
                    return redirect("office:receipt", pk=payment.pk)
                messages.success(request, "Anuncio renovado.")
                return redirect("office:listing", pk=pk)
        except services.BusinessError as exc:
            messages.error(request, str(exc))

    return render(request, "office/listing_manage.html", _ctx(
        request, listing=listing, form=form, status_choices=Listing.Status.choices, payments=listing.payments.all(), details=listing.details,
    ))


@admin_required
def audit(request):
    qs = AuditLog.objects.all()
    action = request.GET.get("accion", "")
    if action:
        qs = qs.filter(action=action)
    page = Paginator(qs, 40).get_page(request.GET.get("page"))
    actions = AuditLog.objects.values_list("action", flat=True).distinct().order_by("action")
    return render(request, "office/audit.html", _ctx(request, page=page, actions=actions, action=action))
