from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import selectinload, sessionmaker

from vendei_desktop.infra.db.models import Category, Product, ProductOffering, UnitOfMeasure


@dataclass(frozen=True)
class ResolvedListing:
    unit_of_measure_id: int
    unit_label: str
    price: float
    cost: float


@dataclass(frozen=True)
class CatalogDao:
    session_factory: sessionmaker

    def list_categories(self) -> list[Category]:
        with self.session_factory() as s:
            return list(s.execute(select(Category).order_by(Category.name.asc())).scalars().all())

    def list_products(
        self,
        *,
        query: str | None = None,
        category_id: int | None = None,
        only_visible: bool = True,
        limit: int = 500,
    ) -> list[Product]:
        q = select(Product).order_by(Product.name.asc()).limit(limit)
        if only_visible:
            q = q.where(Product.visible.is_(True))
        if category_id is not None:
            q = q.where(Product.category_id == category_id)
        if query:
            like = f"%{query.strip()}%"
            q = q.where((Product.name.ilike(like)) | (Product.code.ilike(like)))
        with self.session_factory() as s:
            return list(s.execute(q).scalars().all())

    def get_product_by_code(self, code: str) -> Product | None:
        with self.session_factory() as s:
            return s.execute(select(Product).where(Product.code == code.strip())).scalars().first()

    def get_product(self, product_id: int) -> Product | None:
        with self.session_factory() as s:
            return s.get(Product, product_id)

    def resolve_listing_for_brand(self, *, product: Product, brand_id: int) -> ResolvedListing:
        pid = int(product.id)
        du = product.default_unit_of_measure_id
        with self.session_factory() as s:
            q = (
                select(ProductOffering)
                .where(ProductOffering.product_id == pid)
                .where(ProductOffering.brand_id == int(brand_id))
                .options(selectinload(ProductOffering.unit_of_measure))
            )
            offers = list(s.execute(q).scalars().all())
            if not offers:
                u = s.get(UnitOfMeasure, du) if du else None
                if not u:
                    u = s.execute(select(UnitOfMeasure).order_by(UnitOfMeasure.id.asc()).limit(1)).scalars().first()
                label = (u.abbreviation or u.name) if u else "—"
                uid = int(u.id) if u else 0
                return ResolvedListing(
                    unit_of_measure_id=uid,
                    unit_label=str(label),
                    price=float(product.price or 0.0),
                    cost=0.0,
                )
            chosen = None
            if du:
                for o in offers:
                    if int(o.unit_of_measure_id) == int(du):
                        chosen = o
                        break
            if chosen is None:
                chosen = min(offers, key=lambda o: int(o.id))
            u = chosen.unit_of_measure
            label = (u.abbreviation or u.name) if u else "—"
            return ResolvedListing(
                unit_of_measure_id=int(chosen.unit_of_measure_id),
                unit_label=str(label),
                price=float(chosen.price),
                cost=float(chosen.cost),
            )

    def list_offerings_for_brand(
        self,
        *,
        brand_id: int,
        query: str | None = None,
        only_visible: bool = True,
        limit: int = 500,
    ) -> list[ProductOffering]:
        """All catalog rows for a brand: one row per product × unit (and per brand) offering."""
        bid = int(brand_id)
        like = f"%{query.strip()}%" if query and query.strip() else None
        with self.session_factory() as s:
            q = (
                select(ProductOffering)
                .join(Product)
                .where(ProductOffering.brand_id == bid)
                .options(
                    selectinload(ProductOffering.product),
                    selectinload(ProductOffering.brand),
                    selectinload(ProductOffering.unit_of_measure),
                )
                .order_by(Product.name.asc(), ProductOffering.id.asc())
                .limit(limit)
            )
            if only_visible:
                q = q.where(Product.visible.is_(True))
            if like:
                q = q.where((Product.name.ilike(like)) | (Product.code.ilike(like)))
            return list(s.execute(q).scalars().all())

    def list_all_offerings_for_pos(
        self,
        *,
        query: str | None = None,
        only_visible: bool = True,
        limit: int = 3000,
    ) -> list[ProductOffering]:
        """Every offering for visible products (all brands), for cashier catalog."""
        like = f"%{query.strip()}%" if query and query.strip() else None
        with self.session_factory() as s:
            q = (
                select(ProductOffering)
                .join(Product)
                .options(
                    selectinload(ProductOffering.product),
                    selectinload(ProductOffering.brand),
                    selectinload(ProductOffering.unit_of_measure),
                )
                .order_by(Product.name.asc(), ProductOffering.brand_id.asc(), ProductOffering.id.asc())
                .limit(limit)
            )
            if only_visible:
                q = q.where(Product.visible.is_(True))
            if like:
                q = q.where((Product.name.ilike(like)) | (Product.code.ilike(like)))
            return list(s.execute(q).scalars().all())

    def resolve_offering_for_brand(self, *, product: Product, brand_id: int) -> ProductOffering | None:
        """Pick the offering row used for quick-add / default UOM for this brand, if any."""
        pid = int(product.id)
        du = product.default_unit_of_measure_id
        with self.session_factory() as s:
            q = (
                select(ProductOffering)
                .where(ProductOffering.product_id == pid)
                .where(ProductOffering.brand_id == int(brand_id))
                .options(selectinload(ProductOffering.unit_of_measure), selectinload(ProductOffering.brand))
            )
            offers = list(s.execute(q).scalars().all())
            if not offers:
                return None
            chosen = None
            if du:
                for o in offers:
                    if int(o.unit_of_measure_id) == int(du):
                        chosen = o
                        break
            if chosen is None:
                chosen = min(offers, key=lambda o: int(o.id))
            return chosen

    def replace_product_offerings(
        self,
        product_id: int,
        rows: list[tuple[int, int, float, float]],
    ) -> None:
        """rows: (brand_id, unit_of_measure_id, cost, price). Upserts by (brand, UOM); keeps ids & stock."""
        if not rows:
            raise ValueError("At least one offering row is required.")
        pid = int(product_id)
        with self.session_factory() as s:
            prev = list(
                s.execute(select(ProductOffering).where(ProductOffering.product_id == pid)).scalars().all()
            )
            by_key: dict[tuple[int, int], ProductOffering] = {
                (int(o.brand_id), int(o.unit_of_measure_id)): o for o in prev
            }
            new_keys = {(int(bid), int(uid)) for bid, uid, _, _ in rows}
            for o in prev:
                if (int(o.brand_id), int(o.unit_of_measure_id)) not in new_keys:
                    s.delete(o)
            for bid, uid, cost, price in rows:
                if float(price) < 0 or float(cost) < 0:
                    raise ValueError("Cost and price cannot be negative.")
                sk = (int(bid), int(uid))
                ex = by_key.get(sk)
                if ex is not None:
                    ex.cost = float(cost)
                    ex.price = float(price)
                else:
                    s.add(
                        ProductOffering(
                            product_id=pid,
                            brand_id=int(bid),
                            unit_of_measure_id=int(uid),
                            cost=float(cost),
                            price=float(price),
                            stock=0.0,
                        )
                    )
            s.commit()

    def list_offerings_for_product(self, product_id: int) -> list[ProductOffering]:
        pid = int(product_id)
        with self.session_factory() as s:
            q = (
                select(ProductOffering)
                .where(ProductOffering.product_id == pid)
                .options(selectinload(ProductOffering.brand), selectinload(ProductOffering.unit_of_measure))
                .order_by(ProductOffering.brand_id.asc(), ProductOffering.unit_of_measure_id.asc())
            )
            return list(s.execute(q).scalars().all())

    def update_product(
        self,
        product_id: int,
        *,
        name: str,
        code: str | None,
        price: float,
        category_id: int | None = None,
        visible: bool = True,
        image_url: str | None = None,
        track_expiry: bool = False,
        default_shelf_life_days: int | None = None,
        default_unit_of_measure_id: int | None = None,
    ) -> Product:
        nm = (name or "").strip()
        if not nm:
            raise ValueError("Product name is required")
        cd = (code or "").strip() or None
        if cd and len(cd) > 64:
            raise ValueError("Code is too long (max 64 characters).")
        if len(nm) > 240:
            raise ValueError("Name is too long (max 240 characters).")
        img = (image_url or "").strip() or None
        if img and len(img) > 500:
            raise ValueError("Image path is too long (max 500 characters).")
        pr = float(price)
        if pr < 0:
            raise ValueError("Price cannot be negative.")

        with self.session_factory() as s:
            p = s.get(Product, int(product_id))
            if not p:
                raise ValueError("Product not found")
            p.name = nm
            p.code = cd
            p.image_url = img
            p.visible = bool(visible)
            p.price = pr
            p.track_expiry = bool(track_expiry)
            p.default_shelf_life_days = (
                int(default_shelf_life_days) if default_shelf_life_days is not None else None
            )
            p.category_id = int(category_id) if category_id is not None else None
            p.default_unit_of_measure_id = (
                int(default_unit_of_measure_id) if default_unit_of_measure_id else None
            )
            s.commit()
            s.refresh(p)
            return p

    def create_product(
        self,
        *,
        name: str,
        code: str | None,
        price: float,
        category_id: int | None = None,
        visible: bool = True,
        image_url: str | None = None,
        track_expiry: bool = False,
        default_shelf_life_days: int | None = None,
        default_unit_of_measure_id: int | None = None,
    ) -> Product:
        nm = (name or "").strip()
        if not nm:
            raise ValueError("Product name is required")
        cd = (code or "").strip() or None
        if cd and len(cd) > 64:
            raise ValueError("Code is too long (max 64 characters).")
        if len(nm) > 240:
            raise ValueError("Name is too long (max 240 characters).")
        img = (image_url or "").strip() or None
        if img and len(img) > 500:
            raise ValueError("Image path is too long (max 500 characters).")
        pr = float(price)
        if pr < 0:
            raise ValueError("Price cannot be negative.")

        with self.session_factory() as s:
            p = Product(
                name=nm,
                code=cd,
                image_url=img,
                visible=bool(visible),
                price=pr,
                stock=0.0,
                track_expiry=bool(track_expiry),
                default_shelf_life_days=int(default_shelf_life_days) if default_shelf_life_days is not None else None,
                category_id=int(category_id) if category_id is not None else None,
                default_unit_of_measure_id=int(default_unit_of_measure_id) if default_unit_of_measure_id else None,
            )
            s.add(p)
            s.commit()
            s.refresh(p)
            return p
