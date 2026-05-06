from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from vendei_desktop.infra.db.models import Order, OrderLine


@dataclass(frozen=True)
class OrderDao:
    session_factory: sessionmaker

    def create_order(
        self,
        *,
        customer_id: int | None,
        total: float,
        lines: list[dict],
    ) -> int:
        with self.session_factory() as s:
            o = Order(
                created_at=datetime.utcnow(),
                customer_id=customer_id,
                total=float(total),
                paid=True,
                delivered=True,
            )
            s.add(o)
            s.flush()

            for ln in lines:
                s.add(
                    OrderLine(
                        order_id=o.id,
                        product_id=int(ln["product_id"]),
                        quantity=float(ln["quantity"]),
                        unit_price=float(ln["unit_price"]),
                        line_total=float(ln["line_total"]),
                    )
                )

            s.commit()
            return int(o.id)

