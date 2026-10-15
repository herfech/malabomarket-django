import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from .filters import ListingFilterForm
from .forms import DETAIL_FORM_BY_CATEGORY, ListingForm
from .image_processing import process_uploaded_image
from apps.office import services as office

from .models import City, Favorite, Listing, ListingImage

MAX_PHOTOS = 10
MAX_LISTINGS_PER_DAY = 10
PAGE_SIZE = 12

# Segmento de URL público -> categoría interna
CATEGORY_SLUGS = {"coches": "coche", "casas": "casa", "terrenos": "terreno"}
CATEGORY_TITLES = {"coches": "Coches", "casas": "Casas y Apartamentos", "terrenos": "Terrenos"}


def _favorite_ids(request):
    if request.user.is_authenticated:
        return set(Favorite.objects.filter(user=request.user).values_list("listing_id", flat=True))
    return set()


def home(request):
    public = Listing.objects.public().with_card_data()
    counts = dict(Listing.objects.public().values_list("category").annotate(n=Count("id")))
    return render(request, "listings/home.html", {
        "hero": list(public.filter(images__isnull=False).distinct().order_by("-is_premium", "-created_at")[:3]),
        "featured": public.filter(is_premium=True).order_by("-created_at")[:6],
        "latest": public.order_by("-created_at")[:8],
        "counts": counts,
        "cities": City.objects.filter(is_active=True),
        "favorite_ids": _favorite_ids(request),
    })


def _search(request, category, template, extra=None):
    form = ListingFilterForm(request.GET)
    form.is_valid()
    qs = form.apply(Listing.objects.public().with_card_data(), category)
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    context = {
        "form": form,
        "page": page,
        "total": page.paginator.count,
        "category": category,
        "favorite_ids": _favorite_ids(request),
        "has_filters": any(k != "page" and v for k, v in request.GET.items()),
    }
    context.update(extra or {})
    return render(request, template, context)


def category_list(request, segment):
    category = CATEGORY_SLUGS.get(segment)
    if not category:
        raise Http404
    return _search(request, category, "listings/list.html", {
        "category_label": CATEGORY_TITLES[segment],
        "segment": segment,
    })


def search(request):
    return _search(request, None, "listings/list.html", {"category_label": "Todos los anuncios", "segment": ""})


@login_required
def publish_start(request):
    """Paso previo: elegir qué publicar."""
    options = [("coche", "Coche", "car"), ("casa", "Casa / Apartamento", "home"), ("terreno", "Terreno", "land")]
    return render(request, "listings/publish_start.html", {"options": options})


@login_required
def publish_listing(request, category):
    """
    Publica un anuncio desde la cuenta del usuario. Elige un plan:
    el gratuito se activa al momento; uno de pago queda en borrador
    hasta que la oficina confirme el cobro en efectivo.
    (La publicación en nombre de un cliente sin cuenta está en /oficina/.)
    """
    if category not in DETAIL_FORM_BY_CATEGORY:
        raise Http404("Categoría desconocida")

    DetailFormClass = DETAIL_FORM_BY_CATEGORY[category]
    plans = office.active_plans()

    if request.method == "POST":
        listing_form = ListingForm(request.POST)
        detail_form = DetailFormClass(request.POST)
        images = request.FILES.getlist("images")
        selected_plan = request.POST.get("plan") or "basico"

        image_error = None
        if not request.user.is_office_staff and Listing.objects.filter(
            owner=request.user, created_at__gte=timezone.now() - timedelta(days=1)
        ).count() >= MAX_LISTINGS_PER_DAY:
            image_error = f"Has alcanzado el máximo de {MAX_LISTINGS_PER_DAY} anuncios por día. Inténtalo mañana."
        try:
            plan = office.get_plan(selected_plan)
        except office.BusinessError as exc:
            plan, image_error = None, str(exc)
        if not images:
            image_error = image_error or "Sube al menos una foto."
        elif len(images) > MAX_PHOTOS:
            image_error = image_error or f"Puedes subir un máximo de {MAX_PHOTOS} fotos."

        if listing_form.is_valid() and detail_form.is_valid() and not image_error:
            try:
                processed_images = [process_uploaded_image(f) for f in images]
            except ValidationError as exc:
                image_error = exc.message
            else:
                with transaction.atomic():
                    listing = listing_form.save(commit=False)
                    listing.owner = request.user
                    listing.category = category
                    listing.status = Listing.Status.BORRADOR  # se activa según el plan
                    listing.save()

                    detail = detail_form.save(commit=False)
                    detail.listing = listing
                    detail.save()

                    for position, processed in enumerate(processed_images):
                        ListingImage.objects.create(
                            listing=listing, image=processed, position=position, is_cover=(position == 0)
                        )
                    pending = office.start_listing_with_plan(listing, plan, request.user)

                if pending:
                    messages.success(
                        request,
                        f"Anuncio guardado. Para activarlo, paga {int(pending.amount):,} XAF en nuestra oficina".replace(",", ".")
                        + " y lo publicamos en cuanto se confirme el cobro.",
                    )
                else:
                    messages.success(request, "Tu anuncio fue publicado correctamente.")
                return redirect("listings:my_listings")

        if image_error:
            messages.error(request, image_error)
    else:
        listing_form = ListingForm()
        detail_form = DetailFormClass()
        selected_plan = "basico"

    return render(
        request,
        "listings/publish.html",
        {
            "listing_form": listing_form,
            "detail_form": detail_form,
            "category": category,
            "category_label": dict(Listing.Category.choices)[category],
            "max_photos": MAX_PHOTOS,
            "plans": plans,
            "selected_plan": selected_plan,
        },
    )


@login_required
def my_listings(request):
    listings = request.user.listings.select_related("city").prefetch_related("images").order_by("-created_at")
    return render(request, "listings/my_listings.html", {"listings": listings})


@login_required
def delete_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk)

    # Solo el dueño, o personal de oficina/administrador, puede eliminar.
    if listing.owner_id != request.user.id and not request.user.is_office_staff:
        raise Http404  # no revelamos que el anuncio existe a quien no tiene permiso

    if request.method == "POST":
        listing.delete()
        messages.success(request, "Anuncio eliminado.")
        return redirect("listings:my_listings")

    return render(request, "listings/delete_confirm.html", {"listing": listing})


def listing_detail(request, pk, slug=None):
    listing = get_object_or_404(Listing.objects.with_card_data(), pk=pk)
    user = request.user
    can_see_hidden = user.is_authenticated and (listing.owner_id == user.id or user.is_office_staff)
    if not listing.is_publicly_visible and not can_see_hidden:
        raise Http404

    # URL canónica (SEO): si el slug no coincide, redirigimos.
    if slug != listing.slug:
        return redirect(listing, permanent=True)

    if not can_see_hidden:
        Listing.objects.filter(pk=pk).update(views_count=F("views_count") + 1)

    related = (
        Listing.objects.public().with_card_data()
        .filter(category=listing.category, city=listing.city).exclude(pk=pk)
        .order_by("-is_premium", "-created_at")[:4]
    )
    cover = listing.cover_image
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": listing.title,
        "description": listing.description[:300],
        "offers": {"@type": "Offer", "price": str(int(listing.price)), "priceCurrency": listing.currency},
    }
    if cover:
        json_ld["image"] = request.build_absolute_uri(cover.image.url)
    map_bbox = ""
    if listing.latitude is not None and listing.longitude is not None:
        lat, lng, d = listing.latitude, listing.longitude, 0.01
        map_bbox = f"{lng - d}%2C{lat - d}%2C{lng + d}%2C{lat + d}"
    return render(request, "listings/detail.html", {
        "map_bbox": map_bbox,
        "json_ld": mark_safe(json.dumps(json_ld, ensure_ascii=False).replace("<", "\\u003c")),
        "listing": listing,
        "images": list(listing.images.all()),
        "image_urls": [i.image.url for i in listing.images.all()],
        "details": listing.details,
        "related": related,
        "favorite_ids": _favorite_ids(request),
        "is_favorite": listing.pk in _favorite_ids(request),
        "is_hidden": not listing.is_publicly_visible,
    })


@login_required
@require_POST
def toggle_favorite(request, pk):
    listing = get_object_or_404(Listing.objects.public(), pk=pk)
    fav, created = Favorite.objects.get_or_create(user=request.user, listing=listing)
    if not created:
        fav.delete()
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = listing.get_absolute_url()
    return redirect(target)


@login_required
def favorites(request):
    qs = Listing.objects.public().with_card_data().filter(favorited_by__user=request.user).order_by("-favorited_by__created_at")
    return render(request, "listings/favorites.html", {
        "listings": qs, "favorite_ids": {l.pk for l in qs},
    })
