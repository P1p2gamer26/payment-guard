from django.db import models


class PolicyVersion(models.Model):
    version = models.IntegerField(unique=True)
    raw = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"v{self.version}"


class Invoice(models.Model):
    invoice_id = models.CharField(max_length=16, unique=True)
    filename = models.CharField(max_length=255)
    text = models.TextField()
    extraction = models.JSONField(null=True, blank=True)
    # quien cargó/solicitó el pago; no puede ser quien lo aprueba (separación de funciones)
    requested_by = models.CharField(max_length=120, default="ap@lumbre.example")

    def __str__(self):
        return self.invoice_id


class DecisionRecord(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="decisions")
    policy_version = models.ForeignKey(PolicyVersion, on_delete=models.CASCADE, related_name="decisions")
    outcome = models.CharField(max_length=16)  # PAGAR | FRENAR | ESCALAR
    rule = models.CharField(max_length=32)
    amount_usd = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    facts = models.JSONField(default=dict)
    explanation = models.TextField()
    second_read = models.JSONField(null=True, blank=True)
    receipt = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("invoice", "policy_version")

    def __str__(self):
        return f"{self.invoice.invoice_id} v{self.policy_version.version}: {self.outcome}"


class Approval(models.Model):
    OUTCOMES = (("APROBADO", "Aprobado"), ("RECHAZADO", "Rechazado"))
    decision = models.OneToOneField(DecisionRecord, on_delete=models.CASCADE, related_name="approval")
    outcome = models.CharField(max_length=16, choices=OUTCOMES)
    note = models.TextField()
    approver = models.CharField(max_length=255)
    draft = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.decision} -> {self.outcome}"


class ExtractionCorrection(models.Model):
    """Corrección humana de un campo extraído: quién, qué cambió y por qué (auditoría)."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="corrections")
    field = models.CharField(max_length=32)
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    actor = models.CharField(max_length=120)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice.invoice_id}.{self.field}: «{self.old_value}» -> «{self.new_value}»"


class UsedNonce(models.Model):
    nonce = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(auto_now_add=True)


class ArenaRun(models.Model):
    policy_version = models.ForeignKey(PolicyVersion, on_delete=models.CASCADE, related_name="arena_runs")
    total = models.IntegerField()
    indebidos = models.IntegerField()
    por_categoria = models.JSONField(default=dict)
    ejemplos = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class Event(models.Model):
    KIND_CHOICES = [
        ("decision", "Decisión"),
        ("aprobacion", "Aprobación"),
        ("rechazo", "Rechazo"),
        ("correccion", "Corrección"),
        ("arena", "Arena"),
        ("prueba", "Prueba"),
    ]
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    invoice_id = models.CharField(max_length=16, blank=True)
    outcome = models.CharField(max_length=10, blank=True)
    rule = models.CharField(max_length=32, blank=True)
    amount_usd = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    message = models.CharField(max_length=240, blank=True)
    policy_version = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.kind}] {self.invoice_id or '—'} {self.outcome or self.message}"
