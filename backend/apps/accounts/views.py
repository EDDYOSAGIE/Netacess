from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField()


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.RegexField(r"^\d{6}$")
    full_name = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(required=False, min_length=8, write_only=True)


def _err(e):
    codes = {"rate_limited": 429, "too_soon": 429, "too_many_attempts": 429}
    return Response({"error": e.code, "message": e.message}, status=codes.get(e.code, 400))


class OTPRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "otp"

    def post(self, request):
        s = OTPRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            phone = services.normalize_phone(s.validated_data["phone"])
            services.request_otp(phone, ip=request.META.get("REMOTE_ADDR"))
        except services.OTPError as e:
            return _err(e)
        return Response({"sent": True, "expires_in": 300, "resend_after": 60})


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = OTPVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            phone = services.normalize_phone(d["phone"])
            user, token = services.verify_otp(phone, d["code"], d["full_name"], d["email"], d.get("password"))
        except services.OTPError as e:
            return _err(e)
        return Response({"token": token, "user": {"id": str(user.id), "phone": user.phone,
                                                  "full_name": user.full_name}}, status=status.HTTP_200_OK)
