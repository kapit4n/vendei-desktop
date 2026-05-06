from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from vendei_desktop.infra.dao.catalog_dao import CatalogDao
from vendei_desktop.infra.dao.customer_dao import CustomerDao
from vendei_desktop.infra.dao.order_dao import OrderDao
from vendei_desktop.infra.dao.stock_dao import StockDao


@dataclass(frozen=True)
class TicketLine:
    product_id: int
    name: str
    unit_label: str | None
    image_url: str | None
    unit_price: float
    quantity: float

    @property
    def line_total(self) -> float:
        return round(float(self.unit_price) * float(self.quantity), 2)


class PosService:
    def __init__(
        self,
        catalog: CatalogDao,
        customers: CustomerDao,
        stock: StockDao,
        orders: OrderDao,
    ) -> None:
        self._catalog = catalog
        self._customers = customers
        self._stock = stock
        self._orders = orders

    def list_categories(self):
        return self._catalog.list_categories()

    def list_products(self, *, query: str | None = None, category_id: int | None = None, only_visible: bool = True):
        return self._catalog.list_products(query=query, category_id=category_id, only_visible=only_visible)

    def quick_add_by_code(self, code: str):
        return self._catalog.get_product_by_code(code)

    def anonymous_customer(self):
        return self._customers.get_anonymous()

    def list_customers(self, query: str | None = None):
        return self._customers.list_customers(query=query)

    def submit_order(
        self,
        *,
        customer_id: int | None,
        lines: list[TicketLine],
    ) -> int:
        if not lines:
            raise ValueError("Ticket is empty")

        total = round(sum(l.line_total for l in lines), 2)
        order_id = self._orders.create_order(
            customer_id=customer_id,
            total=total,
            lines=[
                {
                    "product_id": l.product_id,
                    "quantity": l.quantity,
                    "unit_price": l.unit_price,
                    "line_total": l.line_total,
                }
                for l in lines
            ],
        )

        # Reduce inventory after creating the order (simple; can be made transactional later).
        for l in lines:
            self._stock.reduce_stock_fefo(l.product_id, l.quantity)

        return order_id

    def list_inventory_lots(self, product_id: int):
        return self._stock.list_lots(product_id)

    def add_inventory(
        self,
        *,
        product_id: int,
        quantity: float,
        expiry_date: date | None = None,
        batch_code: str | None = None,
    ) -> None:
        self._stock.add_stock(product_id=product_id, quantity=quantity, expiry_date=expiry_date, batch_code=batch_code)

    def get_product(self, product_id: int):
        return self._catalog.get_product(product_id)

