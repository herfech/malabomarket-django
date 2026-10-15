"""
Filtros de búsqueda pública. Se validan con un Form de Django: un valor
inválido (ej. "abc" en el precio) se ignora en vez de romper la página,
y nunca se concatena SQL a mano.
"""
from django import forms
from django.db.models import Q

from .models import CarDetails, City, HouseDetails, LandDetails, Listing

ORDER_CHOICES = [
    ("recientes", "Más recientes"),
    ("precio_asc", "Precio: menor a mayor"),
    ("precio_desc", "Precio: mayor a menor"),
]
ORDERING = {
    "recientes": ["-created_at"],
    "precio_asc": ["price", "-created_at"],
    "precio_desc": ["-price", "-created_at"],
}


def _choices(model_choices):
    return [("", "Todos")] + list(model_choices)


class ListingFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=100)
    operacion = forms.ChoiceField(required=False, choices=_choices(Listing.OperationType.choices))
    ciudad = forms.ModelChoiceField(required=False, queryset=City.objects.none())
    precio_min = forms.DecimalField(required=False, min_value=0)
    precio_max = forms.DecimalField(required=False, min_value=0)
    orden = forms.ChoiceField(required=False, choices=ORDER_CHOICES)

    # Coches
    marca = forms.CharField(required=False, max_length=80)
    anio_min = forms.IntegerField(required=False, min_value=1980, max_value=2100)
    anio_max = forms.IntegerField(required=False, min_value=1980, max_value=2100)
    km_max = forms.IntegerField(required=False, min_value=0)
    combustible = forms.ChoiceField(required=False, choices=_choices(CarDetails.FuelType.choices))
    transmision = forms.ChoiceField(required=False, choices=_choices(CarDetails.Transmission.choices))
    condicion = forms.ChoiceField(required=False, choices=_choices(CarDetails.Condition.choices))

    # Casas
    tipo = forms.ChoiceField(required=False, choices=_choices(HouseDetails.PropertyType.choices))
    hab_min = forms.IntegerField(required=False, min_value=0)
    banos_min = forms.IntegerField(required=False, min_value=0)
    amueblado = forms.BooleanField(required=False)
    parqueo = forms.BooleanField(required=False)
    jardin = forms.BooleanField(required=False)

    # Casas y terrenos
    m2_min = forms.DecimalField(required=False, min_value=0)
    m2_max = forms.DecimalField(required=False, min_value=0)

    # Terrenos
    uso = forms.ChoiceField(required=False, choices=_choices(LandDetails.LandUse.choices))
    titulo = forms.BooleanField(required=False)
    cercado = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ciudad"].queryset = City.objects.filter(is_active=True)
        self.fields["ciudad"].empty_label = "Todas"
        placeholders = {
            "q": "Marca, zona, palabra clave…", "precio_min": "Mínimo", "precio_max": "Máximo",
            "anio_min": "Desde", "anio_max": "Hasta", "km_max": "ej. 100000", "marca": "ej. Toyota",
            "hab_min": "Mínimo", "banos_min": "Mínimo", "m2_min": "Mínimo", "m2_max": "Máximo",
        }
        for name, text in placeholders.items():
            self.fields[name].widget.attrs["placeholder"] = text
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "h-4 w-4 rounded border-gray-300"
            else:
                field.widget.attrs["class"] = (
                    "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-navy focus:outline-none"
                )

    def clean(self):
        # Los campos inválidos se descartan en lugar de mostrar error.
        for name in list(self.errors):
            self.cleaned_data.pop(name, None)
        return self.cleaned_data

    def apply(self, qs, category=None):
        d = self.cleaned_data
        if category:
            qs = qs.filter(category=category)

        if d.get("q"):
            for word in d["q"].split()[:6]:
                qs = qs.filter(
                    Q(title__icontains=word)
                    | Q(description__icontains=word)
                    | Q(address_zone__icontains=word)
                    | Q(city__name__icontains=word)
                    | Q(car_details__brand__icontains=word)
                    | Q(car_details__model__icontains=word)
                )
        if d.get("operacion"):
            qs = qs.filter(operation_type=d["operacion"])
        if d.get("ciudad"):
            qs = qs.filter(city=d["ciudad"])
        if d.get("precio_min") is not None:
            qs = qs.filter(price__gte=d["precio_min"])
        if d.get("precio_max") is not None:
            qs = qs.filter(price__lte=d["precio_max"])

        if category == "coche":
            if d.get("marca"):
                qs = qs.filter(car_details__brand__iexact=d["marca"])
            if d.get("anio_min"):
                qs = qs.filter(car_details__year__gte=d["anio_min"])
            if d.get("anio_max"):
                qs = qs.filter(car_details__year__lte=d["anio_max"])
            if d.get("km_max") is not None:
                qs = qs.filter(car_details__mileage_km__lte=d["km_max"])
            if d.get("combustible"):
                qs = qs.filter(car_details__fuel_type=d["combustible"])
            if d.get("transmision"):
                qs = qs.filter(car_details__transmission=d["transmision"])
            if d.get("condicion"):
                qs = qs.filter(car_details__condition=d["condicion"])

        elif category == "casa":
            if d.get("tipo"):
                qs = qs.filter(house_details__property_type=d["tipo"])
            if d.get("hab_min"):
                qs = qs.filter(house_details__bedrooms__gte=d["hab_min"])
            if d.get("banos_min"):
                qs = qs.filter(house_details__bathrooms__gte=d["banos_min"])
            if d.get("amueblado"):
                qs = qs.filter(house_details__is_furnished=True)
            if d.get("parqueo"):
                qs = qs.filter(house_details__has_parking=True)
            if d.get("jardin"):
                qs = qs.filter(house_details__has_garden=True)
            if d.get("m2_min") is not None:
                qs = qs.filter(house_details__area_m2__gte=d["m2_min"])
            if d.get("m2_max") is not None:
                qs = qs.filter(house_details__area_m2__lte=d["m2_max"])

        elif category == "terreno":
            if d.get("uso"):
                qs = qs.filter(land_details__land_use=d["uso"])
            if d.get("titulo"):
                qs = qs.filter(land_details__has_title_deed=True)
            if d.get("cercado"):
                qs = qs.filter(land_details__is_fenced=True)
            if d.get("m2_min") is not None:
                qs = qs.filter(land_details__area_m2__gte=d["m2_min"])
            if d.get("m2_max") is not None:
                qs = qs.filter(land_details__area_m2__lte=d["m2_max"])

        # Los destacados (is_premium) siempre salen primero.
        return qs.order_by("-is_premium", *ORDERING[d.get("orden") or "recientes"])
