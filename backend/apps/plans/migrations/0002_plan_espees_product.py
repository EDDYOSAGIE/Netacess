from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plans", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="plan",
            name="code",
            field=models.CharField(max_length=16, unique=True),
        ),
        migrations.AddField(
            model_name="plan",
            name="espees_product_sku",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="plan",
            name="espees_payment_ref",
            field=models.CharField(blank=True, max_length=128),
        ),
    ]