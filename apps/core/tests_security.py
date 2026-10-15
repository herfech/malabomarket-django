from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.listings.models import City, Listing
from apps.listings import views as listing_views


class SecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="u@x.com", password="unaClaveSegura123")

    def test_health(self):
        r = self.client.get("/salud/")
        self.assertEqual((r.status_code, r.content), (200, b"ok"))

    def test_no_cdn_in_pages(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("cdn.tailwindcss.com", html)
        self.assertIn("css/tailwind.css", html)

    def test_login_locks_after_five_failures(self):
        url = reverse("accounts:login")
        for _ in range(5):
            self.client.post(url, {"username": "u@x.com", "password": "mala"})
        r = self.client.post(url, {"username": "u@x.com", "password": "unaClaveSegura123"})
        self.assertContains(r, "Demasiados intentos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_ok_resets_counter(self):
        url = reverse("accounts:login")
        for _ in range(3):
            self.client.post(url, {"username": "u@x.com", "password": "mala"})
        r = self.client.post(url, {"username": "u@x.com", "password": "unaClaveSegura123"})
        self.assertEqual(r.status_code, 302)

    def test_register_honeypot_blocks_bots(self):
        data = {"email": "bot@x.com", "full_name": "Bot", "phone": "123456789",
                "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "website": "http://spam"}
        self.client.post(reverse("accounts:register"), data)
        self.assertFalse(User.objects.filter(email="bot@x.com").exists())
        data["website"] = ""
        self.client.post(reverse("accounts:register"), data)
        self.assertTrue(User.objects.filter(email="bot@x.com").exists())

    def test_daily_publish_limit(self):
        city = City.objects.create(name="Malabo")
        for i in range(listing_views.MAX_LISTINGS_PER_DAY):
            Listing.objects.create(owner=self.user, category="coche", operation_type="venta", city=city,
                                   price=1, title=f"c{i}", status="borrador")
        self.client.login(email="u@x.com", password="unaClaveSegura123")
        r = self.client.post(reverse("listings:publish", args=["coche"]), {"title": "otro"})
        self.assertContains(r, "máximo de")
