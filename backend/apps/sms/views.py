import logging

from django.conf import settings
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.email_otp import EmailOTPError, send_email_otp, verify_email_otp
from apps.accounts.models import AuthToken, PolicyAcceptance, User
from apps.accounts.policies import PRIVACY_VERSION, TERMS_VERSION

from .throttles import CacheUnavailable, OTPEmailIPThrottle

log = logging.getLogger(__name__)


class OTPDataSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    purpose = serializers.ChoiceField(choices=("signup", "login", "reset", "phone_change"), required=False, default="signup")

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        if attrs["purpose"] == "signup" and not attrs.get("phone"):
            raise serializers.ValidationError({"phone": "A phone number is required for payment code delivery."})
        return attrs


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
            if not attrs.get("phone"):
                errors["phone"] = "A phone number is required for payment code delivery."
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class OTPSendView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OTPEmailIPThrottle]

    def post(self, request):
        serializer = OTPDataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["purpose"] == "signup":
            if User.objects.filter(email__iexact=data["email"]).exists():
                return Response({"error": "email_in_use", "message": "An account already uses this email."}, status=400)
            if data.get("phone"):
                from .providers import SMSError, normalize_ng
                try:
                    phone = "+" + normalize_ng(data["phone"])
                except SMSError:
                    return Response({"error": "invalid_phone", "message": "Enter a valid phone number."}, status=400)
                if User.objects.filter(phone=phone).exists():
                    return Response({"error": "phone_in_use", "message": "An account already uses this phone number."}, status=400)
        if data["purpose"] == "login":
            matches = User.objects.filter(email__iexact=data["email"], is_active=True)
            if matches.count() > 1:
                return Response({
                    "error": "email_not_unique",
                    "message": "This email is linked to more than one account. Contact support to update your account email.",
                }, status=status.HTTP_409_CONFLICT)
            if not matches.exists():
                return Response({
                    "error": "account_not_found",
                    "message": "No active account exists for this email.",
                }, status=status.HTTP_404_NOT_FOUND)
        try:
            send_email_otp(data["email"], data["purpose"])
        except EmailOTPError as exc:
            code = status.HTTP_429_TOO_MANY_REQUESTS if exc.code == "too_soon" else status.HTTP_502_BAD_GATEWAY
            return Response({"error": exc.code, "message": exc.message}, status=code)
        except Exception as exc:
            log.error("OTP request infrastructure unavailable (%s)", type(exc).__name__)
            raise CacheUnavailable() from None
        return Response({"sent": True, "expires_in": settings.OTP_TTL_SECONDS,
                         "resend_after": settings.OTP_RESEND_SECONDS}, status=status.HTTP_200_OK)


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
            matches = User.objects.filter(email__iexact=data["email"], is_active=True)
            if matches.count() > 1:
                return Response({
                    "error": "email_not_unique",
                    "message": "This email is linked to more than one account. Contact support to update your account email.",
                }, status=status.HTTP_409_CONFLICT)
            login_user = matches.first()
            if not login_user:
                return Response({
                    "error": "account_not_found",
                    "message": "No active account exists for this email.",
                }, status=status.HTTP_404_NOT_FOUND)
        try:
            verify_email_otp(data["email"], data["purpose"], data["code"])
        except EmailOTPError:
            return Response({"error": "invalid_code", "message": "The code is invalid or expired."}, status=400)

        if data["purpose"] == "signup":
            from .providers import SMSError, normalize_ng
            try:
                e164 = "+" + normalize_ng(data["phone"])
            except SMSError:
                return Response({"error": "invalid_phone", "message": "Enter a valid phone number."}, status=400)
            with transaction.atomic():
                if User.objects.filter(email__iexact=data["email"]).exists() or User.objects.filter(phone=e164).exists():
                    return Response({"error": "account_exists", "message": "An account already uses this email or phone."}, status=400)
                user = User.objects.create_user(
                    e164, data["password"], full_name=data["full_name"], email=data["email"],
                )
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
                "is_staff": login_user.is_staff,
            }})
        return Response({"verified": True})

