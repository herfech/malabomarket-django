from django.urls import path

from . import views

app_name = "office"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("publicar/", views.publish_start, name="publish_start"),
    path("publicar/<str:category>/", views.publish, name="publish"),
    path("cobros/", views.payments, name="payments"),
    path("cobros/<int:pk>/confirmar/", views.confirm_payment, name="confirm_payment"),
    path("cobros/<int:pk>/anular/", views.void_payment, name="void_payment"),
    path("recibo/<int:pk>/", views.receipt, name="receipt"),
    path("anuncios/", views.listings, name="listings"),
    path("anuncios/<int:pk>/", views.listing_manage, name="listing"),
    path("auditoria/", views.audit, name="audit"),
]
