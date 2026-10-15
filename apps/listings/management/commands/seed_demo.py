from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.listings.models import CarDetails, City, HouseDetails, LandDetails, Listing


class Command(BaseCommand):
    help = "Crea ciudades y anuncios de ejemplo (solo para desarrollo/demos)."

    def handle(self, *args, **opts):
        cities = {n: City.objects.get_or_create(name=n)[0] for n in ["Malabo", "Bata", "Ebibeyín", "Mongomo", "Luba"]}
        user, _ = User.objects.get_or_create(
            email="demo@malabomarket.test",
            defaults={"full_name": "Vendedor Demo", "phone": "240222000111", "whatsapp_number": "240222000111"},
        )
        if not user.has_usable_password():
            user.set_password("demo-1234-demo")
            user.save()
        if Listing.objects.filter(owner=user).exists():
            self.stdout.write("Los datos demo ya existen.")
            return

        def mk(category, title, price, city, op="venta", premium=False, zone=""):
            return Listing.objects.create(
                owner=user, category=category, operation_type=op, title=title, price=Decimal(price),
                city=cities[city], address_zone=zone, is_premium=premium,
                description="Anuncio de demostración generado automáticamente.",
            )

        l = mk("coche", "Toyota Land Cruiser Prado 2019", 18500000, "Malabo", premium=True)
        CarDetails.objects.create(listing=l, brand="Toyota", model="Prado", year=2019, mileage_km=42000, fuel_type="diesel", transmission="automatico")
        l = mk("coche", "Hyundai Tucson 2016", 7200000, "Bata")
        CarDetails.objects.create(listing=l, brand="Hyundai", model="Tucson", year=2016, mileage_km=88000, fuel_type="gasolina", transmission="automatico")
        l = mk("casa", "Apartamento 3 hab. en Malabo II", 450000, "Malabo", op="alquiler", zone="Malabo II", premium=True)
        HouseDetails.objects.create(listing=l, property_type="apartamento", bedrooms=3, bathrooms=2, area_m2=120, has_parking=True)
        l = mk("casa", "Casa familiar en Bata", 65000000, "Bata", zone="Ela Nguema")
        HouseDetails.objects.create(listing=l, property_type="casa", bedrooms=5, bathrooms=3, area_m2=260, has_garden=True)
        l = mk("terreno", "Solar de 600 m² con título", 22000000, "Luba")
        LandDetails.objects.create(listing=l, area_m2=600, land_use="urbano", has_title_deed=True, is_fenced=True)
        self.stdout.write(self.style.SUCCESS("Datos demo creados (usuario demo@malabomarket.test)."))
