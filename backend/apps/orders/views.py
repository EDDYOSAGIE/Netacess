from rest_framework import serializers
from rest_framework.generics import ListAPIView

from apps.payments.models import Payment


class TransactionSerializer(serializers.ModelSerializer):
    plan = serializers.CharField(source="order.plan.name")

    class Meta:
        model = Payment
        fields = ["id", "plan", "provider", "amount", "currency", "status", "created_at",
              "card_brand", "card_last4"]


class TransactionList(ListAPIView):
    """Profile transaction history. Filter with ?status=SUCCESSFUL or ?status=FAILED."""
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = Payment.objects.filter(order__user=self.request.user).select_related("order__plan")
        st = self.request.query_params.get("status")
        return qs.filter(status=st.upper()) if st else qs
