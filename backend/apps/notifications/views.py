from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "link", "is_read", "created_at"]


class NotificationList(ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user, channel=Notification.IN_APP)

    def list(self, request, *a, **kw):
        resp = super().list(request, *a, **kw)
        resp.data["unread_count"] = self.get_queryset().filter(is_read=False).count()
        return resp


class MarkRead(APIView):
    def post(self, request):
        qs = Notification.objects.filter(user=request.user, is_read=False)
        ids = request.data.get("ids")
        if ids:
            qs = qs.filter(id__in=ids)
        qs.update(is_read=True, read_at=timezone.now())
        return Response({"ok": True})
