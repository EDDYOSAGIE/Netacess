import hashlib
import secrets
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        if not phone:
            raise ValueError("Phone number is required")
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_phone_verified", True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True)  # E.164, e.g. +2348012345678
    email = models.EmailField(blank=True)
    full_name = models.CharField(max_length=120, blank=True)
    is_phone_verified = models.BooleanField(default=False)
    preferred_provider = models.CharField(max_length=16, blank=True)  # renewal payment method
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return self.phone


class PhoneOTP(models.Model):
    """SMS code. Only a hash is stored."""
    phone = models.CharField(max_length=20, db_index=True)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["phone", "-created_at"])]


class AuthToken(models.Model):
    """Bearer token. Only the SHA-256 of the key is stored."""
    key_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def hash_key(key):
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def issue(cls, user):
        key = secrets.token_urlsafe(32)
        cls.objects.create(key_hash=cls.hash_key(key), user=user)
        return key


class PolicyAcceptance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="policy_acceptances")
    terms_version = models.CharField(max_length=40)
    privacy_version = models.CharField(max_length=40)
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-accepted_at"]
