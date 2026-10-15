from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import SignUpForm


class RegisterView(CreateView):
    form_class = SignUpForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("listings:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)  # inicia sesión automáticamente al registrarse
        return response
