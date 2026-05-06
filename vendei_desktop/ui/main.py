from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date as _date, datetime, time, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
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
    QTabWidget,
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
        new_btn = QPushButton("New client")
        ok = QPushButton("Select")
        cancel = QPushButton("Cancel")
        btns.addStretch(1)
        btns.addWidget(new_btn)
        btns.addWidget(cancel)
        btns.addWidget(ok)

        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)
        layout.addLayout(btns)

        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._select)
        new_btn.clicked.connect(self._new_customer)
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

    def _new_customer(self) -> None:
        dlg = NewCustomerDialog(self._svc, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        c = dlg.created
        if not c:
            return
        self._vm.set_customer(c)
        self.accept()


class NewCustomerDialog(QDialog):
    def __init__(self, svc, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New client")
        self._svc = svc
        self.created = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Full name")
        self.doc = QLineEdit()
        self.doc.setPlaceholderText("Document / ID (optional)")
        form.addRow("Name", self.name)
        form.addRow("Document", self.doc)
        layout.addLayout(form)

        btns = QHBoxLayout()
        save = QPushButton("Create")
        cancel = QPushButton("Cancel")
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._create)
        self.name.returnPressed.connect(self._create)

    def _create(self) -> None:
        try:
            c = self._svc.create_customer(name=self.name.text(), document=self.doc.text())
        except Exception as e:
            QMessageBox.critical(self, "Create failed", str(e))
            return
        self.created = c
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


class ClientsDialog(QDialog):
    def __init__(self, vm: PosViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Clients")
        self.resize(760, 560)
        self._vm = vm
        self._svc = vm._svc  # pragmatic; can be injected via controller

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or document…")
        self.btn_new = QPushButton("New client")
        top.addWidget(self.search, 1)
        top.addWidget(self.btn_new)
        layout.addLayout(top)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Document", "ID"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        btns = QHBoxLayout()
        close_btn = QPushButton("Close")
        btns.addStretch(1)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

        close_btn.clicked.connect(self.accept)
        self.search.textChanged.connect(self._reload)
        self.btn_new.clicked.connect(self._new)
        self._reload()

    def _reload(self) -> None:
        q = self.search.text().strip() or None
        items = self._svc.list_customers(q)
        self.table.setRowCount(len(items))
        for row, c in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(str(getattr(c, "name", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(getattr(c, "document", "") or "—")))
            self.table.setItem(row, 2, QTableWidgetItem(str(getattr(c, "id", ""))))
        self.table.resizeColumnsToContents()

    def _new(self) -> None:
        dlg = NewCustomerDialog(self._svc, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._reload()


@dataclass(frozen=True)
class SalesRow:
    label: str
    orders: int
    total: float


class SalesReportDialog(QDialog):
    def __init__(self, vm: PosViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sales report")
        self.resize(860, 600)
        self._svc = vm._svc  # pragmatic; can be injected via controller

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self._tab_daily = self._make_range_tab("Daily")
        self._tab_weekly = self._make_range_tab("Weekly")
        self._tab_monthly = self._make_range_tab("Monthly")
        self._tab_yearly = self._make_range_tab("Yearly")
        self._tab_custom = self._make_custom_tab()
        self._tab_today_details = self._make_today_details_tab()

        self.tabs.addTab(self._tab_daily["root"], "Daily")
        self.tabs.addTab(self._tab_weekly["root"], "Weekly")
        self.tabs.addTab(self._tab_monthly["root"], "Monthly")
        self.tabs.addTab(self._tab_yearly["root"], "Yearly")
        self.tabs.addTab(self._tab_custom["root"], "Custom range")
        self.tabs.addTab(self._tab_today_details["root"], "Today (detailed)")

        close_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_row.addStretch(1)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)
        close_btn.clicked.connect(self.accept)

        self._refresh_active()
        self.tabs.currentChanged.connect(lambda *_: self._refresh_active())

    def _make_table(self) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(3)
        t.setHorizontalHeaderLabels(["Period", "Orders", "Total"])
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        t.verticalHeader().setVisible(False)
        return t

    def _make_range_tab(self, title: str):
        root = QWidget()
        layout = QVBoxLayout(root)

        row = QHBoxLayout()
        row.addWidget(QLabel("From"))
        start = QDateEdit()
        start.setCalendarPopup(True)
        row.addWidget(start)
        row.addWidget(QLabel("To"))
        end = QDateEdit()
        end.setCalendarPopup(True)
        row.addWidget(end)
        refresh = QPushButton("Refresh")
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)

        summary = QLabel("")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        table = self._make_table()
        layout.addWidget(table, 1)

        # defaults: last 30 days
        today = _date.today()
        start.setDate(today - timedelta(days=30))
        end.setDate(today)

        refresh.clicked.connect(lambda *_: self._refresh_tab(title.lower()))

        return {"root": root, "start": start, "end": end, "refresh": refresh, "summary": summary, "table": table}

    def _make_custom_tab(self):
        root = QWidget()
        layout = QVBoxLayout(root)

        row = QHBoxLayout()
        row.addWidget(QLabel("From"))
        start = QDateEdit()
        start.setCalendarPopup(True)
        row.addWidget(start)
        row.addWidget(QLabel("To"))
        end = QDateEdit()
        end.setCalendarPopup(True)
        row.addWidget(end)
        refresh = QPushButton("Refresh")
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)

        summary = QLabel("")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        table = self._make_table()
        layout.addWidget(table, 1)

        today = _date.today()
        start.setDate(today - timedelta(days=7))
        end.setDate(today)

        refresh.clicked.connect(lambda *_: self._refresh_tab("custom"))

        return {"root": root, "start": start, "end": end, "refresh": refresh, "summary": summary, "table": table}

    def _active_key(self) -> str:
        i = self.tabs.currentIndex()
        return ["daily", "weekly", "monthly", "yearly", "custom", "today_details"][i] if i >= 0 else "daily"

    def _refresh_active(self) -> None:
        self._refresh_tab(self._active_key())

    def _range_for(self, key: str):
        tab = {
            "daily": self._tab_daily,
            "weekly": self._tab_weekly,
            "monthly": self._tab_monthly,
            "yearly": self._tab_yearly,
            "custom": self._tab_custom,
        }[key]
        start_d = tab["start"].date()
        end_d = tab["end"].date()
        start = datetime.combine(_date(start_d.year(), start_d.month(), start_d.day()), time.min)
        # inclusive end date in UI -> exclusive end datetime
        end = datetime.combine(_date(end_d.year(), end_d.month(), end_d.day()), time.min) + timedelta(days=1)
        return tab, start, end

    def _aggregate(self, key: str, orders) -> list[SalesRow]:
        buckets: dict[str, list[float]] = defaultdict(list)
        for o in orders:
            dt = getattr(o, "created_at", None)
            total = float(getattr(o, "total", 0.0) or 0.0)
            if not dt:
                continue

            if key == "daily":
                label = dt.date().isoformat()
            elif key == "weekly":
                y, w, _ = dt.isocalendar()
                label = f"{y}-W{w:02d}"
            elif key == "monthly":
                label = f"{dt.year:04d}-{dt.month:02d}"
            elif key == "yearly":
                label = f"{dt.year:04d}"
            else:  # custom -> daily breakdown
                label = dt.date().isoformat()

            buckets[label].append(total)

        rows: list[SalesRow] = []
        for label in sorted(buckets.keys()):
            totals = buckets[label]
            rows.append(SalesRow(label=label, orders=len(totals), total=round(sum(totals), 2)))
        return rows

    def _render(self, tab, *, key: str, rows: list[SalesRow], start: datetime, end: datetime) -> None:
        total_orders = sum(r.orders for r in rows)
        total_amount = round(sum(r.total for r in rows), 2)
        tab["summary"].setText(
            f"Range: {start.date().isoformat()} → {(end - timedelta(days=1)).date().isoformat()}  ·  "
            f"Orders: {total_orders}  ·  Total: {total_amount:.2f}"
        )

        t = tab["table"]
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(r.label))
            t.setItem(i, 1, QTableWidgetItem(str(r.orders)))
            t.setItem(i, 2, QTableWidgetItem(f"{r.total:.2f}"))
        t.resizeColumnsToContents()

    def _refresh_tab(self, key: str) -> None:
        if key == "today_details":
            self._refresh_today_details()
            return
        tab, start, end = self._range_for(key)
        orders = list(self._svc.list_orders_between(start=start, end=end))
        rows = self._aggregate(key, orders)
        self._render(tab, key=key, rows=rows, start=start, end=end)

    def _make_today_details_tab(self):
        root = QWidget()
        layout = QVBoxLayout(root)

        row = QHBoxLayout()
        self._today_lbl = QLabel("")
        self._today_lbl.setWordWrap(True)
        refresh = QPushButton("Refresh")
        row.addWidget(self._today_lbl, 1)
        row.addWidget(refresh)
        layout.addLayout(row)

        self._orders_tbl = QTableWidget()
        self._orders_tbl.setColumnCount(5)
        self._orders_tbl.setHorizontalHeaderLabels(["Time", "Order #", "Customer", "Items", "Total"])
        self._orders_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._orders_tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._orders_tbl.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._orders_tbl.verticalHeader().setVisible(False)
        layout.addWidget(self._orders_tbl, 1)

        self._lines_tbl = QTableWidget()
        self._lines_tbl.setColumnCount(5)
        self._lines_tbl.setHorizontalHeaderLabels(["Product", "Qty", "Unit price", "Line total", "Product ID"])
        self._lines_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._lines_tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._lines_tbl.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._lines_tbl.verticalHeader().setVisible(False)
        layout.addWidget(self._lines_tbl, 1)

        refresh.clicked.connect(self._refresh_today_details)
        self._orders_tbl.itemSelectionChanged.connect(self._refresh_selected_order_lines)

        return {"root": root}

    def _refresh_today_details(self) -> None:
        today = _date.today()
        start = datetime.combine(today, time.min)
        end = start + timedelta(days=1)

        orders = list(self._svc.list_orders_between(start=start, end=end))
        total_amount = round(sum(float(getattr(o, "total", 0.0) or 0.0) for o in orders), 2)
        self._today_lbl.setText(f"Date: {today.isoformat()}  ·  Orders: {len(orders)}  ·  Total: {total_amount:.2f}")

        self._orders_tbl.setRowCount(len(orders))
        for row, o in enumerate(orders):
            created = getattr(o, "created_at", None)
            created_txt = created.strftime("%H:%M:%S") if created else "—"
            oid = int(getattr(o, "id", 0) or 0)
            cust = getattr(o, "customer", None)
            cust_name = str(getattr(cust, "name", "") or "Anonymous") if cust else "Anonymous"
            lines = list(getattr(o, "lines", []) or [])
            items = sum(float(getattr(ln, "quantity", 0.0) or 0.0) for ln in lines) if lines else 0.0
            total = float(getattr(o, "total", 0.0) or 0.0)

            it0 = QTableWidgetItem(created_txt)
            it1 = QTableWidgetItem(str(oid))
            it1.setData(Qt.ItemDataRole.UserRole, oid)
            self._orders_tbl.setItem(row, 0, it0)
            self._orders_tbl.setItem(row, 1, it1)
            self._orders_tbl.setItem(row, 2, QTableWidgetItem(cust_name))
            self._orders_tbl.setItem(row, 3, QTableWidgetItem(f"{items:g}"))
            self._orders_tbl.setItem(row, 4, QTableWidgetItem(f"{total:.2f}"))

        self._orders_tbl.resizeColumnsToContents()

        # reset lines table until an order is selected
        self._lines_tbl.setRowCount(0)
        if orders:
            self._orders_tbl.selectRow(0)
            self._refresh_selected_order_lines()

    def _selected_order_id(self) -> int | None:
        items = self._orders_tbl.selectedItems()
        if not items:
            return None
        # Order # column stores the id in UserRole
        it = self._orders_tbl.item(items[0].row(), 1)
        if not it:
            return None
        oid = it.data(Qt.ItemDataRole.UserRole)
        return int(oid) if oid is not None else None

    def _refresh_selected_order_lines(self) -> None:
        oid = self._selected_order_id()
        if not oid:
            self._lines_tbl.setRowCount(0)
            return
        o = self._svc.get_order_with_lines(oid)
        lines = list(getattr(o, "lines", []) or []) if o else []

        self._lines_tbl.setRowCount(len(lines))
        for row, ln in enumerate(lines):
            prod = getattr(ln, "product", None)
            prod_name = str(getattr(prod, "name", "") or f"Product #{getattr(ln, 'product_id', '—')}")
            qty = float(getattr(ln, "quantity", 0.0) or 0.0)
            unit = float(getattr(ln, "unit_price", 0.0) or 0.0)
            total = float(getattr(ln, "line_total", 0.0) or 0.0)
            pid = int(getattr(ln, "product_id", 0) or 0)

            self._lines_tbl.setItem(row, 0, QTableWidgetItem(prod_name))
            self._lines_tbl.setItem(row, 1, QTableWidgetItem(f"{qty:g}"))
            self._lines_tbl.setItem(row, 2, QTableWidgetItem(f"{unit:.2f}"))
            self._lines_tbl.setItem(row, 3, QTableWidgetItem(f"{total:.2f}"))
            self._lines_tbl.setItem(row, 4, QTableWidgetItem(str(pid)))

        self._lines_tbl.resizeColumnsToContents()


class ReorderDialog(QDialog):
    def __init__(self, vm: PosViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reorder / Purchase request")
        self.resize(980, 650)
        self._svc = vm._svc  # pragmatic; can be injected via controller

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search products…")
        self.btn_refresh = QPushButton("Refresh")
        top.addWidget(self.search, 1)
        top.addWidget(self.btn_refresh)
        layout.addLayout(top)

        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        layout.addWidget(self.lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Image", "Name", "Code", "Stock", "Out", "Request", "Qty"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setIconSize(QSize(32, 32))
        layout.addWidget(self.table, 1)

        close_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_row.addStretch(1)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)
        close_btn.clicked.connect(self.accept)

        self.btn_refresh.clicked.connect(self._reload)
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
        px = px.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return QIcon(px)

    def _reload(self) -> None:
        q = self.search.text().strip() or None
        products = self._svc.list_products(query=q, category_id=None, only_visible=False)

        pr = self._svc.get_open_purchase_request()
        requested = {int(it.product_id): float(it.quantity) for it in getattr(pr, "items", []) or []}

        self.table.setRowCount(len(products))
        out_brush = QBrush(QColor(180, 0, 0))

        for row, p in enumerate(products):
            pid = int(getattr(p, "id", 0) or 0)
            stock = float(getattr(p, "stock", 0.0) or 0.0)
            out = stock <= 0

            icon = self._product_icon(getattr(p, "image_url", None))
            img_item = QTableWidgetItem()
            if icon:
                img_item.setIcon(icon)
            self.table.setItem(row, 0, img_item)

            name_item = QTableWidgetItem(str(getattr(p, "name", "")))
            code_item = QTableWidgetItem(str(getattr(p, "code", "") or "—"))
            stock_item = QTableWidgetItem(f"{stock:g}")
            out_item = QTableWidgetItem("YES" if out else "")

            if out:
                for it in (name_item, code_item, stock_item, out_item):
                    it.setForeground(out_brush)

            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, code_item)
            self.table.setItem(row, 3, stock_item)
            self.table.setItem(row, 4, out_item)

            cb = QCheckBox()
            cb.setChecked(pid in requested)
            self.table.setCellWidget(row, 5, cb)

            qty = QDoubleSpinBox()
            qty.setDecimals(3)
            qty.setRange(0.001, 1_000_000)
            qty.setValue(max(0.001, requested.get(pid, 1.0)))
            qty.setEnabled(cb.isChecked())
            self.table.setCellWidget(row, 6, qty)

            def on_toggle(checked: bool, product_id: int = pid, spin: QDoubleSpinBox = qty) -> None:
                spin.setEnabled(checked)
                try:
                    if checked:
                        self._svc.set_purchase_request_item(product_id=product_id, quantity=float(spin.value()))
                    else:
                        self._svc.remove_purchase_request_item(product_id=product_id)
                except Exception as e:
                    QMessageBox.critical(self, "Request update failed", str(e))

            def on_qty_change(_v: float, product_id: int = pid, spin: QDoubleSpinBox = qty, box: QCheckBox = cb) -> None:
                if not box.isChecked():
                    return
                try:
                    self._svc.set_purchase_request_item(product_id=product_id, quantity=float(spin.value()))
                except Exception as e:
                    QMessageBox.critical(self, "Request update failed", str(e))

            cb.toggled.connect(on_toggle)
            qty.valueChanged.connect(on_qty_change)

        requested_count = len(requested)
        self.lbl.setText(f"Open request #{getattr(pr, 'id', '—')}  ·  Items requested: {requested_count}")
        self.table.resizeColumnsToContents()


class ProductCard(QFrame):
    def __init__(self, *, title: str, subtitle: str, badge: str, icon: QIcon | None, on_add) -> None:
        super().__init__()
        self.setObjectName("ProductCard")
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        img = QLabel()
        img.setFixedSize(64, 64)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icon:
            img.setPixmap(icon.pixmap(64, 64))
        else:
            img.setText("No\nimg")
        root.addWidget(img)

        mid = QVBoxLayout()
        mid.setSpacing(4)
        name = QLabel(title)
        name.setObjectName("ProductCardTitle")
        name.setWordWrap(True)
        meta = QLabel(subtitle)
        meta.setObjectName("ProductCardSubtitle")
        meta.setWordWrap(True)
        mid.addWidget(name)
        mid.addWidget(meta)
        root.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(6)
        stock = QLabel(badge)
        stock.setObjectName("ProductCardBadge")
        stock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stock.setWordWrap(True)
        stock.setMinimumWidth(120)
        qty = QDoubleSpinBox()
        qty.setDecimals(0)
        qty.setRange(1, 1_000_000)
        qty.setValue(1)
        qty.setObjectName("ProductCardQty")

        btn = QPushButton("Add")
        btn.setObjectName("ProductCardAdd")

        def add_clicked() -> None:
            on_add(float(qty.value()))

        btn.clicked.connect(add_clicked)
        right.addWidget(stock)
        right.addWidget(qty)
        right.addWidget(btn)
        right.addStretch(1)
        root.addLayout(right)


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
        self.products.setUniformItemSizes(False)
        r.addWidget(self.products, 1)

        self.setCentralWidget(splitter)

        # Menu
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        act_products = QAction("Products", self)
        act_products.triggered.connect(self._open_products)
        act_clients = QAction("Clients", self)
        act_clients.triggered.connect(self._open_clients)
        act_inventory = QAction("Inventory", self)
        act_inventory.triggered.connect(self._open_inventory)
        act_sales = QAction("Sales report", self)
        act_sales.triggered.connect(self._open_sales)
        act_reorder = QAction("Reorder", self)
        act_reorder.triggered.connect(self._open_reorder)
        self.menuBar().addAction(act_products)
        self.menuBar().addAction(act_clients)
        self.menuBar().addAction(act_inventory)
        self.menuBar().addAction(act_sales)
        self.menuBar().addAction(act_reorder)
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

    def _open_clients(self) -> None:
        dlg = ClientsDialog(self.vm, self)
        dlg.exec()

    def _open_inventory(self) -> None:
        dlg = InventoryDialog(self.vm, self)
        dlg.exec()

    def _open_sales(self) -> None:
        dlg = SalesReportDialog(self.vm, self)
        dlg.exec()

    def _open_reorder(self) -> None:
        dlg = ReorderDialog(self.vm, self)
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
            icon = self._product_icon(getattr(p, "image_url", None))
            stock = float(getattr(p, "stock", 0.0) or 0.0)
            out = stock <= 0
            badge = "OUT OF STOCK" if out else f"Stock: {stock:g}"
            subtitle = f"Bs {float(getattr(p, 'price', 0.0) or 0.0):.2f}"

            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, p)
            it.setSizeHint(QSize(340, 110))
            self.products.addItem(it)

            def on_add(_checked: bool = False, product=p) -> None:
                self.vm.add_product(product)
                self._render_ticket()

            def on_add_qty(qty: float, product=p) -> None:
                self.vm.add_product(product, quantity=qty)
                self._render_ticket()

            card = ProductCard(
                title=str(getattr(p, "name", "")),
                subtitle=subtitle,
                badge=badge,
                icon=icon,
                on_add=on_add_qty,
            )
            if out:
                card.setProperty("outOfStock", True)
            self.products.setItemWidget(it, card)

        # Keep the app readable under light system themes:
        # only style the product cards, don't force a dark palette globally.
        self.products.setStyleSheet(
            """
            QListWidget { background: transparent; border: none; }
            QFrame#ProductCard {
              background: #ffffff;
              border: 1px solid #e5e7eb;
              border-radius: 14px;
            }
            QFrame#ProductCard[outOfStock="true"] { border: 1px solid #fca5a5; }
            QLabel#ProductCardTitle { font-weight: 650; font-size: 14px; color: #111827; }
            QLabel#ProductCardSubtitle { color: #374151; }
            QLabel#ProductCardBadge {
              background: #f3f4f6;
              border: 1px solid #e5e7eb;
              color: #111827;
              border-radius: 10px;
              padding: 6px 8px;
              font-weight: 650;
              min-height: 34px;
            }
            QPushButton#ProductCardAdd { font-weight: 700; }
            """
        )

    def _render_ticket(self) -> None:
        self.ticket.clear()
        for ln in self.vm.state.lines:
            it = QListWidgetItem()
            icon = self._product_icon(getattr(ln, "image_url", None))
            if icon:
                it.setIcon(icon)
            it.setSizeHint(QSize(520, 46))
            self.ticket.addItem(it)

            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(8, 6, 8, 6)
            lay.setSpacing(8)

            name = QLabel(ln.name)
            name.setWordWrap(True)
            lay.addWidget(name, 1)

            unit = QLabel(f"Bs {ln.unit_price:.2f}")
            unit.setMinimumWidth(90)
            unit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(unit)

            qty = QDoubleSpinBox()
            qty.setDecimals(0)
            qty.setRange(1, 1_000_000)
            qty.setValue(float(ln.quantity))
            qty.setMinimumWidth(80)
            lay.addWidget(qty)

            line_total = QLabel(f"Bs {ln.line_total:.2f}")
            line_total.setMinimumWidth(110)
            line_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(line_total)

            rm = QPushButton("Remove")
            lay.addWidget(rm)

            def on_qty_change(_v: float, product_id: int = ln.product_id, unit_price: float = ln.unit_price) -> None:
                qv = float(qty.value())
                self.vm.set_line_quantity(product_id=product_id, quantity=qv)
                line_total.setText(f"Bs {qv * float(unit_price):.2f}")
                self.total.setText(f"Total: Bs {self.vm.state.total:.2f}")

            def on_remove(_checked: bool = False, product_id: int = ln.product_id) -> None:
                self.vm.set_line_quantity(product_id=product_id, quantity=0)
                self._render_ticket()

            qty.valueChanged.connect(on_qty_change)
            rm.clicked.connect(on_remove)

            self.ticket.setItemWidget(it, row)
        self.total.setText(f"Total: Bs {self.vm.state.total:.2f}")
        doc = self.vm.state.customer_doc or "—"
        self.cust_lbl.setText(f"Client: {self.vm.state.customer_name}  ·  ID: {doc}")

    def _add_clicked(self, item: QListWidgetItem) -> None:
        p = item.data(Qt.ItemDataRole.UserRole)
        self.vm.add_product(p, quantity=1)
        self._render_ticket()

    def _quick_add(self) -> None:
        code = self.code.text().strip()
        if not code:
            return
        p = self.vm._svc.quick_add_by_code(code)
        if not p:
            QMessageBox.information(self, "Not found", f"No product with code: {code}")
            return
        self.vm.add_product(p, quantity=1)
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
        # Reload catalog to reflect reduced stock after submit.
        self._reload_products()


def run_app() -> None:
    app = QApplication(sys.argv)
    w = PosWindow()
    w.show()
    raise SystemExit(app.exec())

