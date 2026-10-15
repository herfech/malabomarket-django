from django.db import IntegrityError
from django.test import TestCase

from .models import User


class UserModelTests(TestCase):
    def test_crear_usuario_normal_nace_como_cliente(self):
        """Nadie se auto-asigna un rol elevado al registrarse."""
        user = User.objects.create_user(email="cliente@example.com", password="unaClaveSegura123")
        self.assertEqual(user.role, User.Role.CLIENTE)
        self.assertFalse(user.is_office_staff)
        self.assertFalse(user.is_platform_admin)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_password_se_guarda_hasheada_no_en_texto_plano(self):
        user = User.objects.create_user(email="seguro@example.com", password="unaClaveSegura123")
        self.assertNotEqual(user.password, "unaClaveSegura123")
        self.assertTrue(user.check_password("unaClaveSegura123"))
        self.assertTrue(user.password.startswith("argon2"))  # Argon2 es el hasher configurado

    def test_email_duplicado_no_permitido(self):
        User.objects.create_user(email="dup@example.com", password="unaClaveSegura123")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="dup@example.com", password="otraClave456")

    def test_crear_superusuario_queda_como_administrador(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="unaClaveSegura123")
        self.assertEqual(admin.role, User.Role.ADMINISTRADOR)
        self.assertTrue(admin.is_platform_admin)
        self.assertTrue(admin.is_office_staff)  # un administrador también cuenta como personal de oficina
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_personal_de_oficina_es_office_staff_pero_no_platform_admin(self):
        staff = User.objects.create_user(
            email="oficina@example.com", password="unaClaveSegura123", role=User.Role.PERSONAL_OFICINA
        )
        self.assertTrue(staff.is_office_staff)
        self.assertFalse(staff.is_platform_admin)

    def test_cliente_no_es_office_staff(self):
        cliente = User.objects.create_user(email="normal@example.com", password="unaClaveSegura123")
        self.assertFalse(cliente.is_office_staff)

    def test_login_es_por_email_no_por_username(self):
        self.assertEqual(User.USERNAME_FIELD, "email")
