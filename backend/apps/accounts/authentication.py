from django.utils import timezone
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
        AuthToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
        return token.user, token

    def authenticate_header(self, request):
        return self.keyword
