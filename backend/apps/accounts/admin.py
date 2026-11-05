from django.contrib import admin

from .models import PolicyAcceptance


@admin.register(PolicyAcceptance)
class PolicyAcceptanceAdmin(admin.ModelAdmin):
	list_display = ("user", "terms_version", "privacy_version", "accepted_at")
	list_filter = ("terms_version", "privacy_version")
	search_fields = ("user__phone", "user__email")
	readonly_fields = ("user", "terms_version", "privacy_version", "accepted_at")

	def has_add_permission(self, request):
		return False

	def has_change_permission(self, request, obj=None):
		return False
