from django.contrib import admin, messages

from apps.access_codes.models import AccessCode

from .models import Payment, PaymentEvent
from .providers.base import ProviderError
from .services import admin_approve, admin_mark, check_payment


class EventInline(admin.TabularInline):
    model = PaymentEvent
    extra = 0
    can_delete = False
    readonly_fields = ("source", "event_type", "event_id", "payload", "received_at")
    has_add_permission = lambda self, request, obj=None: False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "amount", "currency", "status", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("id", "provider_reference", "order__user__phone")
    readonly_fields = [f.name for f in Payment._meta.fields]  # status only changes through the actions below
    inlines = [EventInline]
    actions = ["recheck", "approve", "mark_failed", "mark_refunded"]
    has_add_permission = lambda self, request: False

    def _run(self, request, qs, fn, label):
        ok = bad = 0
        for p in qs:
            try:
                fn(p)
                ok += 1
            except (ValueError, ProviderError) as e:
                bad += 1
                self.message_user(request, f"{p.id}: {e}", messages.WARNING)
        self.message_user(request, f"{label}: {ok} done, {bad} skipped")

    @admin.action(description="Re-check with the provider")
    def recheck(self, request, qs):
        self._run(request, qs, lambda p: check_payment(p.id, "admin"), "Re-check")

    @admin.action(description="Approve: money received, issue the access code")
    def approve(self, request, qs):
        self._run(request, qs, lambda p: admin_approve(p.id, request.user), "Approve")

    @admin.action(description="Mark as failed")
    def mark_failed(self, request, qs):
        self._run(request, qs, lambda p: admin_mark(p.id, Payment.FAILED, request.user), "Mark failed")

    @admin.action(description="Mark as refunded")
    def mark_refunded(self, request, qs):
        self._run(request, qs, lambda p: admin_mark(p.id, Payment.REFUNDED, request.user), "Mark refunded")


@admin.register(AccessCode)
class AccessCodeAdmin(admin.ModelAdmin):
    list_display = ("plan_code", "status", "created_at")
    exclude = ("code_encrypted",)  # staff never see the raw code
