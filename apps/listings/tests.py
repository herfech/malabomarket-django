from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from .models import CarDetails, City, Favorite, HouseDetails, LandDetails, Listing


class ListingModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.city = City.objects.create(name="Malabo", region="Isla de Bioko")
        cls.owner = User.objects.create_user(email="dueno@example.com", password="unaClaveSegura123")
        cls.staff = User.objects.create_user(
            email="oficina@example.com", password="unaClaveSegura123", role=User.Role.PERSONAL_OFICINA
        )

    def _base_listing(self, **overrides):
        data = dict(
            owner=self.owner,
            category=Listing.Category.COCHE,
            operation_type=Listing.OperationType.VENTA,
            title="Toyota Land Cruiser Prado 2019",
            price=Decimal("18500000"),
            city=self.city,
        )
        data.update(overrides)
        return Listing.objects.create(**data)

    def test_crear_anuncio_normal_con_detalle_de_coche(self):
        listing = self._base_listing()
        CarDetails.objects.create(
            listing=listing, brand="Toyota", model="Land Cruiser Prado", year=2019,
            mileage_km=42000, fuel_type=CarDetails.FuelType.DIESEL,
            transmission=CarDetails.Transmission.AUTOMATICO,
        )
        self.assertEqual(listing.car_details.brand, "Toyota")
        self.assertEqual(listing.status, Listing.Status.ACTIVO)  # default
        self.assertEqual(listing.plan, Listing.Plan.BASICO)  # default

    def test_precio_negativo_viola_la_restriccion_de_base_de_datos(self):
        with self.assertRaises(IntegrityError):
            self._base_listing(price=Decimal("-100"))

    def test_anuncio_normal_muestra_contacto_del_dueno(self):
        """Sin is_office_listing, el contacto público es el del dueño de la cuenta."""
        self.owner.full_name = "Juan Nsue"
        self.owner.whatsapp_number = "240222111111"
        self.owner.save()
        listing = self._base_listing()
        self.assertEqual(listing.display_contact_name, "Juan Nsue")
        self.assertEqual(listing.display_whatsapp, "240222111111")

    def test_opcion_2_anuncio_de_oficina_muestra_contacto_del_cliente_no_del_empleado(self):
        """El técnico (staff) es el owner técnico, pero el público ve al cliente real."""
        listing = self._base_listing(
            owner=self.staff,
            is_office_listing=True,
            contact_name="María Ondo",
            contact_phone="+240333222111",
            contact_whatsapp="240333222111",
        )
        self.assertEqual(listing.display_contact_name, "María Ondo")
        self.assertEqual(listing.display_whatsapp, "240333222111")
        self.assertNotEqual(listing.display_contact_name, self.staff.full_name)

    def test_casa_requiere_su_propio_detalle_no_el_de_coche(self):
        listing = self._base_listing(category=Listing.Category.CASA, title="Casa de 4 habitaciones")
        HouseDetails.objects.create(
            listing=listing, property_type=HouseDetails.PropertyType.CASA,
            bedrooms=4, bathrooms=3, area_m2=Decimal("220.00"),
        )
        self.assertEqual(listing.house_details.bedrooms, 4)
        with self.assertRaises(Listing.car_details.RelatedObjectDoesNotExist):
            listing.car_details

    def test_terreno_area_debe_ser_positiva(self):
        listing = self._base_listing(category=Listing.Category.TERRENO, title="Terreno urbano de 800 m2")
        with self.assertRaises(ValidationError):
            land = LandDetails(listing=listing, area_m2=Decimal("0"), land_use=LandDetails.LandUse.URBANO)
            land.full_clean()

    def test_favorito_no_se_puede_duplicar_para_el_mismo_usuario(self):
        listing = self._base_listing()
        Favorite.objects.create(user=self.owner, listing=listing)
        with self.assertRaises(IntegrityError):
            Favorite.objects.create(user=self.owner, listing=listing)


# ---------------------------------------------------------------------
# Helpers para generar una imagen real en memoria (no un archivo falso)
# ---------------------------------------------------------------------
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from PIL import Image

from .image_processing import process_uploaded_image


def make_test_image(name="foto.jpg", size=(50, 50), fmt="JPEG"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color="blue").save(buffer, format=fmt)
    buffer.seek(0)
    content_type = "image/jpeg" if fmt == "JPEG" else f"image/{fmt.lower()}"
    return SimpleUploadedFile(name, buffer.read(), content_type=content_type)


class ImageProcessingTests(TestCase):
    def test_imagen_valida_se_procesa_y_queda_como_jpeg(self):
        result = process_uploaded_image(make_test_image())
        self.assertTrue(result.name.endswith(".jpg"))

    def test_archivo_que_no_es_imagen_se_rechaza(self):
        fake = SimpleUploadedFile("no-es-foto.txt", b"esto no es una imagen", content_type="text/plain")
        with self.assertRaises(ValidationError):
            process_uploaded_image(fake)

    def test_imagen_demasiado_pesada_se_rechaza(self):
        big = make_test_image()
        big.size = 9 * 1024 * 1024  # simula 9 MB sin generar el archivo real
        with self.assertRaises(ValidationError):
            process_uploaded_image(big)


class PublishListingViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.city = City.objects.create(name="Bata")
        cls.user = User.objects.create_user(email="ana@example.com", password="unaClaveSegura123")
        cls.other_user = User.objects.create_user(email="otro@example.com", password="unaClaveSegura123")

    def setUp(self):
        self.client = Client()

    def test_usuario_no_logueado_no_puede_publicar(self):
        response = self.client.get(reverse("listings:publish", args=["coche"]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_publicar_coche_completo_con_foto_crea_todo_correctamente(self):
        self.client.login(email="ana@example.com", password="unaClaveSegura123")

        response = self.client.post(
            reverse("listings:publish", args=["coche"]),
            data={
                "operation_type": Listing.OperationType.VENTA,
                "title": "Toyota Hilux 2020",
                "description": "Buen estado",
                "price": "15000000",
                "city": self.city.id,
                "address_zone": "Centro",
                "brand": "Toyota",
                "model": "Hilux",
                "year": 2020,
                "mileage_km": 30000,
                "fuel_type": CarDetails.FuelType.DIESEL,
                "transmission": CarDetails.Transmission.MANUAL,
                "condition": CarDetails.Condition.USADO,
                "images": [make_test_image()],
            },
        )

        self.assertEqual(response.status_code, 302)  # redirige tras publicar con éxito
        listing = Listing.objects.get(title="Toyota Hilux 2020")
        self.assertEqual(listing.owner, self.user)
        self.assertEqual(listing.category, Listing.Category.COCHE)
        self.assertEqual(listing.car_details.brand, "Toyota")
        self.assertEqual(listing.images.count(), 1)
        self.assertTrue(listing.images.first().is_cover)

    def test_publicar_sin_ninguna_foto_no_crea_el_anuncio(self):
        self.client.login(email="ana@example.com", password="unaClaveSegura123")
        self.client.post(
            reverse("listings:publish", args=["coche"]),
            data={
                "operation_type": Listing.OperationType.VENTA,
                "title": "Coche sin fotos",
                "price": "1000000",
                "city": self.city.id,
                "brand": "Kia", "model": "Rio", "year": 2018, "mileage_km": 50000,
                "fuel_type": CarDetails.FuelType.GASOLINA,
                "transmission": CarDetails.Transmission.MANUAL,
                "condition": CarDetails.Condition.USADO,
            },
        )
        self.assertFalse(Listing.objects.filter(title="Coche sin fotos").exists())

    def test_categoria_invalida_en_la_url_da_404(self):
        self.client.login(email="ana@example.com", password="unaClaveSegura123")
        response = self.client.get(reverse("listings:publish", args=["barco"]))
        self.assertEqual(response.status_code, 404)

    def test_un_usuario_no_puede_eliminar_el_anuncio_de_otro(self):
        listing = Listing.objects.create(
            owner=self.other_user, category=Listing.Category.COCHE,
            operation_type=Listing.OperationType.VENTA, title="Anuncio ajeno",
            price=1000, city=self.city,
        )
        self.client.login(email="ana@example.com", password="unaClaveSegura123")
        response = self.client.post(reverse("listings:delete", args=[listing.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Listing.objects.filter(pk=listing.pk).exists())

    def test_el_dueno_si_puede_eliminar_su_propio_anuncio(self):
        listing = Listing.objects.create(
            owner=self.user, category=Listing.Category.COCHE,
            operation_type=Listing.OperationType.VENTA, title="Mi anuncio",
            price=1000, city=self.city,
        )
        self.client.login(email="ana@example.com", password="unaClaveSegura123")
        response = self.client.post(reverse("listings:delete", args=[listing.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())
