from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_preferred_provider"),
    ]

    operations = [
        migrations.CreateModel(
            name="PolicyAcceptance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("terms_version", models.CharField(max_length=40)),
                ("privacy_version", models.CharField(max_length=40)),
                ("accepted_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="policy_acceptances", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-accepted_at"],
            },
        ),
    ]