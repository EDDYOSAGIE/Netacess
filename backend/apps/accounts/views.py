from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .email_otp import EmailOTPError, send_email_otp, verify_email_otp
from .models import AuthToken, PolicyAcceptance, User
from .policies import PRIVACY_VERSION, TERMS_VERSION


class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(choices=("signup", "login"))
    phone = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        attrs["email"] = attrs["email"].strip().lower()
        if attrs["purpose"] == "signup" and not attrs.get("phone"):
            raise serializers.ValidationError({"phone": "This field is required for signup."})
        return attrs


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(choices=("signup", "login"))
    phone = serializers.CharField(required=False, allow_blank=True)
    code = serializers.RegexField(r"^\d{6}$")
    full_name = serializers.CharField(required=False, allow_blank=True, default="")
    password = serializers.CharField(required=False, min_length=8, write_only=True)
    policies_accepted = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        attrs["email"] = attrs["email"].strip().lower()
        if attrs["purpose"] == "signup":
            if not attrs.get("phone"):
                raise serializers.ValidationError({"phone": "This field is required for signup."})
            if not attrs.get("password"):
                raise serializers.ValidationError({"password": "This field is required for signup."})
        return attrs


def _err(code, message, status_code=400):
    return Response({"error": code, "message": message}, status=status_code)


def _email_matches(email):
    return User.objects.filter(email__iexact=email)


class OTPRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "otp"

    def post(self, request):
        s = OTPRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        email = data["email"]
        purpose = data["purpose"]
        try:
            if purpose == "signup":
                phone = services.normalize_phone(data["phone"])
                if _email_matches(email).exists():
                    return _err("email_in_use", "An account already uses this email address.")
            else:
                matches = _email_matches(email)
                if not matches.exists():
                    return _err("account_not_found", "No account was found for this email.", 404)
                if matches.count() > 1:
                    return _err("email_not_unique", "More than one account uses this email address.", 409)
            send_email_otp(email, purpose)
        except services.OTPError as e:
            return _err(e.code, e.message)
        except EmailOTPError as e:
            status_code = 429 if e.code == "too_soon" else 502
            return _err(e.code, e.message, status_code)
        return Response({"sent": True, "expires_in": 300, "resend_after": 60})


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = OTPVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        email = d["email"]
        purpose = d["purpose"]
        try:
            if purpose == "login":
                matches = _email_matches(email)
                if not matches.exists():
                    return _err("account_not_found", "No account was found for this email.", 404)
                if matches.count() > 1:
                    return _err("email_not_unique", "More than one account uses this email address.", 409)
                verify_email_otp(email, purpose, d["code"])
                user = matches.first()
                token = AuthToken.issue(user)
            else:
                phone = services.normalize_phone(d["phone"])
                if not d["policies_accepted"]:
                    return _err("policies_required", "Accept the Terms of Service and Privacy Notice to continue.")
                if _email_matches(email).exists():
                    return _err("email_in_use", "An account already uses this email address.")
                if User.objects.filter(phone=phone).exists():
                    return _err("account_exists", "An account already uses this phone number.")
                verify_email_otp(email, purpose, d["code"])
                user = User.objects.create_user(
                    phone,
                    d["password"],
                    email=email,
                    full_name=d["full_name"],
                )
                PolicyAcceptance.objects.create(
                    user=user,
                    terms_version=TERMS_VERSION,
                    privacy_version=PRIVACY_VERSION,
                )
                token = AuthToken.issue(user)
        except services.OTPError as e:
            return _err(e.code, e.message)
        except EmailOTPError as e:
            return _err(e.code, e.message)
        return Response({"token": token, "user": {"id": str(user.id), "phone": user.phone,
                                                  "full_name": user.full_name, "is_staff": user.is_staff}},
                        status=status.HTTP_200_OK)
