from django.core.management.base import BaseCommand

from guard import arena
from guard.data import load_policy
from guard.domain import Policy
from guard.services import mandato_v2


class Command(BaseCommand):
    help = "Corre la arena de ataques contra el mandato v1 y v2 (política de data/reglas.json)."

    def handle(self, *args, **opts):
        base = load_policy().raw
        for nombre, raw in (("v1 (base)", base), ("v2 (anti-fraccionamiento + unicode)", mandato_v2(base))):
            r = arena.run(Policy(raw))
            self.stdout.write(f"\nMandato {nombre}: {r.total} ataques, {r.indebidos} pagos indebidos")
            for cat, c in r.por_categoria.items():
                self.stdout.write(f"  {cat:16} {c['indebidos']:>4} / {c['n']}")
            for e in r.ejemplos[:5]:
                self.stdout.write(f"    ej: {e}")
