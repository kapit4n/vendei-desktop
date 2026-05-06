from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from vendei_desktop.infra.dao.catalog_dao import CatalogDao
from vendei_desktop.infra.dao.customer_dao import CustomerDao
from vendei_desktop.infra.dao.order_dao import OrderDao
from vendei_desktop.infra.dao.purchase_request_dao import PurchaseRequestDao
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
        purchase_requests: PurchaseRequestDao,
    ) -> None:
        self._catalog = catalog
        self._customers = customers
        self._stock = stock
        self._orders = orders
        self._purchase_requests = purchase_requests

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

    def create_customer(self, *, name: str, document: str | None = None):
        return self._customers.create_customer(name=name, document=document)

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

    def list_orders_between(self, *, start: datetime, end: datetime):
        return self._orders.list_orders_between(start=start, end=end)

    def get_order_with_lines(self, order_id: int):
        return self._orders.get_order_with_lines(order_id)

    def get_open_purchase_request(self):
        return self._purchase_requests.get_open_with_items()

    def set_purchase_request_item(self, *, product_id: int, quantity: float) -> None:
        pr = self._purchase_requests.get_open()
        self._purchase_requests.set_item(request_id=pr.id, product_id=product_id, quantity=quantity)

    def remove_purchase_request_item(self, *, product_id: int) -> None:
        pr = self._purchase_requests.get_open()
        self._purchase_requests.remove_item(request_id=pr.id, product_id=product_id)

