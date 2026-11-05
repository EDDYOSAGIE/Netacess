from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from .models import Plan


class PlanSerializer(serializers.ModelSerializer):
    price_esp_ngn_kobo = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = ["id", "code", "name", "price_ngn_kobo", "price_esp", "price_esp_ngn_kobo",
                  "is_recurring", "duration_days"]

    def get_price_esp_ngn_kobo(self, plan):
        from apps.adminops.models import CurrencyRate

        rate = CurrencyRate.current().esp_to_ngn
        return (plan.price_esp * rate * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


class PlanList(ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PlanSerializer
    pagination_class = None
    queryset = Plan.objects.filter(is_active=True).order_by("price_ngn_kobo")
