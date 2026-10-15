from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Listing


class StaticSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return ["listings:home", "listings:search"]

    def location(self, item):
        return reverse(item)


class CategorySitemap(StaticSitemap):
    def items(self):
        return ["coches", "casas", "terrenos"]

    def location(self, item):
        return reverse("listings:category", kwargs={"segment": item})


class ListingSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    limit = 5000

    def items(self):
        return Listing.objects.public().order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at
