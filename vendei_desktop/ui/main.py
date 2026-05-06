from __future__ import annotations

import sys
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

