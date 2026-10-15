from django.db import migrations

PLANS = [
    ("basico", "Básico", "Publicación estándar", 0, 30, False),
    ("destacado", "Destacado", "Sales por delante de los anuncios básicos", 8000, 30, True),
    ("premium", "Premium", "Máxima visibilidad durante más tiempo", 20000, 60, True),
]


def seed(apps, schema_editor):
    PlanConfig = apps.get_model("office", "PlanConfig")
    for code, name, desc, price, days, featured in PLANS:
        PlanConfig.objects.get_or_create(
            code=code,
            defaults=dict(name=name, description=desc, price=price, duration_days=days, is_featured=featured),
        )


class Migration(migrations.Migration):
    dependencies = [("office", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
