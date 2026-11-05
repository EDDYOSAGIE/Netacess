import math

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subscription


class MeView(APIView):
    def patch(self, request):
        pref = request.data.get("preferred_provider")
        if pref not in ("flutterwave", "espees"):
            return Response({"error": "invalid", "message": "Choose Flutterwave or Espees."}, status=400)
        request.user.preferred_provider = pref
        request.user.save(update_fields=["preferred_provider"])
        return self.get(request)

    def get(self, request):
        u = request.user
        now = timezone.now()
        sub = (Subscription.objects.filter(user=u, status=Subscription.ACTIVE, expires_at__gt=now)
               .select_related("plan").order_by("-expires_at").first())
        subscription = None
        if sub:
            subscription = {"plan": sub.plan.name, "plan_code": sub.plan.code, "starts_at": sub.starts_at,
                            "expires_at": sub.expires_at, "days_left": max(math.ceil((sub.expires_at - now).total_seconds() / 86400), 0),
                            "is_recurring": sub.plan.is_recurring}
        from apps.payments.models import Payment
        pref = u.preferred_provider
        if not pref:  # default to whatever they paid with last
            last = Payment.objects.filter(order__user=u, status=Payment.SUCCESSFUL).order_by("-created_at").first()
            pref = last.provider if last else ""
        return Response({"id": str(u.id), "is_staff": u.is_staff, "preferred_provider": pref, "phone": u.phone, "full_name": u.full_name, "email": u.email,
                         "subscription": subscription})
