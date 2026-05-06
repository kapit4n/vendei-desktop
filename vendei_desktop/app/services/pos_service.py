from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from vendei_desktop.infra.dao.brand_dao import BrandDao
from vendei_desktop.infra.dao.catalog_dao import CatalogDao
from vendei_desktop.infra.dao.customer_dao import CustomerDao
from vendei_desktop.infra.dao.order_dao import OrderDao
from vendei_desktop.infra.dao.purchase_request_dao import PurchaseRequestDao
from vendei_desktop.infra.dao.stock_dao import StockDao
from vendei_desktop.infra.dao.unit_dao import UnitDao
from vendei_desktop.infra.db.models import ProductOffering


@dataclass(frozen=True)
class TicketLine:
    product_offering_id: int
    product_id: int
    brand_id: int
    brand_name: str
    name: str
    unit_label: str | None
    unit_of_measure_id: int | None
    image_url: str | None
    unit_price: float
    quantity: float

    @property
    def line_total(self) -> float:
        return round(float(self.unit_price) * float(self.quantity), 2)


@dataclass(frozen=True)
class ProductListing:
    product_offering_id: int
    product_id: int
    name: str
    code: str | None
    image_url: str | None
    stock: float
    visible: bool
    brand_id: int
    brand_name: str
    unit_of_measure_id: int
    unit_label: str
    unit_price: float
    cost: float


def _product_listing_from_offering(o: ProductOffering) -> ProductListing:
    p = o.product
    if p is None:
        raise ValueError("Offering is missing product")
    u = o.unit_of_measure
    b = o.brand
    label = (u.abbreviation or u.name) if u else "—"
    bname = str(b.name) if b else "—"
    return ProductListing(
        product_offering_id=int(o.id),
        product_id=int(p.id),
        name=str(p.name),
        code=p.code,
        image_url=p.image_url,
        stock=float(o.stock or 0.0),
        visible=bool(p.visible),
        brand_id=int(o.brand_id),
        brand_name=bname,
        unit_of_measure_id=int(o.unit_of_measure_id),
        unit_label=str(label),
        unit_price=float(o.price),
        cost=float(o.cost),
    )


class PosService:
    def __init__(
        self,
        catalog: CatalogDao,
        customers: CustomerDao,
        stock: StockDao,
        orders: OrderDao,
        purchase_requests: PurchaseRequestDao,
        units: UnitDao,
        brands: BrandDao,
    ) -> None:
        self._catalog = catalog
        self._customers = customers
        self._stock = stock
        self._orders = orders
        self._purchase_requests = purchase_requests
        self._units = units
        self._brands = brands

    def list_units_of_measure(self):
        return self._units.list_units()

    def create_unit_of_measure(self, *, name: str, abbreviation: str | None = None):
        return self._units.create_unit(name=name, abbreviation=abbreviation)

    def delete_unit_of_measure(self, unit_id: int) -> None:
        self._units.delete_unit(unit_id)

    def list_brands(self):
        return self._brands.list_brands()

    def create_brand(self, *, name: str, code: str | None = None):
        return self._brands.create_brand(name=name, code=code)

    def delete_brand(self, brand_id: int) -> None:
        self._brands.delete_brand(brand_id)

    def list_categories(self):
        return self._catalog.list_categories()

    def list_products(self, *, query: str | None = None, category_id: int | None = None, only_visible: bool = True):
        return self._catalog.list_products(query=query, category_id=category_id, only_visible=only_visible)

    def list_product_listings(
        self,
        *,
        brand_id: int,
        query: str | None = None,
        only_visible: bool = True,
    ) -> list[ProductListing]:
        offers = self._catalog.list_offerings_for_brand(
            brand_id=brand_id, query=query, only_visible=only_visible
        )
        return [_product_listing_from_offering(o) for o in offers]

    def list_all_product_listings(
        self,
        *,
        query: str | None = None,
        only_visible: bool = True,
    ) -> list[ProductListing]:
        """All offerings (every brand × unit) for the POS grid, search optional."""
        offers = self._catalog.list_all_offerings_for_pos(query=query, only_visible=only_visible)
        return [_product_listing_from_offering(o) for o in offers]

    def quick_add_by_code(self, code: str):
        return self._catalog.get_product_by_code(code)

    def listings_for_product_code(self, code: str) -> list[ProductListing]:
        """Visible product match by code with all its offerings (for barcode / quick add)."""
        p = self._catalog.get_product_by_code(code)
        if not p or not p.visible:
            return []
        offers = self._catalog.list_offerings_for_product(int(p.id))
        return [_product_listing_from_offering(o) for o in offers]

    def quick_listing_by_code(self, code: str, *, brand_id: int) -> ProductListing | None:
        p = self._catalog.get_product_by_code(code)
        if not p or not p.visible:
            return None
        o = self._catalog.resolve_offering_for_brand(product=p, brand_id=int(brand_id))
        if not o:
            return None
        return _product_listing_from_offering(o)

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
        brand_id: int | None,
        lines: list[TicketLine],
        payment_method: str = "CASH",
        amount_received: float | None = None,
        change_given: float | None = None,
    ) -> int:
        if not lines:
            raise ValueError("Ticket is empty")

        total = round(sum(l.line_total for l in lines), 2)
        pm = str(payment_method).upper()
        if pm not in ("CASH", "QR"):
            pm = "CASH"
        order_id = self._orders.create_order(
            customer_id=customer_id,
            brand_id=brand_id,
            total=total,
            payment_method=pm,
            amount_received=amount_received,
            change_given=change_given,
            lines=[
                {
                    "product_id": l.product_id,
                    "quantity": l.quantity,
                    "unit_price": l.unit_price,
                    "line_total": l.line_total,
                    "unit_of_measure_id": l.unit_of_measure_id,
                    "product_offering_id": l.product_offering_id,
                }
                for l in lines
            ],
        )

        for l in lines:
            self._stock.reduce_stock_fefo(
                l.product_id, l.quantity, product_offering_id=int(l.product_offering_id)
            )

        return order_id

    def list_inventory_lots(self, product_id: int, *, product_offering_id: int | None = None):
        return self._stock.list_lots(product_id, product_offering_id=product_offering_id)

    def add_inventory(
        self,
        *,
        product_id: int,
        quantity: float,
        product_offering_id: int | None = None,
        expiry_date: date | None = None,
        batch_code: str | None = None,
    ) -> None:
        self._stock.add_stock(
            product_id=product_id,
            quantity=quantity,
            product_offering_id=product_offering_id,
            expiry_date=expiry_date,
            batch_code=batch_code,
        )

    def get_product(self, product_id: int):
        return self._catalog.get_product(product_id)

    def create_product(
        self,
        *,
        name: str,
        code: str | None = None,
        category_id: int | None = None,
        visible: bool = True,
        image_url: str | None = None,
        track_expiry: bool = False,
        default_shelf_life_days: int | None = None,
        default_unit_of_measure_id: int,
        offerings: list[tuple[int, int, float, float]],
        opening_stock: float = 0.0,
        opening_batch_code: str | None = None,
        opening_expiry_date: date | None = None,
    ):
        code_clean = (code or "").strip() or None
        if code_clean and self._catalog.get_product_by_code(code_clean):
            raise ValueError(f'A product with code "{code_clean}" already exists.')
        if not offerings:
            raise ValueError("Add at least one brand / unit / cost / price row.")
        ref_price = max(float(row[3]) for row in offerings)

        p = self._catalog.create_product(
            name=name,
            code=code_clean,
            price=float(ref_price),
            category_id=category_id,
            visible=visible,
            image_url=(image_url or "").strip() or None,
            track_expiry=track_expiry,
            default_shelf_life_days=default_shelf_life_days,
            default_unit_of_measure_id=int(default_unit_of_measure_id),
        )
        oid = int(p.id)
        self._catalog.replace_product_offerings(oid, list(offerings))

        qty = float(opening_stock or 0.0)
        if qty > 0:
            offs = self._catalog.list_offerings_for_product(oid)
            b0, u0, _, _ = offerings[0]
            target = next(
                (o for o in offs if int(o.brand_id) == int(b0) and int(o.unit_of_measure_id) == int(u0)),
                offs[0] if offs else None,
            )
            if target is None:
                raise ValueError("Could not resolve offering for opening stock.")
            self.add_inventory(
                product_id=oid,
                product_offering_id=int(target.id),
                quantity=qty,
                expiry_date=opening_expiry_date,
                batch_code=opening_batch_code,
            )
        return self._catalog.get_product(oid)

    def list_product_offerings(self, product_id: int):
        return self._catalog.list_offerings_for_product(product_id)

    def update_product(
        self,
        product_id: int,
        *,
        name: str,
        code: str | None = None,
        category_id: int | None = None,
        visible: bool = True,
        image_url: str | None = None,
        track_expiry: bool = False,
        default_shelf_life_days: int | None = None,
        default_unit_of_measure_id: int,
        offerings: list[tuple[int, int, float, float]],
    ):
        code_clean = (code or "").strip() or None
        if code_clean:
            other = self._catalog.get_product_by_code(code_clean)
            if other and int(other.id) != int(product_id):
                raise ValueError(f'A product with code "{code_clean}" already exists.')
        if not offerings:
            raise ValueError("Add at least one brand / unit / cost / price row.")
        ref_price = max(float(row[3]) for row in offerings)
        self._catalog.update_product(
            int(product_id),
            name=name,
            code=code_clean,
            price=float(ref_price),
            category_id=category_id,
            visible=visible,
            image_url=(image_url or "").strip() or None,
            track_expiry=track_expiry,
            default_shelf_life_days=default_shelf_life_days,
            default_unit_of_measure_id=int(default_unit_of_measure_id),
        )
        self._catalog.replace_product_offerings(int(product_id), list(offerings))
        return self._catalog.get_product(int(product_id))

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
