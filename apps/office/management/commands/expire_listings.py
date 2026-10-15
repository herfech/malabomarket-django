from django.core.management.base import BaseCommand

from apps.office.services import expire_due_listings


class Command(BaseCommand):
    help = "Marca como expirados los anuncios cuya fecha de caducidad ya pasó (ejecutar una vez al día)."

    def handle(self, *args, **opts):
        n = expire_due_listings()
        self.stdout.write(self.style.SUCCESS(f"{n} anuncio(s) marcados como expirados."))
