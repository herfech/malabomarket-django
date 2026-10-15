from django.db import connection
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from apps.listings.sitemaps import CategorySitemap, ListingSitemap, StaticSitemap

SITEMAPS = {"static": StaticSitemap, "categorias": CategorySitemap, "anuncios": ListingSitemap}

def health(request):
    """Para Render y para vigilancia externa: responde 200 solo si la base de datos contesta."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        return HttpResponse("db error", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("salud/", health, name="health"),
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("cuenta/", include("apps.accounts.urls")),
    path("oficina/", include("apps.office.urls")),
    path("", include("apps.listings.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
