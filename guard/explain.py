# ponytail: plantillas; LLM solo si sobra tiempo.
from decimal import Decimal

from .domain import Extraction
from .engine import Decision


def _money(v) -> str:
    d = Decimal(str(v))
    return f"USD {format(d, ',f')}"


def _raw_money(currency: str, v) -> str:
    return f"{currency} {format(Decimal(str(v)), ',f')}"


def explain(d: Decision, x: Extraction) -> str:
    f = d.facts
    rule = d.rule
    if rule == "R_SOSPECHA":
        return "Escalada: el documento contiene instrucciones sospechosas; una persona debe revisarlo antes de pagar."
    if rule == "R_CONFIANZA":
        if "confianza" in f:
            return f"Escalada: lectura poco confiable (confianza {f['confianza']}); revisar manualmente."
        return f"Escalada: monto leido invalido ({f.get('monto', 'desconocido')}); revisar manualmente."
    if rule == "R_DOBLE_LECTURA":
        return (f"Escalada: la segunda lectura ({f.get('lectura_regex')}) no coincide con lo leido "
                f"por el modelo ({f.get('lectura_llm')}).")
    if rule == "R_MONEDA":
        return f"Frenada: la moneda {f.get('moneda')} no esta entre las permitidas ({f.get('permitidas')})."
    if rule == "R_BENEFICIARIO":
        return f"Escalada: el beneficiario «{f.get('nombre')}» no esta en el registro maestro; darlo de alta primero."
    if rule == "R_CUENTA":
        return (f"Escalada: la cuenta de la factura ({f.get('cuenta_factura')}) no coincide con la cuenta "
                f"registrada ({f.get('cuenta_registrada')}).")
    if rule == "R_DUPLICADO":
        prev = f.get("factura_previa")
        num = f.get("numero_previo") or "sin numero"
        return f"Frenada: parece un duplicado de la factura {prev} (numero {num}); verificar antes de pagar de nuevo."
    if rule == "R_FECHA":
        return (f"Frenada: la fecha {f.get('fecha')} esta fuera de rango (hoy {f.get('hoy')}, "
                f"maximo {f.get('max_dias')} dias de antiguedad).")
    if rule == "R_CONTRATO":
        return (f"Escalada: el monto {_raw_money(f.get('moneda', ''), f.get('monto'))} no coincide con el "
                f"contrato registrado ({_raw_money(f.get('moneda', ''), f.get('contrato'))}).")
    if rule == "R_LIMITE":
        return f"Frenada: {_money(f.get('monto_usd'))} supera el limite por pago de {_money(f.get('limite'))}."
    if rule == "R_UMBRAL":
        return f"Necesita aprobacion: {_money(f.get('monto_usd'))} supera el umbral de {_money(f.get('umbral'))}."
    if rule == "R_PRESUPUESTO":
        return f"Frenada: {_money(f.get('monto_usd'))} supera el presupuesto restante ({_money(f.get('restante'))})."
    if rule == "R_UNICODE":
        return "Escalada: algún campo trae caracteres invisibles, de ancho completo o de otro alfabeto (posible suplantación); revisar manualmente."
    if rule == "R_FRACCIONAMIENTO":
        return (f"Escalada: con los pagos previos del mes a este beneficiario suman {_money(f.get('total_usd'))}, "
                f"sobre el tope de {_money(f.get('tope'))} (posible fraccionamiento).")
    if rule == "R_ERROR":
        return f"Escalada: error interno al evaluar ({f.get('error')}); no se paga hasta revisar."
    if rule == "OK":
        return "Pagable: beneficiario y cuenta registrados, monto igual al contrato, dentro de limites y presupuesto."
    return f"Escalada: regla {rule} sin explicacion predeterminada; revisar manualmente."
