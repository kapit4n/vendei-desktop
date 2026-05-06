from __future__ import annotations

from dataclasses import dataclass, field

from vendei_desktop.app.services.pos_service import PosService, TicketLine


@dataclass
class PosState:
    customer_id: int | None = None
    customer_name: str = "Anonymous"
    customer_doc: str | None = None
    lines: list[TicketLine] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(l.line_total for l in self.lines), 2)


class PosViewModel:
    def __init__(self, service: PosService) -> None:
        self._svc = service
        anon = self._svc.anonymous_customer()
        self.state = PosState(customer_id=anon.id, customer_name=anon.name, customer_doc=anon.document)

    def clear_ticket(self) -> None:
        self.state.lines = []

    def add_product(self, p) -> None:
        # p is ORM Product
        for i, ln in enumerate(self.state.lines):
            if ln.product_id == p.id:
                self.state.lines[i] = TicketLine(
                    product_id=ln.product_id,
                    name=ln.name,
                    unit_label=ln.unit_label,
                    image_url=ln.image_url,
                    unit_price=ln.unit_price,
                    quantity=ln.quantity + 1,
                )
                return
        self.state.lines.append(
            TicketLine(
                product_id=p.id,
                name=p.name,
                unit_label=None,
                image_url=getattr(p, "image_url", None),
                unit_price=float(p.price),
                quantity=1,
            )
        )

    def set_customer(self, c) -> None:
        self.state.customer_id = c.id
        self.state.customer_name = c.name
        self.state.customer_doc = c.document

    def submit(self) -> int:
        return self._svc.submit_order(customer_id=self.state.customer_id, lines=self.state.lines)

