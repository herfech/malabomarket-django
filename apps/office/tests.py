import io
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.listings.models import CarDetails, City, Listing

from . import services
from .models import AuditLog, Payment, PlanConfig

PW = "unaClaveSegura123"


def photo():
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (30, 90, 140)).save(buf, "JPEG")
    return SimpleUploadedFile("f.jpg", buf.getvalue(), content_type="image/jpeg")


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.city = City.objects.create(name="Malabo")
        cls.client_user = User.objects.create_user(email="c@x.com", password=PW, full_name="Cli")
        cls.staff = User.objects.create_user(email="s@x.com", password=PW, role=User.Role.PERSONAL_OFICINA)
        cls.admin = User.objects.create_user(email="a@x.com", password=PW, role=User.Role.ADMINISTRADOR)

    def mk(self, **kw):
        data = dict(owner=self.client_user, category="coche", operation_type="venta", city=self.city,
                    price=Decimal("1000"), title="Coche", status="borrador")
        data.update(kw)
        return Listing.objects.create(**data)

    def car_post(self, **extra):
        data = {
            "operation_type": "venta", "title": "Toyota Hilux", "description": "Buen estado", "price": "9000000",
            "city": self.city.pk, "address_zone": "",
            "brand": "Toyota", "model": "Hilux", "year": 2018, "mileage_km": 50000,
            "fuel_type": "diesel", "transmission": "manual", "condition": "usado",
            "contact_name": "Pedro Nguema", "contact_phone": "222 111 333",
            "images": photo(),
        }
        data.update(extra)
        return data


class PlansAndServices(Base):
    def test_plans_seeded(self):
        self.assertEqual(set(PlanConfig.objects.values_list("code", flat=True)), {"basico", "destacado", "premium"})
        self.assertTrue(services.get_plan("basico").is_free)

    def test_receipts_are_correlative_and_per_year(self):
        a = services.next_receipt_number(timezone.now().replace(year=2030))
        b = services.next_receipt_number(timezone.now().replace(year=2030))
        c = services.next_receipt_number(timezone.now().replace(year=2031))
        self.assertEqual((a, b, c), ("R-2030-000001", "R-2030-000002", "R-2031-000001"))

    def test_free_plan_activates_with_expiry(self):
        l = self.mk()
        services.start_listing_with_plan(l, services.get_plan("basico"), self.client_user)
        l.refresh_from_db()
        self.assertEqual(l.status, "activo")
        self.assertAlmostEqual((l.expires_at - timezone.now()).days, 29, delta=1)

    def test_paid_plan_waits_for_payment_then_confirm(self):
        l = self.mk()
        p = services.start_listing_with_plan(l, services.get_plan("destacado"), self.client_user)
        l.refresh_from_db()
        self.assertEqual((l.status, p.status), ("borrador", "pendiente"))
        self.assertFalse(Listing.objects.public().filter(pk=l.pk).exists())
        p = services.confirm_payment(p, self.staff)
        l.refresh_from_db()
        self.assertEqual(l.status, "activo")
        self.assertTrue(l.is_premium)
        self.assertTrue(p.receipt_number.startswith("R-"))
        self.assertEqual(p.received_by, self.staff)
        with self.assertRaises(services.BusinessError):
            services.confirm_payment(p, self.staff)

    def test_price_change_does_not_alter_old_payment(self):
        l = self.mk()
        p = services.register_cash_payment(l, services.get_plan("destacado"), self.staff)
        PlanConfig.objects.filter(code="destacado").update(price=1)
        p.refresh_from_db()
        self.assertEqual(p.amount, Decimal("8000"))

    def test_void_requires_reason_and_suspends(self):
        l = self.mk()
        p = services.register_cash_payment(l, services.get_plan("premium"), self.staff)
        with self.assertRaises(services.BusinessError):
            services.void_payment(p, self.admin, " ")
        services.void_payment(p, self.admin, "Error de cobro")
        p.refresh_from_db(); l.refresh_from_db()
        self.assertEqual((p.status, l.status), ("anulado", "suspendido"))
        self.assertTrue(AuditLog.objects.filter(action="pago_anulado", payment_id_ref=p.pk).exists())

    def test_audit_records_who_confirmed(self):
        l = self.mk()
        p = services.register_cash_payment(l, services.get_plan("destacado"), self.staff)
        e = AuditLog.objects.get(action="pago_confirmado")
        self.assertEqual((e.user, e.payment_id_ref), (self.staff, p.pk))
        self.assertIn("s@x.com", e.user_label)

    def test_cannot_activate_with_pending_payment(self):
        l = self.mk()
        services.start_listing_with_plan(l, services.get_plan("destacado"), self.client_user)
        with self.assertRaises(services.BusinessError):
            services.set_listing_status(l, "activo", self.staff)


class Expiry(Base):
    def test_public_excludes_expired_and_command_marks_them(self):
        l = self.mk(status="activo", expires_at=timezone.now() - timedelta(days=1))
        ok = self.mk(status="activo", expires_at=timezone.now() + timedelta(days=1), title="Vigente")
        self.assertEqual(list(Listing.objects.public()), [ok])
        call_command("expire_listings")
        l.refresh_from_db()
        self.assertEqual(l.status, "expirado")

    def test_expired_detail_is_404(self):
        l = self.mk(status="activo", expires_at=timezone.now() - timedelta(days=1))
        CarDetails.objects.create(listing=l, brand="A", model="B", year=2010, mileage_km=1, fuel_type="diesel", transmission="manual")
        self.assertEqual(self.client.get(l.get_absolute_url()).status_code, 404)


class Permissions(Base):
    URLS = ["office:dashboard", "office:publish_start", "office:payments", "office:listings", "office:audit"]

    def test_anonymous_redirected_to_login(self):
        for n in self.URLS:
            r = self.client.get(reverse(n))
            self.assertEqual(r.status_code, 302, n)
            self.assertIn("login", r["Location"])

    def test_client_gets_404(self):
        self.client.login(email="c@x.com", password=PW)
        for n in self.URLS:
            self.assertEqual(self.client.get(reverse(n)).status_code, 404, n)

    def test_staff_ok_but_audit_admin_only(self):
        self.client.login(email="s@x.com", password=PW)
        for n in self.URLS[:-1]:
            self.assertEqual(self.client.get(reverse(n)).status_code, 200, n)
        self.assertEqual(self.client.get(reverse("office:audit")).status_code, 404)
        self.client.login(email="a@x.com", password=PW)
        self.assertEqual(self.client.get(reverse("office:audit")).status_code, 200)

    def test_staff_cannot_void(self):
        l = self.mk()
        p = services.register_cash_payment(l, services.get_plan("destacado"), self.staff)
        self.client.login(email="s@x.com", password=PW)
        r = self.client.post(reverse("office:void_payment", args=[p.pk]), {"reason": "x" * 8})
        self.assertEqual(r.status_code, 404)
        p.refresh_from_db()
        self.assertEqual(p.status, "pagado")

    def test_confirm_requires_post(self):
        p = services.start_listing_with_plan(self.mk(), services.get_plan("destacado"), self.client_user)
        self.client.login(email="s@x.com", password=PW)
        self.assertEqual(self.client.get(reverse("office:confirm_payment", args=[p.pk])).status_code, 405)

    def test_pending_has_no_receipt(self):
        p = services.start_listing_with_plan(self.mk(), services.get_plan("destacado"), self.client_user)
        self.client.login(email="s@x.com", password=PW)
        self.assertEqual(self.client.get(reverse("office:receipt", args=[p.pk])).status_code, 404)


class OfficePublishing(Base):
    def setUp(self):
        self.client.login(email="s@x.com", password=PW)
        self.url = reverse("office:publish", args=["coche"])

    def test_form_renders(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Datos del cliente")
        self.assertContains(r, "paid_now")

    def test_free_plan_publishes_without_payment(self):
        r = self.client.post(self.url, self.car_post(plan="basico"))
        l = Listing.objects.get(title="Toyota Hilux")
        self.assertRedirects(r, reverse("office:listing", args=[l.pk]))
        self.assertTrue(l.is_office_listing)
        self.assertEqual((l.status, l.contact_name), ("activo", "Pedro Nguema"))
        self.assertEqual(l.display_contact_name, "Pedro Nguema")
        self.assertFalse(Payment.objects.exists())

    def test_paid_now_creates_receipt_and_activates(self):
        r = self.client.post(self.url, self.car_post(plan="destacado", paid_now="on"))
        p = Payment.objects.get()
        self.assertRedirects(r, reverse("office:receipt", args=[p.pk]))
        self.assertEqual((p.status, p.received_by), ("pagado", self.staff))
        self.assertEqual(p.listing.status, "activo")
        self.assertContains(self.client.get(reverse("office:receipt", args=[p.pk])), p.receipt_number)

    def test_paid_without_checkbox_stays_draft_with_pending_payment(self):
        self.client.post(self.url, self.car_post(plan="premium"))
        l = Listing.objects.get(title="Toyota Hilux")
        self.assertEqual(l.status, "borrador")
        self.assertEqual(Payment.objects.get().status, "pendiente")
        self.assertFalse(Listing.objects.public().filter(pk=l.pk).exists())
        # confirmar desde el panel
        p = Payment.objects.get()
        self.client.post(reverse("office:confirm_payment", args=[p.pk]))
        l.refresh_from_db(); p.refresh_from_db()
        self.assertEqual((l.status, p.status), ("activo", "pagado"))

    def test_requires_photo_and_phone(self):
        data = self.car_post(plan="basico", contact_phone="12")
        self.client.post(self.url, data)
        self.assertFalse(Listing.objects.filter(title="Toyota Hilux").exists())
        data = self.car_post(plan="basico"); data.pop("images")
        self.client.post(self.url, data)
        self.assertFalse(Listing.objects.filter(title="Toyota Hilux").exists())

    def test_audit_entry_for_office_publication(self):
        self.client.post(self.url, self.car_post(plan="basico"))
        self.assertTrue(AuditLog.objects.filter(action="anuncio_publicado_en_oficina", user=self.staff).exists())

    def test_renew_from_manage_page(self):
        l = self.mk(status="expirado", expires_at=timezone.now() - timedelta(days=3))
        r = self.client.post(reverse("office:listing", args=[l.pk]), {"action": "renew", "plan": "destacado", "notes": ""})
        p = Payment.objects.get()
        self.assertRedirects(r, reverse("office:receipt", args=[p.pk]))
        l.refresh_from_db()
        self.assertEqual(l.status, "activo")
        self.assertGreater(l.expires_at, timezone.now())


class ClientPublishWithPlan(Base):
    def test_client_chooses_paid_plan_goes_to_draft(self):
        self.client.login(email="c@x.com", password=PW)
        data = self.car_post(plan="destacado")
        data.pop("contact_name"); data.pop("contact_phone")
        self.client.post(reverse("listings:publish", args=["coche"]), data)
        l = Listing.objects.get(title="Toyota Hilux")
        self.assertEqual((l.status, l.owner), ("borrador", self.client_user))
        self.assertEqual(Payment.objects.get().status, "pendiente")

    def test_client_free_plan_is_active(self):
        self.client.login(email="c@x.com", password=PW)
        data = self.car_post(); data.pop("contact_name"); data.pop("contact_phone")
        self.client.post(reverse("listings:publish", args=["coche"]), data)
        self.assertEqual(Listing.objects.get(title="Toyota Hilux").status, "activo")
