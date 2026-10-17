from django.core.management.base import BaseCommand

from guard.data import DATA
from guard.extractor import extract


class Command(BaseCommand):
    help = "Extrae campos de data/facturas/* con el modo actual (DECISION_MODE) y los imprime."

    def handle(self, *args, **options):
        base = DATA / "facturas"
        for path in sorted(base.iterdir()):
            text = path.read_text(encoding="utf-8")
            x = extract(text)
            self.stdout.write(f"{path.stem}\t{x.amount}\t{x.currency}\t{x.confidence}")
