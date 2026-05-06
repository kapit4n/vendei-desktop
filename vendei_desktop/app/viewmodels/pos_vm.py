from __future__ import annotations

from dataclasses import dataclass, field

from vendei_desktop.app.services.pos_service import PosService, ProductListing, TicketLine


@dataclass
class PosState:
    customer_id: int | None = None
    customer_name: str = "Anonymous"
    customer_doc: str | None = None
    lines: list[TicketLine] = field(default_factory=list)
    payment_method: str = "CASH"  # CASH | QR
    amount_received: float = 0.0

    @property
    def total(self) -> float:
        return round(sum(l.line_total for l in self.lines), 2)


class PosViewModel:
    def __init__(self, service: PosService) -> None:
        self._svc = service
        anon = self._svc.anonymous_customer()
        self.state = PosState(
            customer_id=anon.id,
            customer_name=anon.name,
            customer_doc=anon.document,
        )

    def clear_ticket(self) -> None:
        self.state.lines = []
        self.state.payment_method = "CASH"
        self.state.amount_received = 0.0

    @staticmethod
    def _same_line(a: TicketLine, listing: ProductListing) -> bool:
        return int(a.product_offering_id) == int(listing.product_offering_id)

    def add_product(self, listing: ProductListing, quantity: float = 1) -> None:
        q = float(quantity)
        if q <= 0:
            return
        for i, ln in enumerate(self.state.lines):
            if self._same_line(ln, listing):
                self.state.lines[i] = TicketLine(
                    product_offering_id=ln.product_offering_id,
                    product_id=ln.product_id,
                    brand_id=ln.brand_id,
                    brand_name=ln.brand_name,
                    name=ln.name,
                    unit_label=ln.unit_label,
                    unit_of_measure_id=ln.unit_of_measure_id,
                    image_url=ln.image_url,
                    unit_price=ln.unit_price,
                    quantity=ln.quantity + q,
                )
                return
        self.state.lines.append(
            TicketLine(
                product_offering_id=listing.product_offering_id,
                product_id=listing.product_id,
                brand_id=int(listing.brand_id),
                brand_name=str(listing.brand_name),
                name=listing.name,
                unit_label=listing.unit_label,
                unit_of_measure_id=listing.unit_of_measure_id,
                image_url=listing.image_url,
                unit_price=float(listing.unit_price),
                quantity=q,
            )
        )

    def set_line_quantity(self, *, product_offering_id: int, quantity: float) -> None:
        q = float(quantity)
        oid = int(product_offering_id)
        if q <= 0:
            self.state.lines = [ln for ln in self.state.lines if int(ln.product_offering_id) != oid]
            return
        for i, ln in enumerate(self.state.lines):
            if int(ln.product_offering_id) == oid:
                self.state.lines[i] = TicketLine(
                    product_offering_id=ln.product_offering_id,
                    product_id=ln.product_id,
                    brand_id=ln.brand_id,
                    brand_name=ln.brand_name,
                    name=ln.name,
                    unit_label=ln.unit_label,
                    unit_of_measure_id=ln.unit_of_measure_id,
                    image_url=ln.image_url,
                    unit_price=ln.unit_price,
                    quantity=q,
                )
                return

    def set_customer(self, c) -> None:
        self.state.customer_id = c.id
        self.state.customer_name = c.name
        self.state.customer_doc = c.document

    def submit(self) -> int:
        if not self.state.lines:
            raise ValueError("Ticket is empty")
        total = self.state.total
        pm = self.state.payment_method.upper()
        bids = {int(ln.brand_id) for ln in self.state.lines}
        brand_id = bids.pop() if len(bids) == 1 else None
        if pm == "QR":
            return self._svc.submit_order(
                customer_id=self.state.customer_id,
                brand_id=brand_id,
                lines=self.state.lines,
                payment_method="QR",
                amount_received=None,
                change_given=None,
            )
        tender = float(self.state.amount_received or 0.0)
        if tender + 1e-9 < total:
            raise ValueError("Cash tender is less than the amount due.")
        change = round(max(0.0, tender - total), 2)
        return self._svc.submit_order(
            customer_id=self.state.customer_id,
            brand_id=brand_id,
            lines=self.state.lines,
            payment_method="CASH",
            amount_received=tender,
            change_given=change,
        )
