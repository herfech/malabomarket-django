from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.cache import cache

from .models import User

INPUT_CLASSES = "w-full rounded-lg border border-sand-200 bg-white px-3.5 py-2.5 text-[0.95rem] text-charcoal placeholder:text-charcoal/40 focus:border-navy focus:outline-none"


class SignUpForm(UserCreationForm):
    """
    Registro público. El rol siempre nace como "cliente" (default del
    modelo); nadie puede auto-asignarse "personal_oficina" o
    "administrador" desde este formulario.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "full_name", "phone")

    # Trampa para bots: un campo oculto que una persona nunca rellena.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        "tabindex": "-1", "autocomplete": "off", "aria-hidden": "true",
        "style": "position:absolute;left:-9999px;width:1px;height:1px;",
    }))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "website":
                field.widget.attrs["class"] = INPUT_CLASSES

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("No se pudo completar el registro.")
        return ""


MAX_LOGIN_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60


class LoginForm(AuthenticationForm):
    """Bloquea 15 min tras 5 intentos fallidos con el mismo correo desde la misma IP."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASSES

    def _throttle_key(self):
        ip = (self.request.META.get("REMOTE_ADDR") if self.request else "") or "?"
        email = (self.data.get("username") or "").strip().lower()
        return f"login-fail:{ip}:{email}"

    def clean(self):
        key = self._throttle_key()
        if cache.get(key, 0) >= MAX_LOGIN_FAILURES:
            raise forms.ValidationError("Demasiados intentos. Espera 15 minutos y vuelve a probar.", code="locked")
        try:
            result = super().clean()
        except forms.ValidationError:
            try:
                cache.add(key, 0, LOGIN_LOCK_SECONDS)
                cache.incr(key)
            except ValueError:
                pass
            raise
        cache.delete(key)
        return result
