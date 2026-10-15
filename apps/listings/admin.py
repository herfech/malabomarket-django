from django.contrib import admin

from .models import City, Listing, CarDetails, HouseDetails, LandDetails, ListingImage, Favorite


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "region", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = [
        "title", "category", "operation_type", "status", "plan",
        "payment_status", "price", "city", "is_office_listing", "created_at",
    ]
    list_filter = ["category", "status", "plan", "payment_status", "is_office_listing", "city"]
    search_fields = ["title", "description", "contact_name", "contact_phone", "owner__email"]
    inlines = [ListingImageInline]
    autocomplete_fields = ["owner", "city"]


admin.site.register(CarDetails)
admin.site.register(HouseDetails)
admin.site.register(LandDetails)
admin.site.register(Favorite)
