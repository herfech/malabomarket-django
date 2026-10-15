from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class UserManager(BaseUserManager):
    """
    Manager para el modelo de usuario personalizado. El login es por email,
    no por username — no tiene sentido pedirle un "nombre de usuario" a
    alguien que solo quiere publicar un anuncio.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El usuario debe tener un correo electrónico.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMINISTRADOR)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """
    Usuario de la plataforma. Tres roles de negocio (no confundir con
    is_staff/is_superuser, que son para el admin nativo de Django):

    - CLIENTE: cualquiera que se registra desde la web. Publica y paga.
    - PERSONAL_OFICINA: empleado que publica anuncios EN NOMBRE de un
      cliente que no tiene cuenta (Opción 2), y puede confirmar pagos
      hechos en efectivo.
    - ADMINISTRADOR: además de lo anterior, gestiona usuarios, planes y
      la configuración general de la plataforma.
    """

    class Role(models.TextChoices):
        CLIENTE = "cliente", _("Cliente")
        PERSONAL_OFICINA = "personal_oficina", _("Personal de oficina")
        ADMINISTRADOR = "administrador", _("Administrador")

    email = models.EmailField(_("correo electrónico"), unique=True)
    full_name = models.CharField(_("nombre completo"), max_length=150, blank=True)
    phone = models.CharField(_("teléfono"), max_length=30, blank=True)
    whatsapp_number = models.CharField(_("WhatsApp"), max_length=30, blank=True)
    avatar = models.ImageField(_("foto de perfil"), upload_to="avatars/", blank=True, null=True)

    role = models.CharField(
        _("rol"), max_length=20, choices=Role.choices, default=Role.CLIENTE
    )
    is_verified = models.BooleanField(
        _("verificado"), default=False,
        help_text=_("Sello de confianza visible en sus anuncios."),
    )
    is_professional = models.BooleanField(
        _("cuenta profesional"), default=False,
        help_text=_("Agencia inmobiliaria o concesionario, no particular."),
    )

    # Requeridos por Django para el admin nativo (/django-admin), no para
    # nuestro panel de oficina propio — ese se controla con "role".
    is_active = models.BooleanField(_("activo"), default=True)
    is_staff = models.BooleanField(_("acceso al admin de Django"), default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _("usuario")
        verbose_name_plural = _("usuarios")

    def __str__(self):
        return self.full_name or self.email

    @property
    def is_office_staff(self):
        """True para personal de oficina Y administradores."""
        return self.role in (self.Role.PERSONAL_OFICINA, self.Role.ADMINISTRADOR)

    @property
    def is_platform_admin(self):
        """True solo para administradores (gestión completa)."""
        return self.role == self.Role.ADMINISTRADOR
