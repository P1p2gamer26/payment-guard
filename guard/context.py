from .models import DecisionRecord, PolicyVersion


def shell(request):
    """Datos del app shell: política vigente y escaladas pendientes (contador de la barra lateral)."""
    pv = PolicyVersion.objects.order_by("-version").first()
    pend = 0 if pv is None else DecisionRecord.objects.filter(
        policy_version=pv, outcome="ESCALAR", approval__isnull=True).count()
    return {"nav_pendientes": pend, "nav_pv": pv.version if pv else 1}
