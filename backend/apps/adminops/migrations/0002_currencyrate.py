from decimal import Decimal

from django.db import migrations, models


def create_default_rate(apps, schema_editor):
    CurrencyRate = apps.get_model("adminops", "CurrencyRate")
    CurrencyRate.objects.using(schema_editor.connection.alias).get_or_create(
        pk=1, defaults={"esp_to_ngn": Decimal("4000.0000")},
    )


class Migration(migrations.Migration):
    dependencies = [("adminops", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="CurrencyRate",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("esp_to_ngn", models.DecimalField(decimal_places=4, default=4000, max_digits=16)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(create_default_rate, migrations.RunPython.noop),
    ]