from django.urls import path

from . import views

app_name = "listings"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.search, name="search"),
    path("favoritos/", views.favorites, name="favorites"),
    path("anuncios/publicar/", views.publish_start, name="publish_start"),
    path("anuncios/publicar/<str:category>/", views.publish_listing, name="publish"),
    path("anuncios/mios/", views.my_listings, name="my_listings"),
    path("anuncios/<int:pk>/favorito/", views.toggle_favorite, name="toggle_favorite"),
    path("anuncios/<int:pk>/eliminar/", views.delete_listing, name="delete"),
    path("anuncios/<int:pk>/<slug:slug>/", views.listing_detail, name="detail"),
    # Categorías con URL limpia: /coches/ /casas/ /terrenos/
    path("<slug:segment>/", views.category_list, name="category"),
]
