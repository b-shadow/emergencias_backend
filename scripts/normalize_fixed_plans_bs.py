from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.core.database import SessionLocal
from app.models.subscription_plan import SubscriptionPlan


BS_TO_USD = Decimal("6.96")


def bs_to_usd(bs: Decimal) -> Decimal:
    return (bs / BS_TO_USD).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main() -> None:
    wanted = {
        "BRONCE": ("Plan bronce", "Plan de 30 días", Decimal("30.00"), 30),
        "PLATA": ("Plan plata", "Plan de 60 días", Decimal("55.00"), 60),
        "ORO": ("Plan oro", "Plan de 90 días", Decimal("75.00"), 90),
        "DIAMANTE": ("Plan diamante", "Plan de 180 días", Decimal("140.00"), 180),
    }

    db = SessionLocal()
    try:
        all_plans = db.query(SubscriptionPlan).all()
        for p in all_plans:
            key = (p.codigo_plan or "").upper()
            if key in wanted:
                nombre, desc, bs, dias = wanted[key]
                p.nombre_plan = nombre
                p.descripcion = desc
                p.precio_bs = bs
                p.duracion_dias = dias
                p.precio_mensual_usd = bs_to_usd(bs)
                p.es_activo = True
                print(f"Activo/actualizado: {key}")
            else:
                p.es_activo = False
                print(f"Inactivado: {p.codigo_plan}")
        db.commit()
        print("OK: catálogo de planes normalizado a BRONCE/PLATA/ORO/DIAMANTE.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
