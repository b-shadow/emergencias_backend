from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.core.database import SessionLocal
from app.models.subscription_plan import SubscriptionPlan


BS_TO_USD = Decimal("6.96")


def bs_to_usd(bs: Decimal) -> Decimal:
    return (bs / BS_TO_USD).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main() -> None:
    plans = [
        ("BRONCE", "Plan bronce", "Plan de 30 dias", Decimal("30.00"), 30),
        ("PLATA", "Plan plata", "Plan de 60 dias", Decimal("55.00"), 60),
        ("ORO", "Plan oro", "Plan de 90 dias", Decimal("75.00"), 90),
        ("DIAMANTE", "Plan diamante", "Plan de 180 dias", Decimal("140.00"), 180),
    ]

    db = SessionLocal()
    try:
        for codigo, nombre, descripcion, precio_bs, duracion_dias in plans:
            usd = bs_to_usd(precio_bs)
            item = db.query(SubscriptionPlan).filter(SubscriptionPlan.codigo_plan == codigo).first()
            if item:
                item.nombre_plan = nombre
                item.descripcion = descripcion
                item.precio_bs = precio_bs
                item.precio_mensual_usd = usd
                item.duracion_dias = duracion_dias
                item.es_activo = True
                print(f"Actualizado: {codigo}")
            else:
                db.add(
                    SubscriptionPlan(
                        codigo_plan=codigo,
                        nombre_plan=nombre,
                        descripcion=descripcion,
                        precio_bs=precio_bs,
                        precio_mensual_usd=usd,
                        duracion_dias=duracion_dias,
                        es_activo=True,
                    )
                )
                print(f"Creado: {codigo}")
        db.commit()
        print("OK: planes de suscripcion listos.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
