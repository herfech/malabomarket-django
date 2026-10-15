from django import forms

from apps.listings.forms import INPUT


class OfficeClientForm(forms.Form):
    """Datos del cliente en nombre del que se publica (no tiene cuenta)."""

    contact_name = forms.CharField(label="Nombre del cliente", max_length=150)
    contact_phone = forms.CharField(label="Teléfono", max_length=30)
    contact_whatsapp = forms.CharField(label="WhatsApp (si es distinto)", max_length=30, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs["class"] = INPUT

    def clean_contact_phone(self):
        value = self.cleaned_data["contact_phone"].strip()
        if sum(c.isdigit() for c in value) < 6:
            raise forms.ValidationError("Escribe un teléfono válido.")
        return value


class RegisterPaymentForm(forms.Form):
    plan = forms.ChoiceField(label="Plan")
    notes = forms.CharField(label="Notas (opcional)", max_length=200, required=False)

    def __init__(self, plans, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].choices = [(p.code, f"{p.name}: {int(p.price):,} XAF, {p.duration_days} días".replace(",", ".")) for p in plans]
        for f in self.fields.values():
            f.widget.attrs["class"] = INPUT
