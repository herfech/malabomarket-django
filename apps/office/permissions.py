from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import Http404


def staff_required(view):
    """Solo personal de oficina o administrador. Cualquier otro usuario ve un 404 (no se revela que el panel existe)."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_office_staff:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_platform_admin:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapper
