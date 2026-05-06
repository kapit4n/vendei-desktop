from __future__ import annotations

import re

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .base import Base
from .models import Brand, Category, Customer, InventoryLot, Product, ProductOffering, UnitOfMeasure


def _pragma_fk_refs_table(conn, sqlite_table: str, referenced_table: str) -> bool:
    try:
        rows = conn.execute(text(f"PRAGMA foreign_key_list({sqlite_table})")).fetchall()
    except Exception:
        return False
    for row in rows:
        # (id, seq, table, from, to, on_update, on_delete, match)
        if len(row) > 2 and row[2] == referenced_table:
            return True
    return False


def _rebuild_product_offerings_brands_fk(conn, *, force: bool = False) -> None:
    """Ensure product_offerings.brand_id references brands, not legacy branches."""
    insp = inspect(conn)
    if not insp.has_table("product_offerings"):
        return
    if not force:
        if not _pragma_fk_refs_table(conn, "product_offerings", "branches") and not insp.has_table(
            "branches"
        ):
            return
    pcols = {c["name"] for c in inspect(conn).get_columns("product_offerings")}
    bcol = "brand_id" if "brand_id" in pcols else "branch_id"
    stock_sel = "stock" if "stock" in pcols else "0"
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        conn.execute(text("DROP TABLE IF EXISTS product_offerings__new"))
        conn.execute(
            text(
                """
                CREATE TABLE product_offerings__new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    product_id INTEGER NOT NULL,
                    brand_id INTEGER NOT NULL,
                    unit_of_measure_id INTEGER NOT NULL,
                    cost FLOAT NOT NULL,
                    price FLOAT NOT NULL,
                    stock FLOAT NOT NULL DEFAULT 0,
                    UNIQUE (product_id, brand_id, unit_of_measure_id),
                    FOREIGN KEY(product_id) REFERENCES products (id),
                    FOREIGN KEY(brand_id) REFERENCES brands (id),
                    FOREIGN KEY(unit_of_measure_id) REFERENCES units_of_measure (id)
                )
                """
            )
        )
        conn.execute(
            text(
                f"INSERT INTO product_offerings__new "
                f"(id, product_id, brand_id, unit_of_measure_id, cost, price, stock) "
                f"SELECT id, product_id, {bcol}, unit_of_measure_id, cost, price, {stock_sel} FROM product_offerings"
            )
        )
        conn.execute(text("DROP TABLE product_offerings"))
        conn.execute(text("ALTER TABLE product_offerings__new RENAME TO product_offerings"))
    finally:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _rebuild_orders_brands_fk(conn, *, force: bool = False) -> None:
    """Ensure orders.brand_id references brands, not legacy branches."""
    insp = inspect(conn)
    if not insp.has_table("orders") or not insp.has_table("order_lines"):
        return
    if not force:
        if not _pragma_fk_refs_table(conn, "orders", "branches") and not insp.has_table("branches"):
            return
    ocols = {c["name"] for c in inspect(conn).get_columns("orders")}
    bcol = "brand_id" if "brand_id" in ocols else "branch_id"
    lcols_pre = {c["name"] for c in inspect(conn).get_columns("order_lines")}
    has_po_line = "product_offering_id" in lcols_pre
    po_sel = "product_offering_id" if has_po_line else "NULL"
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        conn.execute(text("DROP TABLE IF EXISTS order_lines__new"))
        conn.execute(text("DROP TABLE IF EXISTS orders__new"))
        conn.execute(
            text(
                """
                CREATE TABLE orders__new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    created_at DATETIME NOT NULL,
                    customer_id INTEGER,
                    brand_id INTEGER,
                    total FLOAT NOT NULL,
                    paid BOOLEAN NOT NULL,
                    delivered BOOLEAN NOT NULL,
                    payment_method VARCHAR(16) NOT NULL,
                    amount_received FLOAT,
                    change_given FLOAT,
                    FOREIGN KEY(customer_id) REFERENCES customers (id),
                    FOREIGN KEY(brand_id) REFERENCES brands (id)
                )
                """
            )
        )
        conn.execute(
            text(
                f"INSERT INTO orders__new "
                f"(id, created_at, customer_id, brand_id, total, paid, delivered, "
                f"payment_method, amount_received, change_given) "
                f"SELECT id, created_at, customer_id, {bcol}, total, paid, delivered, "
                f"payment_method, amount_received, change_given FROM orders"
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE order_lines__new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    order_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity FLOAT NOT NULL,
                    unit_price FLOAT NOT NULL,
                    line_total FLOAT NOT NULL,
                    unit_of_measure_id INTEGER,
                    product_offering_id INTEGER,
                    FOREIGN KEY(order_id) REFERENCES orders__new (id),
                    FOREIGN KEY(product_id) REFERENCES products (id),
                    FOREIGN KEY(unit_of_measure_id) REFERENCES units_of_measure (id),
                    FOREIGN KEY(product_offering_id) REFERENCES product_offerings (id)
                )
                """
            )
        )
        conn.execute(
            text(
                f"INSERT INTO order_lines__new "
                f"(id, order_id, product_id, quantity, unit_price, line_total, unit_of_measure_id, product_offering_id) "
                f"SELECT id, order_id, product_id, quantity, unit_price, line_total, unit_of_measure_id, {po_sel} "
                f"FROM order_lines"
            )
        )
        conn.execute(text("DROP TABLE order_lines"))
        conn.execute(text("DROP TABLE orders"))
        conn.execute(text("ALTER TABLE orders__new RENAME TO orders"))
        conn.execute(text("ALTER TABLE order_lines__new RENAME TO order_lines"))
    finally:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _migrate_order_lines_remove_order_product_unique(conn) -> None:
    """
    Legacy UNIQUE(order_id, product_id) blocks multiple lines for the same product
    (different brand/UOM offerings). Rebuild without that constraint and add
    product_offering_id when missing.
    """
    insp = inspect(conn)
    if not insp.has_table("order_lines"):
        return
    lcols = {c["name"] for c in insp.get_columns("order_lines")}
    sql_row = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='order_lines'")
    ).fetchone()
    sql = (sql_row[0] or "") if sql_row else ""
    has_bad_unique = bool(re.search(r"UNIQUE\s*\(\s*order_id\s*,\s*product_id\s*\)", sql, re.I))
    missing_po = "product_offering_id" not in lcols
    if not has_bad_unique and not missing_po:
        return
    if missing_po and not has_bad_unique:
        conn.execute(
            text(
                "ALTER TABLE order_lines ADD COLUMN product_offering_id INTEGER NULL "
                "REFERENCES product_offerings (id)"
            )
        )
        return

    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        conn.execute(text("DROP TABLE IF EXISTS order_lines__mig"))
        conn.execute(
            text(
                """
                CREATE TABLE order_lines__mig (
                    id INTEGER NOT NULL PRIMARY KEY,
                    order_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity FLOAT NOT NULL,
                    unit_price FLOAT NOT NULL,
                    line_total FLOAT NOT NULL,
                    unit_of_measure_id INTEGER,
                    product_offering_id INTEGER,
                    FOREIGN KEY(order_id) REFERENCES orders (id),
                    FOREIGN KEY(product_id) REFERENCES products (id),
                    FOREIGN KEY(unit_of_measure_id) REFERENCES units_of_measure (id),
                    FOREIGN KEY(product_offering_id) REFERENCES product_offerings (id)
                )
                """
            )
        )
        po_sel = "product_offering_id" if "product_offering_id" in lcols else "NULL"
        conn.execute(
            text(
                f"INSERT INTO order_lines__mig "
                f"(id, order_id, product_id, quantity, unit_price, line_total, unit_of_measure_id, product_offering_id) "
                f"SELECT id, order_id, product_id, quantity, unit_price, line_total, unit_of_measure_id, {po_sel} "
                f"FROM order_lines"
            )
        )
        conn.execute(text("DROP TABLE order_lines"))
        conn.execute(text("ALTER TABLE order_lines__mig RENAME TO order_lines"))
    finally:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _reconcile_branches_vs_brands_tables(conn) -> None:
    """
    Fix DBs where `create_all` added empty `brands` while legacy data stayed in `branches`.
    Then product_offerings still referenced `branches`, so new rows in `brands` failed FK checks.
    """
    insp = inspect(conn)
    if not insp.has_table("branches"):
        return
    if not insp.has_table("brands"):
        conn.execute(text("ALTER TABLE branches RENAME TO brands"))
        return
    conn.execute(text("INSERT OR IGNORE INTO brands SELECT * FROM branches"))
    _rebuild_product_offerings_brands_fk(conn, force=True)
    _rebuild_orders_brands_fk(conn, force=True)
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    conn.execute(text("DROP TABLE branches"))
    conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def create_schema(engine) -> None:
    Base.metadata.create_all(engine)
    # Lightweight migration for early dev: add new columns when DB already exists.
    with engine.begin() as conn:
        insp = inspect(conn)
        if insp.has_table("branches") and not insp.has_table("brands"):
            conn.execute(text("ALTER TABLE branches RENAME TO brands"))

        cols = {c["name"] for c in inspect(conn).get_columns("products")}
        if "visible" not in cols:
            conn.execute(text("ALTER TABLE products ADD COLUMN visible BOOLEAN NOT NULL DEFAULT 1"))
        cols = {c["name"] for c in inspect(conn).get_columns("products")}
        if "default_unit_of_measure_id" not in cols:
            conn.execute(text("ALTER TABLE products ADD COLUMN default_unit_of_measure_id INTEGER NULL"))

        def order_col_names() -> set[str]:
            return {c["name"] for c in inspect(conn).get_columns("orders")}

        ocols = order_col_names()
        if "payment_method" not in ocols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(16) NOT NULL DEFAULT 'CASH'"))
        ocols = order_col_names()
        if "amount_received" not in ocols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN amount_received FLOAT NULL"))
        ocols = order_col_names()
        if "change_given" not in ocols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN change_given FLOAT NULL"))
        ocols = order_col_names()
        if "brand_id" not in ocols and "branch_id" in ocols:
            conn.execute(text("ALTER TABLE orders RENAME COLUMN branch_id TO brand_id"))
        elif "brand_id" not in ocols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN brand_id INTEGER NULL"))

        if inspect(conn).has_table("product_offerings"):
            pcols = {c["name"] for c in inspect(conn).get_columns("product_offerings")}
            if "brand_id" not in pcols and "branch_id" in pcols:
                conn.execute(text("ALTER TABLE product_offerings RENAME COLUMN branch_id TO brand_id"))
            pcols = {c["name"] for c in inspect(conn).get_columns("product_offerings")}
            if "stock" not in pcols:
                conn.execute(text("ALTER TABLE product_offerings ADD COLUMN stock FLOAT NOT NULL DEFAULT 0"))
                conn.execute(
                    text(
                        """
                        UPDATE product_offerings SET stock = (
                            SELECT stock FROM products WHERE products.id = product_offerings.product_id
                        )
                        WHERE id IN (
                            SELECT MIN(id) FROM product_offerings GROUP BY product_id
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        UPDATE products SET stock = (
                            SELECT COALESCE(SUM(stock), 0) FROM product_offerings
                            WHERE product_offerings.product_id = products.id
                        )
                        WHERE EXISTS (
                            SELECT 1 FROM product_offerings
                            WHERE product_offerings.product_id = products.id
                        )
                        """
                    )
                )

        if inspect(conn).has_table("inventory_lots"):
            lcols = {c["name"] for c in inspect(conn).get_columns("inventory_lots")}
            if "product_offering_id" not in lcols:
                conn.execute(
                    text(
                        "ALTER TABLE inventory_lots ADD COLUMN product_offering_id INTEGER NULL "
                        "REFERENCES product_offerings (id)"
                    )
                )
                conn.execute(
                    text(
                        """
                        UPDATE inventory_lots SET product_offering_id = (
                            SELECT MIN(id) FROM product_offerings
                            WHERE product_offerings.product_id = inventory_lots.product_id
                        )
                        WHERE product_offering_id IS NULL
                        """
                    )
                )

        if inspect(conn).has_table("order_lines"):
            lcols = {c["name"] for c in inspect(conn).get_columns("order_lines")}
            if "unit_of_measure_id" not in lcols:
                conn.execute(text("ALTER TABLE order_lines ADD COLUMN unit_of_measure_id INTEGER NULL"))

        _migrate_order_lines_remove_order_product_unique(conn)

        _reconcile_branches_vs_brands_tables(conn)


def seed_if_empty(session: Session) -> None:
    # Units of measure (required for product offerings)
    if session.query(UnitOfMeasure).count() == 0:
        session.add_all(
            [
                UnitOfMeasure(name="Unit", abbreviation="u"),
                UnitOfMeasure(name="Kilogram", abbreviation="kg"),
                UnitOfMeasure(name="Gram", abbreviation="g"),
                UnitOfMeasure(name="Liter", abbreviation="L"),
                UnitOfMeasure(name="Milliliter", abbreviation="ml"),
                UnitOfMeasure(name="Pack", abbreviation="pk"),
            ]
        )
        session.flush()

    # Brands (supplier / manufacturer labels for offerings)
    if session.query(Brand).count() == 0:
        session.add(Brand(name="Default", code="DEF"))
        session.flush()

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

    # Product offerings (brand + unit → cost/price) and default UOM on products
    primary_brand = (
        session.query(Brand).filter(Brand.name.in_(["Default", "Main"])).first() or session.query(Brand).first()
    )
    default_uom = session.query(UnitOfMeasure).filter_by(name="Unit").first()
    if primary_brand and default_uom:
        for p in session.query(Product).all():
            if p.default_unit_of_measure_id is None:
                p.default_unit_of_measure_id = default_uom.id
            has_offering = (
                session.query(ProductOffering).filter(ProductOffering.product_id == p.id).first() is not None
            )
            if not has_offering:
                price = float(p.price or 0.0)
                session.add(
                    ProductOffering(
                        product_id=p.id,
                        brand_id=primary_brand.id,
                        unit_of_measure_id=default_uom.id,
                        cost=max(0.0, round(price * 0.75, 2)),
                        price=price,
                        stock=float(p.stock or 0.0),
                    )
                )

    session.commit()

