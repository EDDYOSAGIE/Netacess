from django.utils import timezone
from django.conf import settings
from rest_framework import authentication, exceptions

from .models import AuthToken


class TokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode()
        parts = header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None
        try:
            token = AuthToken.objects.select_related("user").get(key_hash=AuthToken.hash_key(parts[1]))
        except AuthToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid token")
        if not token.user.is_active:
            raise exceptions.AuthenticationFailed("Account disabled")
        now = timezone.now()
        last_used = token.last_used_at or token.created_at
        if (now - last_used).total_seconds() >= settings.AUTH_IDLE_TIMEOUT_SECONDS:
            token.delete()
            raise exceptions.AuthenticationFailed("Session expired. Please sign in again.")
        AuthToken.objects.filter(pk=token.pk).update(last_used_at=now)
        return token.user, token

    def authenticate_header(self, request):
        return self.keyword
