from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AccessCode
from .services import decrypt


class MyCodesView(APIView):
    def get(self, request):
        codes = (AccessCode.objects.filter(subscription__user=request.user)
                 .select_related("subscription").order_by("-created_at"))
        return Response([{"code": decrypt(c), "plan": c.plan_code, "status": c.status,
                          "expires_at": c.subscription.expires_at} for c in codes])
