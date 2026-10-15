import re
from decimal import Decimal
from urllib.parse import quote

from django import template

register = template.Library()


@register.filter
def xaf(value, currency="XAF"):
    """1500000 -> '1.500.000 XAF'"""
    try:
        number = int(Decimal(value))
    except (TypeError, ValueError, ArithmeticError):
        return value
    return f"{number:,}".replace(",", ".") + f" {currency}"


@register.filter
def price(listing):
    return xaf(listing.price, listing.currency)


@register.filter
def digits(value):
    return re.sub(r"\D", "", value or "")


@register.simple_tag(takes_context=True)
def whatsapp_url(context, listing):
    number = digits(listing.display_whatsapp)
    if not number:
        return ""
    request = context.get("request")
    link = request.build_absolute_uri(listing.get_absolute_url()) if request else ""
    text = f"Hola, me interesa tu anuncio «{listing.title}» en MalaboMarket. {link}"
    return f"https://wa.me/{number}?text={quote(text)}"


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """Mantiene los filtros actuales y cambia/quita los indicados."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"


@register.filter
def xaf_number(value):
    """42000 -> '42.000'"""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return value


@register.simple_tag
def icon(name, css="ic"):
    """Icono del sprite SVG: {% icon 'car' %} o {% icon 'x' 'ic ic-sm' %}"""
    from django.utils.html import format_html
    return format_html('<svg class="{}" aria-hidden="true"><use href="#i-{}"/></svg>', css, name)
