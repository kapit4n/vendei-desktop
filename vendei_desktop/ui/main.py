from __future__ import annotations

import sys
from datetime import date as _date
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QComboBox,
    QVBoxLayout,
    QWidget,
)

from vendei_desktop.app.container import build_container
from vendei_desktop.app.viewmodels.pos_vm import PosViewModel


class CustomerDialog(QDialog):
    def __init__(self, vm: PosViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select customer")
        self._vm = vm
        self._svc = vm._svc  # pragmatic; can be injected via controller

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search customer…")
        self.list = QListWidget()
        btns = QHBoxLayout()
        ok = QPushButton("Select")
        cancel = QPushButton("Cancel")
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)

        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)
        layout.addLayout(btns)

        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._select)
        self.search.textChanged.connect(self._reload)
        self._reload()

    def _reload(self) -> None:
        self.list.clear()
        q = self.search.text().strip() or None
        for c in self._svc.list_customers(q):
            it = QListWidgetItem(f"{c.name}  ·  {c.document or '—'}")
            it.setData(Qt.ItemDataRole.UserRole, c)
            self.list.addItem(it)

    def _select(self) -> None:
        it = self.list.currentItem()
        if not it:
            return
        c = it.data(Qt.ItemDataRole.UserRole)
        self._vm.set_customer(c)
        self.accept()


class ProductsDialog(QDialog):
    def __init__(self, vm: PosViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Products")
        self.resize(900, 600)
        self._vm = vm
        self._svc = vm._svc  # pragmatic; can be injected via controller

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or code…")
        top.addWidget(self.search, 1)
        layout.addLayout(top)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Image", "Name", "Code", "Price", "Stock", "Visible"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QSize(48, 48))
        layout.addWidget(self.table, 1)

        btns = QHBoxLayout()
        close_btn = QPushButton("Close")
        btns.addStretch(1)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

        close_btn.clicked.connect(self.accept)
        self.search.textChanged.connect(self._reload)
        self._reload()

    def _product_icon(self, image_url: str | None) -> QIcon | None:
        if not image_url:
            return None
        asset_path = Path(__file__).resolve().parent / "assets" / image_url
        if not asset_path.exists():
            return None
        px = QPixmap(str(asset_path))
        if px.isNull():
            return None
        px = px.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return QIcon(px)

    def _reload(self) -> None:
        q = self.search.text().strip() or None
        items = self._svc.list_products(query=q, category_id=None, only_visible=False)

        self.table.setRowCount(len(items))
        for row, p in enumerate(items):
            icon = self._product_icon(getattr(p, "image_url", None))
            img_item = QTableWidgetItem()
            if icon:
                img_item.setIcon(icon)
            self.table.setItem(row, 0, img_item)
            self.table.setItem(row, 1, QTableWidgetItem(str(getattr(p, "name", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(getattr(p, "code", "") or "")))
            self.table.setItem(row, 3, QTableWidgetItem(f"{float(getattr(p, 'price', 0.0)):.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{float(getattr(p, 'stock', 0.0)):.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem("Yes" if bool(getattr(p, "visible", True)) else "No"))

        self.table.resizeColumnsToContents()


class InventoryDialog(QDialog):
    def __init__(self, vm: PosViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Inventory")
        self.resize(980, 640)
        self._vm = vm
        self._svc = vm._svc  # pragmatic; can be injected via controller

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.product = QComboBox()
        self.product.setMinimumContentsLength(40)
        self.product.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        form.addRow("Product", self.product)

        self.qty = QDoubleSpinBox()
        self.qty.setDecimals(3)
        self.qty.setRange(0.001, 1_000_000)
        self.qty.setValue(1.0)
        form.addRow("Quantity to add", self.qty)

        self.batch = QLineEdit()
        self.batch.setPlaceholderText("Optional (creates/updates lots)")
        form.addRow("Batch code", self.batch)

        self.has_expiry = QCheckBox("Set expiry date")
        self.expiry = QDateEdit()
        self.expiry.setCalendarPopup(True)
        self.expiry.setDate(_date.today())
        self.expiry.setEnabled(False)
        self.has_expiry.toggled.connect(self.expiry.setEnabled)
        expiry_row = QHBoxLayout()
        expiry_row.addWidget(self.has_expiry)
        expiry_row.addWidget(self.expiry)
        wrap = QWidget()
        wrap.setLayout(expiry_row)
        form.addRow("Expiry", wrap)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add to inventory")
        self.btn_refresh = QPushButton("Refresh")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.lbl = QLabel("Select a product.")
        self.lbl.setWordWrap(True)
        layout.addWidget(self.lbl)

        self.lots = QTableWidget()
        self.lots.setColumnCount(5)
        self.lots.setHorizontalHeaderLabels(["Lot ID", "Quantity", "Expiry", "Batch", "Received"])
        self.lots.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lots.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.lots.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.lots.verticalHeader().setVisible(False)
        layout.addWidget(self.lots, 1)

        close_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_row.addStretch(1)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)
        close_btn.clicked.connect(self.accept)

        self.btn_add.clicked.connect(self._add)
        self.btn_refresh.clicked.connect(self._reload_details)
        self.product.currentIndexChanged.connect(self._reload_details)

        self._load_products()
        self._reload_details()

    def _product_icon(self, image_url: str | None) -> QIcon | None:
        if not image_url:
            return None
        asset_path = Path(__file__).resolve().parent / "assets" / image_url
        if not asset_path.exists():
            return None
        px = QPixmap(str(asset_path))
        if px.isNull():
            return None
        px = px.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return QIcon(px)

    def _load_products(self) -> None:
        self.product.clear()
        items = self._svc.list_products(query=None, category_id=None, only_visible=False)
        for p in items:
            label = f"{p.name}  ·  {p.code or '—'}"
            icon = self._product_icon(getattr(p, "image_url", None))
            if icon:
                self.product.addItem(icon, label, p.id)
            else:
                self.product.addItem(label, p.id)

    def _selected_product_id(self) -> int | None:
        if self.product.currentIndex() < 0:
            return None
        pid = self.product.currentData()
        return int(pid) if pid is not None else None

    def _reload_details(self) -> None:
        pid = self._selected_product_id()
        if not pid:
            self.lbl.setText("Select a product.")
            self.lots.setRowCount(0)
            return

        p = self._svc.get_product(pid)
        track_expiry = bool(getattr(p, "track_expiry", False)) if p else False
        self.batch.setEnabled(True)
        self.has_expiry.setEnabled(True)

        stock = float(getattr(p, "stock", 0.0) or 0.0) if p else 0.0
        mode = "LOT-TRACKED" if track_expiry else "SIMPLE"
        lots = list(self._svc.list_inventory_lots(pid)) if track_expiry else []
        total_qty = sum(float(getattr(l, "quantity", 0.0) or 0.0) for l in lots) if track_expiry else stock
        name = str(getattr(p, "name", "—")) if p else "—"
        code = str(getattr(p, "code", "") or "—") if p else "—"
        price = float(getattr(p, "price", 0.0) or 0.0) if p else 0.0
        visible = bool(getattr(p, "visible", True)) if p else False
        shelf = getattr(p, "default_shelf_life_days", None) if p else None
        shelf_txt = f"{int(shelf)} days" if shelf is not None else "—"
        mismatch = ""
        if track_expiry and abs(stock - total_qty) > 1e-9:
            mismatch = "  ·  ⚠ Stock != lots sum"
        self.lbl.setText(
            f"<b>{name}</b>  ·  {code}<br>"
            f"Mode: {mode}  ·  Visible: {'Yes' if visible else 'No'}  ·  Price: {price:.2f}<br>"
            f"Stock: {stock:g}  ·  Lots: {len(lots)}  ·  Qty in lots: {total_qty:g}{mismatch}<br>"
            f"Default shelf life: {shelf_txt}"
        )

        rows = lots
        if not track_expiry:
            rows = [None]  # show a single "stock" row

        self.lots.setRowCount(len(rows))
        for row, lot in enumerate(rows):
            if lot is None:
                self.lots.setItem(row, 0, QTableWidgetItem("—"))
                self.lots.setItem(row, 1, QTableWidgetItem(f"{stock:g}"))
                self.lots.setItem(row, 2, QTableWidgetItem("—"))
                self.lots.setItem(row, 3, QTableWidgetItem("—"))
                self.lots.setItem(row, 4, QTableWidgetItem("—"))
                continue

            self.lots.setItem(row, 0, QTableWidgetItem(str(getattr(lot, "id", ""))))
            self.lots.setItem(row, 1, QTableWidgetItem(f"{float(getattr(lot, 'quantity', 0.0) or 0.0):g}"))
            exp = getattr(lot, "expiry_date", None)
            self.lots.setItem(row, 2, QTableWidgetItem(str(exp) if exp else "—"))
            self.lots.setItem(row, 3, QTableWidgetItem(str(getattr(lot, "batch_code", "") or "—")))
            received = getattr(lot, "received_at", None)
            self.lots.setItem(row, 4, QTableWidgetItem(str(received) if received else "—"))
        self.lots.resizeColumnsToContents()

    def _add(self) -> None:
        pid = self._selected_product_id()
        if not pid:
            return
        qty = float(self.qty.value())
        expiry_date = None
        if self.has_expiry.isEnabled() and self.has_expiry.isChecked():
            d = self.expiry.date()
            expiry_date = _date(d.year(), d.month(), d.day())
        try:
            self._svc.add_inventory(
                product_id=pid,
                quantity=qty,
                expiry_date=expiry_date,
                batch_code=self.batch.text(),
            )
        except Exception as e:
            QMessageBox.critical(self, "Inventory add failed", str(e))
            return
        self.batch.setText("")
        self._reload_details()


class PosWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Vendei POS (Desktop)")
        self.resize(1200, 720)

        container = build_container()
        self.vm = PosViewModel(container.pos_service)

        # Layout: left ticket / right catalog
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        right = QWidget()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Left
        l = QVBoxLayout(left)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Current ticket</b>"))
        header.addStretch(1)
        self.btn_clear = QPushButton("Clear")
        header.addWidget(self.btn_clear)
        l.addLayout(header)

        self.ticket = QListWidget()
        l.addWidget(self.ticket, 1)

        self.total = QLabel("Total: Bs 0.00")
        self.total.setAlignment(Qt.AlignmentFlag.AlignRight)
        l.addWidget(self.total)

        cust_row = QHBoxLayout()
        self.cust_lbl = QLabel("Client: Anonymous")
        self.btn_customer = QPushButton("Select or create client")
        cust_row.addWidget(self.cust_lbl, 1)
        cust_row.addWidget(self.btn_customer)
        l.addLayout(cust_row)

        self.btn_pay = QPushButton("Pay / Submit order")
        self.btn_pay.setDefault(True)
        l.addWidget(self.btn_pay)

        # Right (catalog)
        r = QVBoxLayout(right)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search products by name or scan barcode…")
        self.code = QLineEdit()
        self.code.setPlaceholderText("Quick add by code (Enter)")
        top.addWidget(self.search, 1)
        top.addWidget(self.code)
        r.addLayout(top)

        self.products = QListWidget()
        self.products.setViewMode(QListWidget.ViewMode.IconMode)
        self.products.setIconSize(QSize(96, 96))
        self.products.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.products.setWrapping(True)
        self.products.setWordWrap(True)
        self.products.setSpacing(12)
        r.addWidget(self.products, 1)

        self.setCentralWidget(splitter)

        # Menu
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        act_products = QAction("Products", self)
        act_products.triggered.connect(self._open_products)
        act_inventory = QAction("Inventory", self)
        act_inventory.triggered.connect(self._open_inventory)
        self.menuBar().addAction(act_products)
        self.menuBar().addAction(act_inventory)
        self.menuBar().addAction(act_quit)

        # Signals
        self.btn_clear.clicked.connect(self._clear)
        self.btn_customer.clicked.connect(self._pick_customer)
        self.btn_pay.clicked.connect(self._submit)
        self.search.textChanged.connect(self._reload_products)
        self.code.returnPressed.connect(self._quick_add)
        self.products.itemClicked.connect(self._add_clicked)

        self._reload_products()
        self._render_ticket()

    def _open_products(self) -> None:
        dlg = ProductsDialog(self.vm, self)
        dlg.exec()

    def _open_inventory(self) -> None:
        dlg = InventoryDialog(self.vm, self)
        dlg.exec()

    def _product_icon(self, image_url: str | None) -> QIcon | None:
        if not image_url:
            return None
        asset_path = Path(__file__).resolve().parent / "assets" / image_url
        if not asset_path.exists():
            return None
        px = QPixmap(str(asset_path))
        if px.isNull():
            return None
        px = px.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return QIcon(px)

    def _reload_products(self) -> None:
        q = self.search.text().strip() or None
        items = self.vm._svc.list_products(query=q, category_id=None, only_visible=True)
        self.products.clear()
        for p in items:
            it = QListWidgetItem(f"Bs {p.price:.2f}  ·  {p.name}")
            icon = self._product_icon(getattr(p, "image_url", None))
            if icon:
                it.setIcon(icon)
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.products.addItem(it)

    def _render_ticket(self) -> None:
        self.ticket.clear()
        for ln in self.vm.state.lines:
            it = QListWidgetItem(
                f"{ln.quantity:g} × Bs {ln.unit_price:.2f}  ·  {ln.name}  =  Bs {ln.line_total:.2f}"
            )
            icon = self._product_icon(getattr(ln, "image_url", None))
            if icon:
                it.setIcon(icon)
            self.ticket.addItem(it)
        self.total.setText(f"Total: Bs {self.vm.state.total:.2f}")
        doc = self.vm.state.customer_doc or "—"
        self.cust_lbl.setText(f"Client: {self.vm.state.customer_name}  ·  ID: {doc}")

    def _add_clicked(self, item: QListWidgetItem) -> None:
        p = item.data(Qt.ItemDataRole.UserRole)
        self.vm.add_product(p)
        self._render_ticket()

    def _quick_add(self) -> None:
        code = self.code.text().strip()
        if not code:
            return
        p = self.vm._svc.quick_add_by_code(code)
        if not p:
            QMessageBox.information(self, "Not found", f"No product with code: {code}")
            return
        self.vm.add_product(p)
        self.code.setText("")
        self._render_ticket()

    def _clear(self) -> None:
        self.vm.clear_ticket()
        self._render_ticket()

    def _pick_customer(self) -> None:
        dlg = CustomerDialog(self.vm, self)
        dlg.exec()
        self._render_ticket()

    def _submit(self) -> None:
        if not self.vm.state.lines:
            QMessageBox.information(self, "Empty ticket", "Add at least one product.")
            return
        try:
            oid = self.vm.submit()
        except Exception as e:
            QMessageBox.critical(self, "Submit failed", str(e))
            return
        QMessageBox.information(self, "Order saved", f"Order #{oid} saved.\nTotal: Bs {self.vm.state.total:.2f}")
        self.vm.clear_ticket()
        self._render_ticket()


def run_app() -> None:
    app = QApplication(sys.argv)
    w = PosWindow()
    w.show()
    raise SystemExit(app.exec())

