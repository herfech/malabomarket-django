from django import forms

from .models import CarDetails, HouseDetails, LandDetails, Listing

INPUT = "w-full rounded-lg border border-sand-200 bg-white px-3.5 py-2.5 text-[0.95rem] text-charcoal placeholder:text-charcoal/40 focus:border-navy focus:outline-none"
CHECK = "h-4 w-4 rounded border-gray-300 text-navy"


class StyledModelForm(forms.ModelForm):
    """Aplica clases de Tailwind a cada campo automáticamente, para no
    repetir `widget=forms.X(attrs={"class": ...})` en cada uno."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (
                f"{existing} {CHECK}".strip() if isinstance(field.widget, forms.CheckboxInput) else INPUT
            )


class ListingForm(StyledModelForm):
    """
    Datos comunes a las 3 categorías. "category" no se expone aquí — la
    fija la URL (/anuncios/publicar/coche/, etc.), así el usuario no
    puede enviarla manipulada desde el HTML.
    """

    class Meta:
        model = Listing
        fields = ["operation_type", "title", "description", "price", "city", "address_zone"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class CarDetailsForm(StyledModelForm):
    class Meta:
        model = CarDetails
        exclude = ["listing"]


class HouseDetailsForm(StyledModelForm):
    class Meta:
        model = HouseDetails
        exclude = ["listing"]


class LandDetailsForm(StyledModelForm):
    class Meta:
        model = LandDetails
        exclude = ["listing"]


DETAIL_FORM_BY_CATEGORY = {
    Listing.Category.COCHE: CarDetailsForm,
    Listing.Category.CASA: HouseDetailsForm,
    Listing.Category.TERRENO: LandDetailsForm,
}
