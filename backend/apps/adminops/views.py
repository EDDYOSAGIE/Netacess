from datetime import timedelta
from decimal import Decimal
import re
import secrets

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.models import Payment
from apps.payments.providers import breaker
from apps.payments.providers.base import ProviderError
from apps.payments.services import admin_approve, admin_mark, check_payment
from apps.payments.providers.espees import EspeesAdapter
from apps.plans.models import Plan, Subscription

from . import providers
from .models import AuditLog, CurrencyRate


class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


def _issue(p):
    """Why a payment is in the review queue, from its event log."""
    ev = p.events.filter(event_type="amount_mismatch").order_by("-received_at").first()
    if ev:
        got = ev.payload.get("got")
        cur = ev.payload.get("currency") or p.currency
        kind = "Currency mismatch" if cur != p.currency else "Amount mismatch"
        return kind, f"{got} {cur}"
    return "Held for review", None


class AdminPaymentSerializer(serializers.ModelSerializer):
    user_phone = serializers.CharField(source="order.user.phone")
    plan = serializers.CharField(source="order.plan.name")
    issue = serializers.SerializerMethodField()
    received = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["id", "provider_reference", "user_phone", "plan", "provider", "amount", "currency",
                  "status", "created_at", "issue", "received"]

    def get_issue(self, p):
        return _issue(p)[0] if p.status == Payment.NEEDS_REVIEW else None

    def get_received(self, p):
        return _issue(p)[1] if p.status == Payment.NEEDS_REVIEW else None


class Summary(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        now = timezone.now()
        day = now - timedelta(hours=24)
        paid_today = Payment.objects.filter(status=Payment.SUCCESSFUL, created_at__gte=day)
        revenue = {}
        for row in paid_today.values("currency").annotate(t=Sum("amount")):
            revenue[row["currency"]] = str(row["t"])
        week = Payment.objects.filter(created_at__gte=now - timedelta(days=7)).aggregate(
            ok=Count("id", filter=Q(status=Payment.SUCCESSFUL)),
            done=Count("id", filter=Q(status__in=[Payment.SUCCESSFUL, Payment.FAILED, Payment.EXPIRED])))
        rate = round(100 * week["ok"] / week["done"], 1) if week["done"] else None
        return Response({
            "revenue_today": revenue,
            "active_subscribers": Subscription.objects.filter(status="ACTIVE", expires_at__gt=now)
            .values("user").distinct().count(),
            "success_rate_7d": rate,
            "needs_review": Payment.objects.filter(status=Payment.NEEDS_REVIEW).count(),
            "providers": [{"name": n, "enabled": providers.is_enabled(n), "degraded": breaker.is_open(n)}
                          for n in providers.NAMES],
        })


class PaymentList(ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = AdminPaymentSerializer

    def get_queryset(self):
        qs = Payment.objects.select_related("order__user", "order__plan")
        g = self.request.query_params
        if g.get("status"):
            qs = qs.filter(status=g["status"].upper())
        if g.get("provider"):
            qs = qs.filter(provider=g["provider"])
        if g.get("q"):
            q = g["q"].strip()
            qs = qs.filter(Q(provider_reference__icontains=q) | Q(order__user__phone__icontains=q) | Q(id__startswith=q))
        return qs


class PaymentDetail(APIView):
    permission_classes = [IsStaff]

    def get(self, request, pk):
        p = get_object_or_404(Payment.objects.select_related("order__user", "order__plan"), pk=pk)
        data = AdminPaymentSerializer(p).data
        data["events"] = [{"source": e.source, "event_type": e.event_type, "payload": e.payload,
                           "received_at": e.received_at} for e in p.events.order_by("received_at")]
        data["issue"], data["received"] = _issue(p) if p.status == Payment.NEEDS_REVIEW else (None, None)
        data["has_code"] = hasattr(p, "access_code")
        return Response(data)


class PaymentAction(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk):
        action = request.data.get("action")
        reason = (request.data.get("reason") or "").strip()
        if action not in ("recheck", "approve", "fail", "refund"):
            return Response({"error": "bad_action", "message": "Unknown action."}, status=400)
        if action != "recheck" and len(reason) < 3:
            return Response({"error": "reason_required", "message": "Write a short reason. It is saved to the audit log."}, status=400)
        get_object_or_404(Payment, pk=pk)
        try:
            if action == "recheck":
                check_payment(pk, "admin")
            elif action == "approve":
                admin_approve(pk, request.user, reason)
            elif action == "fail":
                admin_mark(pk, Payment.FAILED, request.user, reason)
            else:
                admin_mark(pk, Payment.REFUNDED, request.user, reason)
        except ProviderError as e:
            return Response({"error": "provider_error", "message": f"Could not reach the provider: {e}"}, status=502)
        except ValueError as e:
            return Response({"error": "not_allowed", "message": str(e)}, status=409)
        AuditLog.objects.create(actor=request.user, action=action, target_type="payment",
                                target_id=str(pk), reason=reason or "Re-check")
        return PaymentDetail().get(request, pk)


class ProviderToggle(APIView):
    permission_classes = [IsStaff]

    def post(self, request, name):
        if name not in providers.NAMES:
            return Response(status=404)
        enabled = bool(request.data.get("enabled"))
        from django.conf import settings
        if name == "espees" and enabled and not settings.ESPEES_CHECKOUT_READY:
            return Response({"error": "integration_incomplete", "message": "Espees checkout is not ready for customers yet."}, status=409)
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 3:
            return Response({"error": "reason_required", "message": "Write a short reason. It is saved to the audit log."}, status=400)
        providers.set_enabled(name, enabled)
        AuditLog.objects.create(actor=request.user, action="provider_on" if enabled else "provider_off",
                                target_type="provider", target_id=name, reason=reason)
        return Response({"name": name, "enabled": enabled})


class CurrencyRateView(APIView):
    permission_classes = [IsStaff]

    class RateSerializer(serializers.Serializer):
        esp_to_ngn = serializers.DecimalField(
            max_digits=16, decimal_places=4, min_value=Decimal("0.0001"),
        )

    def get(self, request):
        rate = CurrencyRate.current()
        return Response({"esp_to_ngn": rate.esp_to_ngn, "updated_at": rate.updated_at})

    def patch(self, request):
        serializer = self.RateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rate = CurrencyRate.current()
        rate.esp_to_ngn = serializer.validated_data["esp_to_ngn"]
        rate.save(update_fields=["esp_to_ngn", "updated_at"])
        AuditLog.objects.create(
            actor=request.user, action="currency_rate_updated", target_type="currency_rate",
            target_id="esp_to_ngn", reason=f"Updated to NGN {rate.esp_to_ngn} per ESP",
        )
        return Response({"esp_to_ngn": rate.esp_to_ngn, "updated_at": rate.updated_at})


class AdminPlanSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)

    class Meta:
        model = Plan
        fields = ["id", "code", "name", "price_ngn_kobo", "price_esp", "is_recurring",
                  "duration_days", "is_active", "espees_product_sku", "espees_payment_ref"]
        read_only_fields = ["id", "espees_product_sku", "espees_payment_ref"]


class AdminPlanListCreate(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        plans = Plan.objects.all().order_by("code")
        return Response(AdminPlanSerializer(plans, many=True).data)

    def post(self, request):
        serializer = AdminPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        base = re.sub(r"[^A-Z0-9]+", "_", serializer.validated_data["name"].upper()).strip("_")[:9] or "PLAN"
        for _ in range(5):
            code = f"{base}_{secrets.token_hex(3).upper()}"
            if not Plan.objects.filter(code=code).exists():
                plan = serializer.save(code=code)
                break
        else:
            return Response({"error": "code_generation_failed", "message": "Could not generate a plan identifier."}, status=503)
        AuditLog.objects.create(actor=request.user, action="plan_created", target_type="plan",
                                target_id=str(plan.pk), reason="Created through staff plan manager")
        return Response(AdminPlanSerializer(plan).data, status=201)


class AdminPlanDetail(APIView):
    permission_classes = [IsStaff]

    def patch(self, request, pk):
        plan = get_object_or_404(Plan, pk=pk)
        serializer = AdminPlanSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        AuditLog.objects.create(actor=request.user, action="plan_updated", target_type="plan",
                                target_id=str(plan.pk), reason="Updated through staff plan manager")
        return Response(AdminPlanSerializer(plan).data)


class EspeesPlanProduct(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk):
        plan = get_object_or_404(Plan, pk=pk)
        try:
            sku, ref = EspeesAdapter().create_plan_product(plan)
        except ProviderError as e:
            return Response({"error": "provider_error", "message": str(e)}, status=502)
        plan.espees_product_sku = sku
        plan.espees_payment_ref = ref
        plan.save(update_fields=["espees_product_sku", "espees_payment_ref"])
        AuditLog.objects.create(actor=request.user, action="espees_product_created", target_type="plan",
                                target_id=str(plan.pk), reason=f"Created Espees product {sku}")
        return Response(AdminPlanSerializer(plan).data)


class PublicProviders(APIView):
    """Checkout uses this to hide a provider that has been switched off."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({n: providers.is_enabled(n) for n in providers.NAMES})


class AuditSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.full_name")
    actor_phone = serializers.CharField(source="actor.phone")

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "actor_phone", "action", "target_type", "target_id", "reason", "created_at"]


class AuditList(ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = AuditSerializer
    queryset = AuditLog.objects.select_related("actor")
