"""
Pasarela de pago con tarjeta (punto de enganche).

Hoy el cobro es en efectivo en la oficina. Cuando un comprador del software
contrate una pasarela (Stripe, Paystack, Flutterwave, una local...), se escribe
UNA clase que herede de `PaymentGateway` y se activa con la variable de entorno
PAYMENT_GATEWAY="apps.office.gateway.MiPasarela". El resto de la aplicación no cambia:
al confirmarse el cobro se llama a `services.confirm_payment(payment, by_user=None)`.
"""
from django.conf import settings
from django.utils.module_loading import import_string


class PaymentGateway:
    name = "base"

    def create_checkout(self, payment, return_url):
        """Devuelve la URL a la que enviar al cliente para pagar `payment` con tarjeta."""
        raise NotImplementedError

    def parse_webhook(self, request):
        """Valida la firma del aviso de la pasarela y devuelve el Payment pagado (o None)."""
        raise NotImplementedError


def get_gateway():
    path = getattr(settings, "PAYMENT_GATEWAY", "")
    return import_string(path)() if path else None
