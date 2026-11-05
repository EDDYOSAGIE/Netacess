import logging

from django.conf import settings
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuthToken, PolicyAcceptance, User
from apps.accounts.policies import PRIVACY_VERSION, TERMS_VERSION

from .otp import OTPError, PURPOSES, send_otp, verify_otp
from .providers import SMSError, normalize_ng
from .throttles import CacheUnavailable, OTPPhoneIPThrottle

log = logging.getLogger(__name__)


class OTPDataSerializer(serializers.Serializer):
    phone = serializers.CharField()
    purpose = serializers.ChoiceField(choices=PURPOSES, required=False, default="signup")


class OTPVerifySerializer(OTPDataSerializer):
    code = serializers.RegexField(r"^\d{6}$")
    full_name = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(required=False, min_length=8, write_only=True)
    policies_accepted = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs["purpose"] == "signup":
            errors = {}
            if not attrs.get("policies_accepted"):
                errors["policies_accepted"] = "You must agree to the Terms and acknowledge the Privacy Notice."
            if not attrs.get("password"):
                errors["password"] = "A password is required to create an account."
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class OTPSendView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OTPPhoneIPThrottle]

    def post(self, request):
        serializer = OTPDataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["purpose"] == "login":
            try:
                normalized_phone = normalize_ng(data["phone"])
            except SMSError:
                return Response({"error": "invalid_phone", "message": "Enter a valid phone number."}, status=400)
            if not User.objects.filter(phone=f"+{normalized_phone}", is_active=True).exists():
                return Response({
                    "error": "account_not_found",
                    "message": "No active account exists for this phone number.",
                }, status=status.HTTP_404_NOT_FOUND)
        if settings.DEMO_MODE:
            try:
                normalized_phone = normalize_ng(data["phone"])
            except SMSError:
                return Response({"error": "invalid_phone", "message": "Enter a valid phone number."}, status=400)
            if normalized_phone not in settings.DEMO_PHONE_ALLOWLIST:
                return Response({"error": "demo_number_not_allowed", "message": "This demo number is not enabled."}, status=403)
        try:
            code, sms_sent, provider_error = send_otp(
                data["phone"], data["purpose"], request.META.get("REMOTE_ADDR", ""),
            )
        except SMSError as exc:
            message = str(exc)
            throttled = "wait" in message.lower()
            return Response({"error": "sms_unavailable", "message": message},
                            status=status.HTTP_429_TOO_MANY_REQUESTS if throttled else status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            log.error("OTP request infrastructure unavailable (%s)", type(exc).__name__)
            raise CacheUnavailable() from None
        result = {
            "sent": True,
            "sms_sent": sms_sent,
            "expires_in": settings.OTP_TTL_SECONDS,
            "resend_after": settings.OTP_RESEND_SECONDS,
        }
        if not sms_sent:
            log.error("OTP SMS delivery failed: %s", provider_error)
            if not settings.DEMO_MODE:
                return Response({"error": "sms_unavailable", "message": "Could not send SMS right now"},
                                status=status.HTTP_502_BAD_GATEWAY)
        if settings.DEMO_MODE:
            result["code"] = code
        return Response(result, status=status.HTTP_200_OK)


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        login_user = None
        if data["purpose"] == "login":
            try:
                normalized_phone = normalize_ng(data["phone"])
            except SMSError:
                return Response({"error": "invalid_phone", "message": "Enter a valid phone number."}, status=400)
            login_user = User.objects.filter(phone=f"+{normalized_phone}", is_active=True).first()
            if not login_user:
                return Response({
                    "error": "account_not_found",
                    "message": "No active account exists for this phone number.",
                }, status=status.HTTP_404_NOT_FOUND)
        try:
            phone = verify_otp(data["phone"], data["purpose"], data["code"])
        except OTPError:
            return Response({"error": "invalid_code", "message": "The code is invalid or expired."}, status=400)

        e164 = "+" + phone
        if data["purpose"] == "signup":
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    phone=e164, defaults={"full_name": data["full_name"], "email": data["email"]},
                )
                if created:
                    user.set_password(data["password"])
                user.is_phone_verified = True
                fields = ["is_phone_verified"]
                if created:
                    fields.append("password")
                user.save(update_fields=fields)
                PolicyAcceptance.objects.create(
                    user=user,
                    terms_version=TERMS_VERSION,
                    privacy_version=PRIVACY_VERSION,
                )
                token = AuthToken.issue(user)
            return Response({"verified": True, "token": token, "user": {
                "id": str(user.id), "phone": user.phone, "full_name": user.full_name,
            }})
        if data["purpose"] == "login":
            return Response({"verified": True, "token": AuthToken.issue(login_user), "user": {
                "id": str(login_user.id), "phone": login_user.phone, "full_name": login_user.full_name,
            }})
        return Response({"verified": True})

