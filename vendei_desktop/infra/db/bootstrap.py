from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .base import Base
from .models import Category, Customer, InventoryLot, Product


def create_schema(engine) -> None:
    Base.metadata.create_all(engine)
    # Lightweight migration for early dev: add new columns when DB already exists.
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("products")}
        if "visible" not in cols:
            conn.execute(text("ALTER TABLE products ADD COLUMN visible BOOLEAN NOT NULL DEFAULT 1"))


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

    # Customers (ensure at least anonymous + a few demo customers)
    if session.query(Customer).count() == 0:
        session.add(Customer(name="Anonymous", document=None))
        session.flush()

    demo_customers = [
        ("Anonymous", None),
        ("Juan Pérez", "V-12345678"),
        ("María González", "V-87654321"),
        ("Carlos Rodríguez", "V-11223344"),
        ("Ana Martínez", "V-44332211"),
    ]
    for name, doc in demo_customers:
        exists = (
            session.query(Customer)
            .filter(Customer.name == name, Customer.document.is_(doc) if doc is None else Customer.document == doc)
            .first()
        )
        if not exists:
            session.add(Customer(name=name, document=doc))

    # Products demo (idempotent insert by code)
    grocery = session.query(Category).filter_by(name="Grocery").first()
    home = session.query(Category).filter_by(name="Home").first()
    electronics = session.query(Category).filter_by(name="Electronics").first()

    demo_products = [
        # Grocery
        dict(
            name="Red Apple (1 lb)",
            code="GROC-0001",
            price=9.99,
            stock=50,
            category_id=grocery.id if grocery else None,
            image_url="demo-products/apple.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Bananas (1 lb)",
            code="GROC-0002",
            price=11.49,
            stock=60,
            category_id=grocery.id if grocery else None,
            image_url="demo-products/bananas.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Milk (1 L)",
            code="GROC-0004",
            price=14.49,
            stock=20,
            category_id=grocery.id if grocery else None,
            image_url="demo-products/milk.jpg",
            visible=True,
            track_expiry=True,
            default_shelf_life_days=14,
        ),
        dict(
            name="Bread (500 g)",
            code="GROC-0005",
            price=12.0,
            stock=30,
            category_id=grocery.id if grocery else None,
            image_url="demo-products/bread.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Eggs (12 pack)",
            code="GROC-0006",
            price=22.5,
            stock=18,
            category_id=grocery.id if grocery else None,
            image_url="demo-products/eggs.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Coffee (250 g)",
            code="GROC-0007",
            price=35.0,
            stock=25,
            category_id=grocery.id if grocery else None,
            image_url="demo-products/coffee.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Yogurt (150 g)",
            code="GROC-0008",
            price=8.5,
            stock=40,
            category_id=grocery.id if grocery else None,
            image_url="demo-products/yogurt.jpg",
            visible=True,
            track_expiry=True,
            default_shelf_life_days=10,
        ),
        dict(
            name="Water (1.5 L)",
            code="GROC-0009",
            price=7.0,
            stock=80,
            category_id=grocery.id if grocery else None,
            image_url="demo-products/water.jpg",
            visible=True,
            track_expiry=False,
        ),
        # Home
        dict(
            name="Detergent (1 L)",
            code="HOME-0001",
            price=28.0,
            stock=15,
            category_id=home.id if home else None,
            image_url="demo-products/detergent.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Paper Towels (2 rolls)",
            code="HOME-0002",
            price=18.0,
            stock=22,
            category_id=home.id if home else None,
            image_url="demo-products/paper-towels.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Soap (bar)",
            code="HOME-0003",
            price=6.5,
            stock=70,
            category_id=home.id if home else None,
            image_url="demo-products/soap.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Shampoo (400 ml)",
            code="HOME-0004",
            price=24.0,
            stock=16,
            category_id=home.id if home else None,
            image_url="demo-products/shampoo.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Toothpaste (100 ml)",
            code="HOME-0005",
            price=14.0,
            stock=35,
            category_id=home.id if home else None,
            image_url="demo-products/toothpaste.jpg",
            visible=True,
            track_expiry=False,
        ),
        # Electronics
        dict(
            name="Smartphone (64 GB)",
            code="ELEC-0001",
            price=1299.0,
            stock=6,
            category_id=electronics.id if electronics else None,
            image_url="demo-products/smartphone.jpg",
            visible=True,
            track_expiry=False,
        ),
        dict(
            name="Headphones",
            code="ELEC-0002",
            price=199.0,
            stock=12,
            category_id=electronics.id if electronics else None,
            image_url="demo-products/headphones.jpg",
            visible=True,
            track_expiry=False,
        ),
    ]

    for attrs in demo_products:
        code = attrs["code"]
        exists = session.query(Product).filter(Product.code == code).first()
        if not exists:
            session.add(Product(**attrs))

    session.flush()

    # Lots for tracked product(s) (idempotent-ish: only seed lots when none exist yet)
    milk = session.query(Product).filter_by(code="GROC-0004").first()
    if milk and session.query(InventoryLot).filter(InventoryLot.product_id == milk.id).count() == 0:
        # two lots so FEFO can be tested later
        session.add_all(
            [
                InventoryLot(product_id=milk.id, quantity=8, expiry_date=None, batch_code="LOT-A"),
                InventoryLot(product_id=milk.id, quantity=12, expiry_date=None, batch_code="LOT-B"),
            ]
        )

    session.commit()

