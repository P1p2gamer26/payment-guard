import pytest

from guard import arena
from guard.data import load_expected, load_gold, load_policy
from guard.domain import Policy
from guard.engine import run_batch
from guard.models import ArenaRun, PolicyVersion
from guard.services import mandato_v2


def test_arena_v1_finds_holes():
    r = arena.run(load_policy())
    assert r.total > 100 and r.indebidos >= 1
    assert {"fraccionamiento", "unicode", "duplicado", "inyeccion"} <= {c for c, v in r.por_categoria.items() if v["indebidos"]}


def test_arena_v2_closes_them():
    r = arena.run(Policy(mandato_v2(load_policy().raw), 2))
    assert r.indebidos == 0, r.ejemplos


def test_golden_still_25_under_v2():
    got = {d.invoice_id: d.outcome for d in run_batch(load_gold(), Policy(mandato_v2(load_policy().raw), 2))}
    assert got == load_expected()


def test_v1_policy_has_no_flags():
    assert not load_policy().anti_fraccionamiento and not load_policy().normalizar_unicode


@pytest.mark.django_db
def test_board_arena_and_mandato_v2(client):
    client.get("/")
    client.post("/arena/correr/")
    assert ArenaRun.objects.latest("id").indebidos > 0
    html = client.get("/").content.decode()
    assert "pagos indebidos de" in html
    client.post("/reglas/mandato-v2/")
    assert PolicyVersion.objects.order_by("-version").first().raw["reglas_pago"]["normalizar_unicode"] is True
    client.post("/arena/correr/")
    assert "Arena: 0 pagos indebidos de" in client.get("/").content.decode()
