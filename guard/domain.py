from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class Extraction:
    invoice_id: str
    beneficiary_name: str
    beneficiary_id: str | None
    amount: Decimal
    currency: str
    issue_date: date | None
    invoice_number: str
    bank_account: str
    concept: str
    confidence: float = 1.0
    suspicious: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Extraction":
        return cls(
            invoice_id=str(d["invoice_id"]),
            beneficiary_name=d.get("beneficiary_name") or "",
            beneficiary_id=d.get("beneficiary_id"),
            amount=Decimal(str(d["amount"])),
            currency=d["currency"].upper(),
            issue_date=date.fromisoformat(d["issue_date"]) if d.get("issue_date") else None,
            invoice_number=d.get("invoice_number") or "",
            bank_account=d.get("bank_account") or "",
            concept=d.get("concept") or "",
            confidence=float(d.get("confidence", 1.0)),
            suspicious=bool(d.get("suspicious", False)),
        )


@dataclass
class Policy:
    raw: dict
    version: int = 1

    @property
    def _r(self):
        return self.raw["reglas_pago"]

    @property
    def per_payment_limit_usd(self) -> Decimal:
        return Decimal(str(self._r["limite_por_pago_usd"]))

    @property
    def approval_threshold_usd(self) -> Decimal:
        return Decimal(str(self._r["umbral_aprobacion_humana_usd"]))

    @property
    def period_budget_remaining_usd(self) -> Decimal:
        return Decimal(str(self.raw["presupuesto"]["restante_inicial_usd"]))

    @property
    def allowed_currencies(self) -> set[str]:
        return set(self._r["monedas_permitidas"])

    @property
    def fx(self) -> dict[str, Decimal]:
        return {k: Decimal(str(v)) for k, v in self._r["tipos_cambio_a_usd"].items()}

    @property
    def anti_fraccionamiento(self) -> bool:
        return bool(self._r.get("anti_fraccionamiento", False))  # mandato v2

    @property
    def normalizar_unicode(self) -> bool:
        return bool(self._r.get("normalizar_unicode", False))  # mandato v2

    @property
    def contract_tolerance_pct(self) -> Decimal:
        return Decimal(str(self._r["tolerancia_monto_contrato_pct"]))

    @property
    def max_age_days(self) -> int:
        return int(self._r["fecha"]["antiguedad_maxima_dias"])

    @property
    def today(self) -> date:
        return date.fromisoformat(self.raw["periodo"]["fecha_hoy"])

    @property
    def beneficiaries(self) -> dict[str, dict]:
        return {b["id"]: b for b in self.raw["beneficiarios_permitidos"]}
