from django.contrib import admin

from .models import AuditLog, Payment, PlanConfig


@admin.register(PlanConfig)
class PlanConfigAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "price", "duration_days", "is_featured", "is_active"]
    list_editable = ["price", "duration_days", "is_active"]

    def has_delete_permission(self, request, obj=None):
        return False  # los planes se desactivan, no se borran


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Solo lectura: los cobros se registran y anulan desde el panel de oficina (con auditoría)."""

    list_display = ["receipt_number", "listing", "plan_name", "amount", "method", "status", "paid_at", "received_by"]
    list_filter = ["status", "method", "plan_code"]
    search_fields = ["receipt_number", "listing__title", "listing__contact_name"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user_label", "action", "listing_id_ref", "payment_id_ref", "detail"]
    list_filter = ["action"]
    search_fields = ["user_label", "detail"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
