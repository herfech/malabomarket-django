from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class City(models.Model):
    """Tabla de referencia — ciudades donde opera la plataforma."""

    name = models.CharField(_("nombre"), max_length=100, unique=True)
    region = models.CharField(_("región"), max_length=100, blank=True)
    is_active = models.BooleanField(_("activa"), default=True)

    class Meta:
        verbose_name = _("ciudad")
        verbose_name_plural = _("ciudades")
        ordering = ["name"]

    def __str__(self):
        return self.name


class ListingQuerySet(models.QuerySet):
    def public(self):
        """Anuncios visibles para cualquier visitante: activos y no caducados."""
        from django.utils import timezone

        return self.filter(status="activo").filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        )

    def with_card_data(self):
        return self.select_related(
            "city", "owner", "car_details", "house_details", "land_details"
        ).prefetch_related("images")


class Listing(TimeStampedModel):
    """
    Tabla principal de anuncios — común a coches, casas y terrenos.
    El detalle específico de cada categoría vive en su propio modelo
    (CarDetails / HouseDetails / LandDetails), enlazado 1 a 1.
    """

    class Category(models.TextChoices):
        COCHE = "coche", _("Coche")
        CASA = "casa", _("Casa/Apartamento")
        TERRENO = "terreno", _("Terreno")

    class OperationType(models.TextChoices):
        VENTA = "venta", _("Venta")
        ALQUILER = "alquiler", _("Alquiler")

    class Status(models.TextChoices):
        BORRADOR = "borrador", _("Borrador")
        ACTIVO = "activo", _("Activo")
        VENDIDO = "vendido", _("Vendido")
        ALQUILADO = "alquilado", _("Alquilado")
        EXPIRADO = "expirado", _("Expirado")
        SUSPENDIDO = "suspendido", _("Pausado")

    class Plan(models.TextChoices):
        BASICO = "basico", _("Básico")
        DESTACADO = "destacado", _("Destacado")
        PREMIUM = "premium", _("Premium")

    class PaymentStatus(models.TextChoices):
        NO_APLICA = "no_aplica", _("No aplica")
        PENDIENTE = "pendiente", _("Pendiente")
        PAGADO = "pagado", _("Pagado")

    # --- Propiedad del anuncio ---
    # El "dueño" en el sistema (quien puede editarlo) es siempre un User.
    # Para anuncios de oficina (is_office_listing=True), este es el
    # empleado/administrador que lo publicó, NO el cliente real — el
    # contacto real del cliente va en los campos contact_* de abajo.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("propietario"),
        on_delete=models.CASCADE,
        related_name="listings",
    )

    category = models.CharField(_("categoría"), max_length=10, choices=Category.choices)
    operation_type = models.CharField(_("operación"), max_length=10, choices=OperationType.choices)
    status = models.CharField(_("estado"), max_length=12, choices=Status.choices, default=Status.ACTIVO)

    title = models.CharField(_("título"), max_length=120)
    description = models.TextField(_("descripción"), blank=True)
    price = models.DecimalField(_("precio"), max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(_("moneda"), max_length=8, default="XAF")

    city = models.ForeignKey(City, verbose_name=_("ciudad"), on_delete=models.PROTECT, related_name="listings")
    address_zone = models.CharField(_("zona/barrio"), max_length=150, blank=True)
    latitude = models.FloatField(_("latitud"), null=True, blank=True)
    longitude = models.FloatField(_("longitud"), null=True, blank=True)

    plan = models.CharField(_("plan"), max_length=10, choices=Plan.choices, default=Plan.BASICO)
    payment_status = models.CharField(
        _("estado de pago"), max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.NO_APLICA
    )

    # --- Opción 2: publicado en oficina, sin cuenta del cliente ---
    is_office_listing = models.BooleanField(
        _("publicado en oficina"), default=False,
        help_text=_("Marcado por un técnico al publicar en nombre de un cliente sin cuenta."),
    )
    contact_name = models.CharField(_("nombre de contacto"), max_length=150, blank=True)
    contact_phone = models.CharField(_("teléfono de contacto"), max_length=30, blank=True)
    contact_whatsapp = models.CharField(_("WhatsApp de contacto"), max_length=30, blank=True)

    expires_at = models.DateTimeField(
        _("caduca el"), null=True, blank=True,
        help_text=_("Pasada esta fecha el anuncio deja de mostrarse. Vacío = no caduca."),
    )
    is_premium = models.BooleanField(_("destacado"), default=False)
    premium_until = models.DateTimeField(_("destacado hasta"), null=True, blank=True)
    views_count = models.PositiveIntegerField(_("vistas"), default=0)

    objects = ListingQuerySet.as_manager()

    class Meta:
        verbose_name = _("anuncio")
        verbose_name_plural = _("anuncios")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["price"]),
            models.Index(fields=["-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(price__gte=0), name="listing_price_gte_0"),
        ]

    def __str__(self):
        return self.title

    @property
    def is_expired(self):
        from django.utils import timezone

        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_publicly_visible(self):
        return self.status == self.Status.ACTIVO and not self.is_expired

    @property
    def slug(self):
        return slugify(self.title)[:60] or "anuncio"

    def get_absolute_url(self):
        return reverse("listings:detail", kwargs={"pk": self.pk, "slug": self.slug})

    @property
    def cover_image(self):
        """Portada (usa el prefetch de imágenes, sin consultas extra)."""
        images = list(self.images.all())
        for img in images:
            if img.is_cover:
                return img
        return images[0] if images else None

    @property
    def category_title(self):
        return {"coche": "Coches", "casa": "Casas y Apartamentos", "terreno": "Terrenos"}[self.category]

    @property
    def category_segment(self):
        """Segmento de URL público de la categoría (coche -> coches)."""
        return {"coche": "coches", "casa": "casas", "terreno": "terrenos"}[self.category]

    @property
    def details(self):
        return {
            "coche": getattr(self, "car_details", None),
            "casa": getattr(self, "house_details", None),
            "terreno": getattr(self, "land_details", None),
        }.get(self.category)

    @property
    def display_contact_name(self):
        """Nombre a mostrar en la ficha pública: el del cliente si es
        anuncio de oficina, si no, el del dueño de la cuenta."""
        return self.contact_name if self.is_office_listing else self.owner.full_name

    @property
    def display_whatsapp(self):
        return self.contact_whatsapp if self.is_office_listing else self.owner.whatsapp_number

    @property
    def display_phone(self):
        return self.contact_phone if self.is_office_listing else self.owner.phone


class CarDetails(models.Model):
    """Detalle específico de la categoría Coche (1 a 1 con Listing)."""

    class FuelType(models.TextChoices):
        GASOLINA = "gasolina", _("Gasolina")
        DIESEL = "diesel", _("Diésel")
        HIBRIDO = "hibrido", _("Híbrido")
        ELECTRICO = "electrico", _("Eléctrico")
        GAS = "gas", _("Gas")

    class Transmission(models.TextChoices):
        MANUAL = "manual", _("Manual")
        AUTOMATICO = "automatico", _("Automático")

    class Condition(models.TextChoices):
        NUEVO = "nuevo", _("Nuevo")
        USADO = "usado", _("Usado")
        IMPORTADO = "importado", _("Importado")

    listing = models.OneToOneField(Listing, on_delete=models.CASCADE, primary_key=True, related_name="car_details")
    brand = models.CharField(_("marca"), max_length=80)
    model = models.CharField(_("modelo"), max_length=80)
    year = models.PositiveSmallIntegerField(_("año"), validators=[MinValueValidator(1980), MaxValueValidator(2100)])
    mileage_km = models.PositiveIntegerField(_("kilometraje (km)"))
    fuel_type = models.CharField(_("combustible"), max_length=10, choices=FuelType.choices)
    transmission = models.CharField(_("transmisión"), max_length=10, choices=Transmission.choices)
    condition = models.CharField(_("condición"), max_length=10, choices=Condition.choices, default=Condition.USADO)
    engine_size_cc = models.PositiveIntegerField(_("cilindrada (cc)"), null=True, blank=True)
    doors = models.PositiveSmallIntegerField(_("puertas"), null=True, blank=True)
    color = models.CharField(_("color"), max_length=50, blank=True)

    class Meta:
        verbose_name = _("detalle de coche")
        verbose_name_plural = _("detalles de coches")

    def __str__(self):
        return f"{self.brand} {self.model} ({self.year})"


class HouseDetails(models.Model):
    """Detalle específico de Casas/Apartamentos (1 a 1 con Listing)."""

    class PropertyType(models.TextChoices):
        CASA = "casa", _("Casa")
        APARTAMENTO = "apartamento", _("Apartamento")
        CHALET = "chalet", _("Chalet")
        ESTUDIO = "estudio", _("Estudio")

    listing = models.OneToOneField(Listing, on_delete=models.CASCADE, primary_key=True, related_name="house_details")
    property_type = models.CharField(_("tipo"), max_length=15, choices=PropertyType.choices)
    bedrooms = models.PositiveSmallIntegerField(_("habitaciones"))
    bathrooms = models.PositiveSmallIntegerField(_("baños"))
    area_m2 = models.DecimalField(_("superficie (m²)"), max_digits=8, decimal_places=2, validators=[MinValueValidator(0.01)])
    is_furnished = models.BooleanField(_("amueblado"), default=False)
    has_parking = models.BooleanField(_("parqueo"), default=False)
    has_garden = models.BooleanField(_("jardín"), default=False)
    floor_number = models.SmallIntegerField(_("piso"), null=True, blank=True)

    class Meta:
        verbose_name = _("detalle de casa")
        verbose_name_plural = _("detalles de casas")

    def __str__(self):
        return f"{self.get_property_type_display()} · {self.bedrooms} hab."


class LandDetails(models.Model):
    """Detalle específico de Terrenos (1 a 1 con Listing)."""

    class LandUse(models.TextChoices):
        URBANO = "urbano", _("Urbano")
        RURAL = "rural", _("Rural")
        COMERCIAL = "comercial", _("Comercial")
        AGRICOLA = "agricola", _("Agrícola")

    listing = models.OneToOneField(Listing, on_delete=models.CASCADE, primary_key=True, related_name="land_details")
    area_m2 = models.DecimalField(_("superficie (m²)"), max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    land_use = models.CharField(_("uso de suelo"), max_length=10, choices=LandUse.choices)
    has_title_deed = models.BooleanField(_("con título de propiedad"), default=False)
    is_fenced = models.BooleanField(_("cercado"), default=False)

    class Meta:
        verbose_name = _("detalle de terreno")
        verbose_name_plural = _("detalles de terrenos")

    def __str__(self):
        return f"Terreno {self.area_m2} m² ({self.get_land_use_display()})"


def listing_image_upload_path(instance, filename):
    return f"listings/{instance.listing_id}/{filename}"


class ListingImage(models.Model):
    """Galería de fotos de un anuncio."""

    listing = models.ForeignKey(Listing, verbose_name=_("anuncio"), on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(_("imagen"), upload_to=listing_image_upload_path)
    position = models.PositiveSmallIntegerField(_("posición"), default=0)
    is_cover = models.BooleanField(_("es portada"), default=False)

    class Meta:
        verbose_name = _("imagen de anuncio")
        verbose_name_plural = _("imágenes de anuncios")
        ordering = ["position"]

    def __str__(self):
        return f"Imagen #{self.position} de {self.listing_id}"


class Favorite(TimeStampedModel):
    """Anuncios guardados como favoritos por un usuario."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="favorited_by")

    class Meta:
        verbose_name = _("favorito")
        verbose_name_plural = _("favoritos")
        constraints = [
            models.UniqueConstraint(fields=["user", "listing"], name="unique_user_listing_favorite"),
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.listing}"
