from __future__ import annotations

from sqlalchemy.orm import Session

from .base import Base
from .models import Category, Customer, InventoryLot, Product


def create_schema(engine) -> None:
    Base.metadata.create_all(engine)


def seed_if_empty(session: Session) -> None:
    # Categories
    if session.query(Category).count() == 0:
        cats = [
            Category(name="Grocery"),
            Category(name="Electronics"),
            Category(name="Apparel"),
            Category(name="Home"),
            Category(name="Sports"),
        ]
        session.add_all(cats)
        session.flush()

    # Anonymous customer
    if session.query(Customer).count() == 0:
        session.add(Customer(name="Anonymous", document=None))

    # Products demo
    if session.query(Product).count() == 0:
        grocery = session.query(Category).filter_by(name="Grocery").first()
        items = [
            Product(
                name="Red Apple (1 lb)",
                code="GROC-0001",
                price=9.99,
                stock=50,
                category_id=grocery.id if grocery else None,
                image_url=None,
                track_expiry=False,
            ),
            Product(
                name="Bananas (1 lb)",
                code="GROC-0002",
                price=11.49,
                stock=60,
                category_id=grocery.id if grocery else None,
                image_url=None,
                track_expiry=False,
            ),
            Product(
                name="Milk (1 L)",
                code="GROC-0004",
                price=14.49,
                stock=20,
                category_id=grocery.id if grocery else None,
                image_url=None,
                track_expiry=True,
                default_shelf_life_days=14,
            ),
        ]
        session.add_all(items)
        session.flush()

        # Lots for tracked product(s)
        milk = session.query(Product).filter_by(code="GROC-0004").first()
        if milk:
            # two lots so FEFO can be tested later
            session.add_all(
                [
                    InventoryLot(product_id=milk.id, quantity=8, expiry_date=None, batch_code="LOT-A"),
                    InventoryLot(product_id=milk.id, quantity=12, expiry_date=None, batch_code="LOT-B"),
                ]
            )

    session.commit()

