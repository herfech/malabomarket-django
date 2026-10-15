import re

from django.conf import settings

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _rgb(hex_color, fallback):
    m = _HEX.match((hex_color or "").strip()) or _HEX.match(fallback)
    h = m.group(1)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _shade(rgb, factor):
    return tuple(max(0, min(255, round(c * factor))) for c in rgb)


def _triplet(rgb):
    return " ".join(str(c) for c in rgb)


def site(request):
    """Marca, colores y ciudades del pie, disponibles en todas las plantillas."""
    from apps.listings.models import City  # import tardío: evita ciclos al arrancar

    primary = _rgb(settings.SITE.get("color_primary"), "#0B3954")
    accent = _rgb(settings.SITE.get("color_accent"), "#F0A91B")
    theme = {
        "primary": _triplet(primary),
        "primary_dark": _triplet(_shade(primary, 0.72)),
        "primary_soft": _triplet(_shade(primary, 1.0)),
        "accent": _triplet(accent),
        "accent_dark": _triplet(_shade(accent, 0.82)),
    }
    return {
        "SITE": settings.SITE,
        "THEME": theme,
        "footer_cities": City.objects.filter(is_active=True)[:6],  # queryset perezoso
    }
