from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from .models import CarDetails, City, Favorite, HouseDetails, LandDetails, Listing


class PublicSiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.malabo = City.objects.create(name="Malabo")
        cls.bata = City.objects.create(name="Bata")
        cls.owner = User.objects.create_user(
            email="a@example.com", password="unaClaveSegura123", full_name="Ana Obiang",
            phone="240222000111", whatsapp_number="+240 222 000 111",
        )
        cls.other = User.objects.create_user(email="b@example.com", password="unaClaveSegura123")
        cls.staff = User.objects.create_user(
            email="s@example.com", password="unaClaveSegura123", role=User.Role.PERSONAL_OFICINA
        )

        def mk(**kw):
            data = dict(owner=cls.owner, operation_type="venta", city=cls.malabo, price=Decimal("1000000"))
            data.update(kw)
            return Listing.objects.create(**data)

        cls.prado = mk(category="coche", title="Toyota Prado 2019", price=Decimal("18500000"), is_premium=True)
        CarDetails.objects.create(listing=cls.prado, brand="Toyota", model="Prado", year=2019, mileage_km=42000,
                                  fuel_type="diesel", transmission="automatico")
        cls.golf = mk(category="coche", title="Volkswagen Golf", price=Decimal("5000000"), city=cls.bata)
        CarDetails.objects.create(listing=cls.golf, brand="Volkswagen", model="Golf", year=2012, mileage_km=150000,
                                  fuel_type="gasolina", transmission="manual")
        cls.piso = mk(category="casa", title="Apartamento Malabo II", operation_type="alquiler", price=Decimal("400000"))
        HouseDetails.objects.create(listing=cls.piso, property_type="apartamento", bedrooms=3, bathrooms=2,
                                    area_m2=Decimal("120"), has_parking=True)
        cls.solar = mk(category="terreno", title="Solar en Bata", city=cls.bata)
        LandDetails.objects.create(listing=cls.solar, area_m2=Decimal("600"), land_use="urbano", has_title_deed=True)
        cls.oculto = mk(category="coche", title="Coche pausado", status="suspendido")
        CarDetails.objects.create(listing=cls.oculto, brand="Kia", model="Rio", year=2015, mileage_km=1,
                                  fuel_type="gasolina", transmission="manual")

    def titles(self, response):
        return [l.title for l in response.context["page"].object_list]

    # --- listado ---
    def test_home_carga_y_muestra_destacados(self):
        r = self.client.get(reverse("listings:home"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Toyota Prado 2019")
        self.assertNotContains(r, "Coche pausado")

    def test_categoria_solo_muestra_su_categoria_y_activos(self):
        r = self.client.get("/coches/")
        self.assertEqual(sorted(self.titles(r)), ["Toyota Prado 2019", "Volkswagen Golf"])

    def test_categoria_desconocida_404(self):
        self.assertEqual(self.client.get("/motos/").status_code, 404)

    def test_destacados_primero(self):
        self.assertEqual(self.titles(self.client.get("/coches/"))[0], "Toyota Prado 2019")

    def test_filtros_de_coche(self):
        self.assertEqual(self.titles(self.client.get("/coches/?marca=toyota")), ["Toyota Prado 2019"])
        self.assertEqual(self.titles(self.client.get("/coches/?km_max=100000")), ["Toyota Prado 2019"])
        self.assertEqual(self.titles(self.client.get("/coches/?combustible=gasolina")), ["Volkswagen Golf"])
        self.assertEqual(self.titles(self.client.get("/coches/?anio_min=2015")), ["Toyota Prado 2019"])
        self.assertEqual(self.titles(self.client.get("/coches/?precio_max=6000000")), ["Volkswagen Golf"])
        self.assertEqual(self.titles(self.client.get(f"/coches/?ciudad={self.bata.pk}")), ["Volkswagen Golf"])

    def test_filtros_casa_y_terreno(self):
        self.assertEqual(self.titles(self.client.get("/casas/?hab_min=3&parqueo=on")), ["Apartamento Malabo II"])
        self.assertEqual(self.titles(self.client.get("/casas/?hab_min=4")), [])
        self.assertEqual(self.titles(self.client.get("/terrenos/?titulo=on&m2_min=500")), ["Solar en Bata"])

    def test_busqueda_de_texto_en_todas_las_categorias(self):
        self.assertEqual(sorted(self.titles(self.client.get("/buscar/?q=bata"))), ["Solar en Bata", "Volkswagen Golf"])
        self.assertEqual(self.titles(self.client.get("/buscar/?q=prado")), ["Toyota Prado 2019"])

    def test_orden_por_precio(self):
        r = self.client.get("/coches/?orden=precio_asc")
        self.assertEqual(self.titles(r)[0], "Toyota Prado 2019")  # destacado siempre primero
        self.assertEqual(self.titles(self.client.get("/buscar/?orden=precio_asc"))[1], "Apartamento Malabo II")  # tras el destacado

    def test_valores_invalidos_se_ignoran_sin_romper(self):
        r = self.client.get("/coches/?precio_min=abc&anio_min=zz&ciudad=999&orden=hack&page=xx")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self.titles(r)), 2)

    def test_intento_de_inyeccion_en_busqueda_es_inocuo(self):
        r = self.client.get("/buscar/", {"q": "'; DROP TABLE listings_listing; --"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Listing.objects.count(), 5)

    def test_paginacion(self):
        for i in range(15):
            Listing.objects.create(owner=self.owner, category="terreno", operation_type="venta",
                                   title=f"Terreno {i}", price=1, city=self.malabo)
        r = self.client.get("/terrenos/")
        self.assertEqual(len(self.titles(r)), 12)
        self.assertEqual(len(self.titles(self.client.get("/terrenos/?page=2"))), 4)

    # --- ficha ---
    def test_ficha_publica_con_whatsapp_del_dueno(self):
        r = self.client.get(self.prado.get_absolute_url())
        self.assertContains(r, "https://wa.me/240222000111")
        self.assertContains(r, "18.500.000 XAF")
        self.assertContains(r, 'application/ld+json')

    def test_ficha_oficina_muestra_whatsapp_del_cliente_no_del_empleado(self):
        l = Listing.objects.create(owner=self.staff, category="terreno", operation_type="venta", title="Solar oficina",
                                   price=1, city=self.malabo, is_office_listing=True,
                                   contact_name="Pedro Mba", contact_whatsapp="240555123456")
        LandDetails.objects.create(listing=l, area_m2=100, land_use="rural")
        r = self.client.get(l.get_absolute_url())
        self.assertContains(r, "wa.me/240555123456")
        self.assertContains(r, "Pedro Mba")
        self.assertNotContains(r, "s@example.com")

    def test_slug_incorrecto_redirige_a_la_url_canonica(self):
        r = self.client.get(f"/anuncios/{self.prado.pk}/otra-cosa/")
        self.assertRedirects(r, self.prado.get_absolute_url(), status_code=301)

    def test_ficha_incrementa_vistas(self):
        self.client.get(self.prado.get_absolute_url())
        self.prado.refresh_from_db()
        self.assertEqual(self.prado.views_count, 1)

    def test_anuncio_no_activo_404_para_publico_visible_para_dueno_y_staff(self):
        url = self.oculto.get_absolute_url()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "noindex")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.oculto.refresh_from_db()
        self.assertEqual(self.oculto.views_count, 0)  # no cuenta vistas del dueño/staff

    # --- favoritos ---
    def test_favoritos_requieren_login_y_post(self):
        url = reverse("listings:toggle_favorite", args=[self.prado.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Favorite.objects.exists())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_favorito_alterna_y_aparece_en_la_pagina(self):
        self.client.force_login(self.other)
        url = reverse("listings:toggle_favorite", args=[self.prado.pk])
        self.client.post(url)
        self.assertEqual(Favorite.objects.filter(user=self.other).count(), 1)
        self.assertContains(self.client.get("/favoritos/"), "Toyota Prado 2019")
        self.client.post(url)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_favorito_ignora_redireccion_externa(self):
        self.client.force_login(self.other)
        r = self.client.post(reverse("listings:toggle_favorite", args=[self.prado.pk]), {"next": "https://evil.com/"})
        self.assertRedirects(r, self.prado.get_absolute_url(), fetch_redirect_response=False)

    def test_no_se_puede_marcar_favorito_un_anuncio_oculto(self):
        self.client.force_login(self.other)
        r = self.client.post(reverse("listings:toggle_favorite", args=[self.oculto.pk]))
        self.assertEqual(r.status_code, 404)

    # --- SEO ---
    def test_sitemap_incluye_activos_y_excluye_ocultos(self):
        r = self.client.get("/sitemap.xml")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.prado.get_absolute_url())
        self.assertNotContains(r, self.oculto.get_absolute_url())
        self.assertContains(r, "/coches/")

    def test_robots(self):
        r = self.client.get("/robots.txt")
        self.assertContains(r, "Sitemap:")
        self.assertContains(r, "Disallow: /admin/")

    def test_filtros_con_resultados_llevan_noindex(self):
        self.assertContains(self.client.get("/coches/?marca=toyota"), "noindex")
        self.assertNotContains(self.client.get("/coches/"), "noindex")


class DesignPagesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="u@example.com", password="unaClaveSegura123", full_name="Uxía")
        self.city = City.objects.create(name="Malabo")

    def test_publicar_inicio_pide_login_y_muestra_categorias(self):
        self.assertEqual(self.client.get("/anuncios/publicar/").status_code, 302)
        self.client.force_login(self.user)
        r = self.client.get("/anuncios/publicar/")
        self.assertContains(r, "/anuncios/publicar/coche/")
        self.assertContains(r, "/anuncios/publicar/terreno/")

    def test_confirmar_eliminar_get_renderiza(self):
        l = Listing.objects.create(owner=self.user, category="terreno", operation_type="venta", title="X", price=1, city=self.city)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(f"/anuncios/{l.pk}/eliminar/"), "Eliminar este anuncio")

    def test_marca_y_contacto_configurables_en_plantilla(self):
        r = self.client.get("/")
        self.assertContains(r, "Malabo")
        self.assertContains(r, "wa.me/240222000000")
        self.assertContains(r, "Malabo")  # ciudades del pie
