from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as _date, datetime, time, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QComboBox,
    QTabWidget,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vendei_desktop.app.container import build_container
from vendei_desktop.app.services.pos_service import ProductListing
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


class UnitsOfMeasureDialog(QDialog):
    def __init__(self, svc, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Units of measure")
        self.resize(560, 420)
        self._svc = svc
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.btn_new = QPushButton("New unit")
        top.addWidget(self.btn_new)
        top.addStretch(1)
        layout.addLayout(top)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Abbreviation", "ID"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)
        bot = QHBoxLayout()
        self.btn_delete = QPushButton("Delete selected")
        close_btn = QPushButton("Close")
        bot.addWidget(self.btn_delete)
        bot.addStretch(1)
        bot.addWidget(close_btn)
        layout.addLayout(bot)
        self.btn_new.clicked.connect(self._new)
        self.btn_delete.clicked.connect(self._delete)
        close_btn.clicked.connect(self.accept)
        self._reload()

    def _reload(self) -> None:
        items = self._svc.list_units_of_measure()
        self.table.setRowCount(len(items))
        for row, u in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(str(getattr(u, "name", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(getattr(u, "abbreviation", "") or "—")))
            self.table.setItem(row, 2, QTableWidgetItem(str(getattr(u, "id", ""))))
        self.table.resizeColumnsToContents()

    def _new(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("New unit of measure")
        form = QFormLayout(dlg)
        name = QLineEdit()
        abbr = QLineEdit()
        form.addRow("Name", name)
        form.addRow("Abbreviation (optional)", abbr)
        row = QHBoxLayout()
        ok = QPushButton("Create")
        cancel = QPushButton("Cancel")
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(ok)
        form.addRow(row)
        cancel.clicked.connect(dlg.reject)
        ok.clicked.connect(dlg.accept)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._svc.create_unit_of_measure(name=name.text(), abbreviation=abbr.text())
        except Exception as e:
            QMessageBox.critical(self, "Create failed", str(e))
            return
        self._reload()

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        it = self.table.item(row, 2)
        if not it:
            return
        uid = int(it.text())
        if (
            QMessageBox.question(
                self,
                "Delete unit",
                "Delete this unit of measure?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self._svc.delete_unit_of_measure(uid)
        except Exception as e:
            QMessageBox.warning(self, "Cannot delete", str(e))
            return
        self._reload()


class BrandsDialog(QDialog):
    def __init__(self, svc, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Brands")
        self.resize(560, 420)
        self._svc = svc
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.btn_new = QPushButton("New brand")
        top.addWidget(self.btn_new)
        top.addStretch(1)
        layout.addLayout(top)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Code", "ID"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)
        bot = QHBoxLayout()
        self.btn_delete = QPushButton("Delete selected")
        close_btn = QPushButton("Close")
        bot.addWidget(self.btn_delete)
        bot.addStretch(1)
        bot.addWidget(close_btn)
        layout.addLayout(bot)
        self.btn_new.clicked.connect(self._new)
        self.btn_delete.clicked.connect(self._delete)
        close_btn.clicked.connect(self.accept)
        self._reload()

    def _reload(self) -> None:
        items = self._svc.list_brands()
        self.table.setRowCount(len(items))
        for row, b in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(str(getattr(b, "name", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(getattr(b, "code", "") or "—")))
            self.table.setItem(row, 2, QTableWidgetItem(str(getattr(b, "id", ""))))
        self.table.resizeColumnsToContents()

    def _new(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("New brand")
        form = QFormLayout(dlg)
        name = QLineEdit()
        code = QLineEdit()
        form.addRow("Name", name)
        form.addRow("Code (optional)", code)
        row = QHBoxLayout()
        ok = QPushButton("Create")
        cancel = QPushButton("Cancel")
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(ok)
        form.addRow(row)
        cancel.clicked.connect(dlg.reject)
        ok.clicked.connect(dlg.accept)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._svc.create_brand(name=name.text(), code=code.text() or None)
        except Exception as e:
            QMessageBox.critical(self, "Create failed", str(e))
            return
        self._reload()

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        it = self.table.item(row, 2)
        if not it:
            return
        bid = int(it.text())
        if (
            QMessageBox.question(
                self,
                "Delete brand",
                "Delete this brand?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self._svc.delete_brand(bid)
        except Exception as e:
            QMessageBox.warning(self, "Cannot delete", str(e))
            return
        self._reload()


class RegisterProductDialog(QDialog):
    def __init__(
        self, svc, parent: QWidget | None = None, *, edit_product_id: int | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit product" if edit_product_id is not None else "Register product")
        self.resize(640, 640)
        self._svc = svc
        self.created = None
        self._edit_product_id = edit_product_id

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit()
        self.name.setPlaceholderText("Product name")
        form.addRow("Name", self.name)

        self.code = QLineEdit()
        self.code.setPlaceholderText("Barcode / SKU (optional)")
        form.addRow("Code", self.code)

        self.default_uom = QComboBox()
        for u in self._svc.list_units_of_measure():
            ab = getattr(u, "abbreviation", None) or "—"
            self.default_uom.addItem(f"{u.name} ({ab})", int(u.id))
        form.addRow("Default unit (for POS)", self.default_uom)

        self.category = QComboBox()
        self.category.addItem("— No category", None)
        for c in self._svc.list_categories():
            self.category.addItem(str(getattr(c, "name", "")), int(getattr(c, "id", 0)))
        form.addRow("Category", self.category)

        self.visible = QCheckBox("Show in POS catalog")
        self.visible.setChecked(True)
        form.addRow("", self.visible)

        self.track_expiry = QCheckBox("Track batches / expiry for this product")
        form.addRow("", self.track_expiry)

        self.shelf_days = QSpinBox()
        self.shelf_days.setRange(0, 3650)
        self.shelf_days.setSpecialValueText("—")
        self.shelf_days.setValue(0)
        form.addRow("Default shelf life (days)", self.shelf_days)

        self.image_url = QLineEdit()
        self.image_url.setPlaceholderText("Optional: file under ui/assets (e.g. apple.png)")
        form.addRow("Image", self.image_url)

        layout.addLayout(form)

        layout.addWidget(QLabel("<b>Prices by brand and unit</b> (cost and sell price per row):"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._rows_host)
        layout.addWidget(scroll, 1)

        self._offering_rows: list[QWidget] = []
        add_row_btn = QPushButton("Add brand / unit row")
        add_row_btn.clicked.connect(lambda: self._add_offering_row())
        layout.addWidget(add_row_btn)

        self._opening_block = QWidget()
        opening_outer = QVBoxLayout(self._opening_block)
        opening_outer.setContentsMargins(0, 0, 0, 0)
        self.opening_stock = QDoubleSpinBox()
        self.opening_stock.setDecimals(3)
        self.opening_stock.setRange(0.0, 1_000_000.0)
        self.opening_stock.setValue(0.0)
        oform = QFormLayout()
        oform.addRow("Opening stock", self.opening_stock)
        self.opening_batch = QLineEdit()
        self.opening_batch.setPlaceholderText("Optional (creates a lot if expiry tracking)")
        oform.addRow("Opening batch code", self.opening_batch)
        open_exp_row = QHBoxLayout()
        self.opening_has_expiry = QCheckBox("Opening lot expiry")
        self.opening_expiry = QDateEdit()
        self.opening_expiry.setCalendarPopup(True)
        self.opening_expiry.setDate(_date.today())
        self.opening_expiry.setEnabled(False)
        self.opening_has_expiry.toggled.connect(self.opening_expiry.setEnabled)
        open_exp_row.addWidget(self.opening_has_expiry)
        open_exp_row.addWidget(self.opening_expiry)
        open_exp_wrap = QWidget()
        open_exp_wrap.setLayout(open_exp_row)
        oform.addRow("", open_exp_wrap)
        opening_outer.addLayout(oform)
        layout.addWidget(self._opening_block)
        self._opening_block.setVisible(edit_product_id is None)

        btns = QHBoxLayout()
        save = QPushButton("Save" if edit_product_id is not None else "Register")
        cancel = QPushButton("Cancel")
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        self.name.returnPressed.connect(self._save)

        if edit_product_id is not None:
            self._load_for_edit(int(edit_product_id))
        else:
            self._add_offering_row()

    def _clear_offering_rows(self) -> None:
        for row in list(self._offering_rows):
            self._rows_layout.removeWidget(row)
            row.deleteLater()
        self._offering_rows.clear()

    def _load_for_edit(self, pid: int) -> None:
        p = self._svc.get_product(pid)
        if not p:
            QMessageBox.critical(self, "Not found", "This product no longer exists.")
            self.reject()
            return
        self.name.setText(str(p.name))
        self.code.setText(str(p.code or ""))
        du = p.default_unit_of_measure_id
        if du is not None:
            ix = self.default_uom.findData(int(du))
            if ix >= 0:
                self.default_uom.setCurrentIndex(ix)
        cid = p.category_id
        if cid is not None:
            cix = self.category.findData(int(cid))
            if cix >= 0:
                self.category.setCurrentIndex(cix)
        self.visible.setChecked(bool(p.visible))
        self.track_expiry.setChecked(bool(p.track_expiry))
        sld = p.default_shelf_life_days
        if sld is not None and int(sld) > 0:
            self.shelf_days.setValue(int(sld))
        else:
            self.shelf_days.setValue(0)
        self.image_url.setText(str(p.image_url or ""))

        self._clear_offering_rows()
        offs = self._svc.list_product_offerings(pid)
        for o in offs:
            self._add_offering_row(
                brand_id=int(o.brand_id),
                unit_id=int(o.unit_of_measure_id),
                cost_val=float(o.cost),
                price_val=float(o.price),
            )
        if not self._offering_rows:
            self._add_offering_row()

    def _add_offering_row(
        self,
        *,
        brand_id: int | None = None,
        unit_id: int | None = None,
        cost_val: float | None = None,
        price_val: float | None = None,
    ) -> None:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 2)
        b_combo = QComboBox()
        for br in self._svc.list_brands():
            b_combo.addItem(str(br.name), int(br.id))
        u_combo = QComboBox()
        for u in self._svc.list_units_of_measure():
            ab = getattr(u, "abbreviation", None) or "—"
            u_combo.addItem(f"{u.name} ({ab})", int(u.id))
        cost = QDoubleSpinBox()
        cost.setDecimals(2)
        cost.setRange(0.0, 1_000_000.0)
        price = QDoubleSpinBox()
        price.setDecimals(2)
        price.setRange(0.0, 1_000_000.0)
        rm = QPushButton("Remove")

        def on_remove() -> None:
            if len(self._offering_rows) <= 1:
                QMessageBox.information(self, "Row required", "Keep at least one brand / unit / price row.")
                return
            self._rows_layout.removeWidget(row)
            self._offering_rows.remove(row)
            row.deleteLater()

        rm.clicked.connect(on_remove)
        h.addWidget(QLabel("Brand"))
        h.addWidget(b_combo, 1)
        h.addWidget(QLabel("Unit"))
        h.addWidget(u_combo, 1)
        h.addWidget(QLabel("Cost"))
        h.addWidget(cost)
        h.addWidget(QLabel("Price"))
        h.addWidget(price)
        h.addWidget(rm)
        setattr(row, "_brand_combo", b_combo)
        setattr(row, "_uom_combo", u_combo)
        setattr(row, "_cost", cost)
        setattr(row, "_price", price)
        self._offering_rows.append(row)
        self._rows_layout.addWidget(row)

        if brand_id is not None:
            ix = b_combo.findData(int(brand_id))
            if ix >= 0:
                b_combo.setCurrentIndex(ix)
        if unit_id is not None:
            ix = u_combo.findData(int(unit_id))
            if ix >= 0:
                u_combo.setCurrentIndex(ix)
        if cost_val is not None:
            cost.setValue(float(cost_val))
        if price_val is not None:
            price.setValue(float(price_val))

    def _collect_offerings(self) -> list[tuple[int, int, float, float]]:
        seen: set[tuple[int, int]] = set()
        out: list[tuple[int, int, float, float]] = []
        for row in self._offering_rows:
            b_combo = getattr(row, "_brand_combo")
            u_combo = getattr(row, "_uom_combo")
            cost = getattr(row, "_cost")
            price = getattr(row, "_price")
            bid_raw = b_combo.currentData()
            uid_raw = u_combo.currentData()
            if bid_raw is None or uid_raw is None:
                raise ValueError("Every row needs a brand and a unit of measure.")
            bid = int(bid_raw)
            uid = int(uid_raw)
            key = (bid, uid)
            if key in seen:
                raise ValueError("Each brand + unit combination must appear only once.")
            seen.add(key)
            out.append((bid, uid, float(cost.value()), float(price.value())))
        return out

    def _save(self) -> None:
        nm = self.name.text().strip()
        if not nm:
            QMessageBox.warning(self, "Name required", "Enter a product name.")
            return
        if not self._svc.list_brands() or not self._svc.list_units_of_measure():
            QMessageBox.warning(self, "Setup", "Create at least one brand and one unit of measure first.")
            return
        try:
            offerings = self._collect_offerings()
        except ValueError as e:
            QMessageBox.warning(self, "Offerings", str(e))
            return

        cat_data = self.category.currentData()
        category_id = int(cat_data) if cat_data is not None else None
        shelf = self.shelf_days.value()
        default_shelf = int(shelf) if shelf > 0 else None
        du_data = self.default_uom.currentData()
        if du_data is None:
            QMessageBox.warning(self, "Default unit", "Select a default unit of measure.")
            return
        default_uom_id = int(du_data)

        try:
            if self._edit_product_id is not None:
                p = self._svc.update_product(
                    int(self._edit_product_id),
                    name=nm,
                    code=self.code.text().strip() or None,
                    category_id=category_id,
                    visible=self.visible.isChecked(),
                    image_url=self.image_url.text().strip() or None,
                    track_expiry=self.track_expiry.isChecked(),
                    default_shelf_life_days=default_shelf,
                    default_unit_of_measure_id=default_uom_id,
                    offerings=offerings,
                )
            else:
                opening_qty = float(self.opening_stock.value())
                exp = None
                if opening_qty > 0 and self.opening_has_expiry.isChecked():
                    d = self.opening_expiry.date()
                    exp = _date(d.year(), d.month(), d.day())
                p = self._svc.create_product(
                    name=nm,
                    code=self.code.text().strip() or None,
                    category_id=category_id,
                    visible=self.visible.isChecked(),
                    image_url=self.image_url.text().strip() or None,
                    track_expiry=self.track_expiry.isChecked(),
                    default_shelf_life_days=default_shelf,
                    default_unit_of_measure_id=default_uom_id,
                    offerings=offerings,
                    opening_stock=opening_qty,
                    opening_batch_code=self.opening_batch.text().strip() or None,
                    opening_expiry_date=exp,
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save failed" if self._edit_product_id is not None else "Register failed",
                str(e),
            )
            return

        self.created = p
        self.accept()


class ProductsDialog(QDialog):
    def __init__(self, vm: PosViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Products")
        self.resize(900, 600)
        self._vm = vm
        self._svc = vm._svc  # pragmatic; can be injected via controller
        self.catalog_changed = False

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.btn_register = QPushButton("Register product")
        self.btn_edit = QPushButton("Edit product")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or code…")
        top.addWidget(self.btn_register)
        top.addWidget(self.btn_edit)
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
        self.btn_register.clicked.connect(self._register)
        self.btn_edit.clicked.connect(self._edit)
        self.table.itemDoubleClicked.connect(self._on_product_row_activated)
        self.search.textChanged.connect(self._reload)
        self._reload()

    def _on_product_row_activated(self, item: QTableWidgetItem) -> None:
        self.table.selectRow(item.row())
        self._edit()

    def _selected_product_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 1)
        if not it:
            return None
        data = it.data(Qt.ItemDataRole.UserRole)
        return int(data) if data is not None else None

    def _register(self) -> None:
        dlg = RegisterProductDialog(self._svc, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.catalog_changed = True
        self._reload()

    def _edit(self) -> None:
        pid = self._selected_product_id()
        if pid is None:
            QMessageBox.information(self, "Edit product", "Select a product in the table first.")
            return
        dlg = RegisterProductDialog(self._svc, self, edit_product_id=pid)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.catalog_changed = True
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
            name_item = QTableWidgetItem(str(getattr(p, "name", "")))
            name_item.setData(Qt.ItemDataRole.UserRole, int(getattr(p, "id", 0)))
            self.table.setItem(row, 1, name_item)
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
            uom = getattr(ln, "unit_of_measure", None)
            if uom is not None:
                ut = getattr(uom, "abbreviation", None) or getattr(uom, "name", None)
                if ut:
                    prod_name = f"{prod_name} ({ut})"
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
    """One product with optional variant (brand × unit) selector for the cashier."""

    def __init__(
        self,
        *,
        title: str,
        variants: list[ProductListing],
        icon: QIcon | None,
        on_add: Callable[[float, ProductListing], None],
    ) -> None:
        super().__init__()
        self.setObjectName("ProductCard")
        self._variants = list(variants)
        self._on_add = on_add

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
        mid.addWidget(name)

        self._variant_combo: QComboBox | None = None
        if len(self._variants) > 1:
            combo = QComboBox()
            combo.setObjectName("ProductCardVariantCombo")
            for i, v in enumerate(self._variants):
                combo.addItem(
                    f"{v.brand_name} · {v.unit_label}  ·  Bs {v.unit_price:.2f}",
                    i,
                )
            combo.currentIndexChanged.connect(self._sync_variant_display)
            mid.addWidget(combo)
            self._variant_combo = combo

        self._meta = QLabel()
        self._meta.setObjectName("ProductCardSubtitle")
        self._meta.setWordWrap(True)
        mid.addWidget(self._meta)

        root.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(6)
        self._stock = QLabel()
        self._stock.setObjectName("ProductCardBadge")
        self._stock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stock.setWordWrap(True)
        self._stock.setMinimumWidth(120)
        qty = QDoubleSpinBox()
        qty.setDecimals(0)
        qty.setRange(1, 1_000_000)
        qty.setValue(1)
        qty.setObjectName("ProductCardQty")

        btn = QPushButton("Add")
        btn.setObjectName("ProductCardAdd")

        btn.clicked.connect(lambda: self._on_add(float(qty.value()), self.current_listing()))
        right.addWidget(self._stock)
        right.addWidget(qty)
        right.addWidget(btn)
        right.addStretch(1)
        root.addLayout(right)

        self._sync_variant_display()

    def current_listing(self) -> ProductListing:
        if self._variant_combo is not None:
            i = int(self._variant_combo.currentData())
            return self._variants[i]
        return self._variants[0]

    def _sync_variant_display(self, _idx: int | None = None) -> None:
        v = self.current_listing()
        self._meta.setText(f"Bs {v.unit_price:.2f} / {v.unit_label} · {v.brand_name}")
        stock = float(v.stock or 0.0)
        out = stock <= 0
        self._stock.setText("OUT OF STOCK" if out else f"Stock: {stock:g}")
        self.setProperty("outOfStock", out)
        sty = self.style()
        if sty is not None:
            sty.unpolish(self)
            sty.polish(self)


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

        self.variant = QComboBox()
        self.variant.setMinimumContentsLength(48)
        self.variant.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        form.addRow("Brand · Unit", self.variant)

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
        self.product.currentIndexChanged.connect(self._on_product_changed)
        self.variant.currentIndexChanged.connect(self._reload_details)

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
        self._load_variants_for_product()

    def _on_product_changed(self, _idx: int) -> None:
        self._load_variants_for_product()
        self._reload_details()

    def _load_variants_for_product(self) -> None:
        self.variant.blockSignals(True)
        self.variant.clear()
        pid = self._selected_product_id()
        if pid:
            for o in self._svc.list_product_offerings(int(pid)):
                b = getattr(o, "brand", None)
                u = getattr(o, "unit_of_measure", None)
                bname = str(getattr(b, "name", "") or "—") if b else "—"
                ulabel = (
                    str(getattr(u, "abbreviation", None) or getattr(u, "name", "") or "—") if u else "—"
                )
                st = float(getattr(o, "stock", 0.0) or 0.0)
                label = f"{bname}  ·  {ulabel}  ·  stock {st:g}"
                self.variant.addItem(label, int(o.id))
        self.variant.blockSignals(False)
        if self.variant.count() > 0:
            self.variant.setCurrentIndex(0)

    def _selected_product_id(self) -> int | None:
        if self.product.currentIndex() < 0:
            return None
        pid = self.product.currentData()
        return int(pid) if pid is not None else None

    def _selected_offering_id(self) -> int | None:
        if self.variant.currentIndex() < 0:
            return None
        oid = self.variant.currentData()
        return int(oid) if oid is not None else None

    def _reload_details(self) -> None:
        pid = self._selected_product_id()
        oid = self._selected_offering_id()
        if not pid or oid is None:
            self.lbl.setText("Select a product with at least one brand / unit offering.")
            self.lots.setRowCount(0)
            return

        p = self._svc.get_product(pid)
        track_expiry = bool(getattr(p, "track_expiry", False)) if p else False
        self.batch.setEnabled(True)
        self.has_expiry.setEnabled(True)

        offerings = {int(o.id): o for o in self._svc.list_product_offerings(pid)}
        off = offerings.get(int(oid))
        variant_stock = float(getattr(off, "stock", 0.0) or 0.0) if off else 0.0
        agg_stock = float(getattr(p, "stock", 0.0) or 0.0) if p else 0.0
        mode = "LOT-TRACKED" if track_expiry else "SIMPLE"
        lots = (
            list(self._svc.list_inventory_lots(pid, product_offering_id=int(oid))) if track_expiry else []
        )
        total_qty = (
            sum(float(getattr(l, "quantity", 0.0) or 0.0) for l in lots) if track_expiry else variant_stock
        )
        name = str(getattr(p, "name", "—")) if p else "—"
        code = str(getattr(p, "code", "") or "—") if p else "—"
        price = float(getattr(off, "price", 0.0) or 0.0) if off else float(getattr(p, "price", 0.0) or 0.0)
        visible = bool(getattr(p, "visible", True)) if p else False
        shelf = getattr(p, "default_shelf_life_days", None) if p else None
        shelf_txt = f"{int(shelf)} days" if shelf is not None else "—"
        mismatch = ""
        if track_expiry and abs(variant_stock - total_qty) > 1e-9:
            mismatch = "  ·  ⚠ Variant stock != lots sum"
        bname = str(getattr(getattr(off, "brand", None), "name", "") or "—") if off else "—"
        u = getattr(off, "unit_of_measure", None) if off else None
        ulabel = str(getattr(u, "abbreviation", None) or getattr(u, "name", "") or "—") if u else "—"
        self.lbl.setText(
            f"<b>{name}</b>  ·  {code}<br>"
            f"<b>{bname}</b>  ·  <b>{ulabel}</b>  ·  Mode: {mode}  ·  Visible: {'Yes' if visible else 'No'}<br>"
            f"Variant price: {price:.2f}  ·  Variant stock: {variant_stock:g}  ·  Product total: {agg_stock:g}<br>"
            f"Lots: {len(lots)}  ·  Qty in lots: {total_qty:g}{mismatch}<br>"
            f"Default shelf life: {shelf_txt}"
        )

        rows = lots
        if not track_expiry:
            rows = [None]  # show a single "stock" row

        self.lots.setRowCount(len(rows))
        for row, lot in enumerate(rows):
            if lot is None:
                self.lots.setItem(row, 0, QTableWidgetItem("—"))
                self.lots.setItem(row, 1, QTableWidgetItem(f"{variant_stock:g}"))
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
        oid = self._selected_offering_id()
        if not pid or oid is None:
            return
        qty = float(self.qty.value())
        expiry_date = None
        if self.has_expiry.isEnabled() and self.has_expiry.isChecked():
            d = self.expiry.date()
            expiry_date = _date(d.year(), d.month(), d.day())
        try:
            self._svc.add_inventory(
                product_id=pid,
                product_offering_id=int(oid),
                quantity=qty,
                expiry_date=expiry_date,
                batch_code=self.batch.text(),
            )
        except Exception as e:
            QMessageBox.critical(self, "Inventory add failed", str(e))
            return
        self.batch.setText("")
        self._load_variants_for_product()
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
        self.ticket.setSpacing(6)
        self.ticket.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.ticket.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._apply_ticket_list_styles()
        l.addWidget(self.ticket, 1)

        cust_row = QHBoxLayout()
        self.cust_lbl = QLabel("Client: Anonymous")
        self.btn_customer = QPushButton("Select or create client")
        cust_row.addWidget(self.cust_lbl, 1)
        cust_row.addWidget(self.btn_customer)
        l.addLayout(cust_row)

        pay_box = QGroupBox("Payment")
        pay_l = QVBoxLayout(pay_box)
        self.due_lbl = QLabel("Amount due: Bs 0.00")
        self.due_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        due_font = self.due_lbl.font()
        due_font.setBold(True)
        due_font.setPointSize(due_font.pointSize() + 2)
        self.due_lbl.setFont(due_font)
        pay_l.addWidget(self.due_lbl)

        method_row = QHBoxLayout()
        self.btn_pay_cash = QPushButton("Cash")
        self.btn_pay_cash.setCheckable(True)
        self.btn_pay_qr = QPushButton("QR / Digital")
        self.btn_pay_qr.setCheckable(True)
        self.pay_method_group = QButtonGroup(self)
        self.pay_method_group.setExclusive(True)
        self.pay_method_group.addButton(self.btn_pay_cash, 0)
        self.pay_method_group.addButton(self.btn_pay_qr, 1)
        method_row.addWidget(self.btn_pay_cash)
        method_row.addWidget(self.btn_pay_qr)
        method_row.addStretch(1)
        pay_l.addLayout(method_row)

        self.cash_panel = QWidget()
        cash_l = QVBoxLayout(self.cash_panel)
        cash_l.setContentsMargins(0, 0, 0, 0)
        tender_row = QHBoxLayout()
        tender_row.addWidget(QLabel("Cash tender"))
        self.pay_tender = QLineEdit()
        self.pay_tender.setPlaceholderText("0.00")
        tender_row.addWidget(self.pay_tender, 1)
        cash_l.addLayout(tender_row)
        exact_row = QHBoxLayout()
        self.btn_exact_tender = QPushButton("Exact total")
        exact_row.addWidget(self.btn_exact_tender)
        exact_row.addStretch(1)
        cash_l.addLayout(exact_row)
        quick_grid = QGridLayout()
        for i, amt in enumerate((5, 10, 20, 50, 100, 200)):
            b = QPushButton(f"+{amt}")
            b.clicked.connect(lambda _=False, a=float(amt): self._add_quick_tender(a))
            quick_grid.addWidget(b, i // 3, i % 3)
        cash_l.addLayout(quick_grid)

        self.qr_panel = QWidget()
        qr_l = QVBoxLayout(self.qr_panel)
        qr_l.setContentsMargins(0, 0, 0, 0)
        qr_l.addWidget(QLabel("Customer pays via QR. Confirm the transfer before completing."))

        pay_l.addWidget(self.cash_panel)
        pay_l.addWidget(self.qr_panel)

        self.pay_status = QLabel("")
        self.pay_status.setWordWrap(True)
        pay_l.addWidget(self.pay_status)

        self.btn_complete = QPushButton("Complete sale")
        self.btn_complete.setDefault(True)
        pay_l.addWidget(self.btn_complete)

        l.addWidget(pay_box)

        self._tender_block = False

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
        act_units = QAction("Units of measure", self)
        act_units.triggered.connect(self._open_units)
        act_brands = QAction("Brands", self)
        act_brands.triggered.connect(self._open_brands)
        act_clients = QAction("Clients", self)
        act_clients.triggered.connect(self._open_clients)
        act_inventory = QAction("Inventory", self)
        act_inventory.triggered.connect(self._open_inventory)
        act_sales = QAction("Sales report", self)
        act_sales.triggered.connect(self._open_sales)
        act_reorder = QAction("Reorder", self)
        act_reorder.triggered.connect(self._open_reorder)
        self.menuBar().addAction(act_products)
        self.menuBar().addAction(act_units)
        self.menuBar().addAction(act_brands)
        self.menuBar().addAction(act_clients)
        self.menuBar().addAction(act_inventory)
        self.menuBar().addAction(act_sales)
        self.menuBar().addAction(act_reorder)
        self.menuBar().addAction(act_quit)

        # Signals
        self.btn_clear.clicked.connect(self._clear)
        self.btn_customer.clicked.connect(self._pick_customer)
        self.pay_method_group.idClicked.connect(self._on_pay_method_changed)
        self.pay_tender.textChanged.connect(self._on_tender_edited)
        self.btn_exact_tender.clicked.connect(self._on_exact_tender)
        self.btn_complete.clicked.connect(self._complete_sale)
        self.search.textChanged.connect(self._reload_products)
        self.code.returnPressed.connect(self._quick_add)
        self.products.itemClicked.connect(self._add_clicked)

        self._reload_products()
        self.btn_pay_cash.setChecked(True)
        self._render_ticket()

    def _open_products(self) -> None:
        dlg = ProductsDialog(self.vm, self)
        dlg.exec()
        if dlg.catalog_changed:
            self._reload_products()

    def _open_units(self) -> None:
        UnitsOfMeasureDialog(self.vm._svc, self).exec()
        self._reload_products()

    def _open_brands(self) -> None:
        BrandsDialog(self.vm._svc, self).exec()
        self._reload_products()

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

    def _pick_listing_dialog(self, listings: list[ProductListing], *, title: str) -> ProductListing | None:
        if not listings:
            return None
        if len(listings) == 1:
            return listings[0]
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(420, 140)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Choose brand and unit:"))
        combo = QComboBox()
        for li in listings:
            combo.addItem(
                f"{li.brand_name} · {li.unit_label}  ·  Bs {li.unit_price:.2f}  (stock {float(li.stock or 0):g})"
            )
        combo.setCurrentIndex(0)
        lay.addWidget(combo)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        lay.addWidget(box)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return listings[int(combo.currentIndex())]

    def _reload_products(self) -> None:
        q = self.search.text().strip() or None
        rows = self.vm._svc.list_all_product_listings(query=q, only_visible=True)
        by_product: dict[int, list[ProductListing]] = defaultdict(list)
        for li in rows:
            by_product[int(li.product_id)].append(li)
        for lst in by_product.values():
            lst.sort(key=lambda x: (str(x.brand_name).lower(), str(x.unit_label).lower()))

        self.products.clear()
        for _pid, variants in sorted(by_product.items(), key=lambda kv: kv[1][0].name.lower()):
            v0 = variants[0]
            icon = self._product_icon(v0.image_url)
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, v0)
            it.setSizeHint(QSize(360, 140 if len(variants) > 1 else 120))
            self.products.addItem(it)

            def on_add_qty(qty: float, listing: ProductListing) -> None:
                self.vm.add_product(listing, quantity=qty)
                self._render_ticket()

            card = ProductCard(
                title=str(v0.name),
                variants=variants,
                icon=icon,
                on_add=on_add_qty,
            )
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

    @staticmethod
    def _ticket_price_breakdown(unit_price: float, qty: float) -> str:
        return f"{float(unit_price):.2f} × {int(qty)}"

    def _apply_ticket_list_styles(self) -> None:
        self.ticket.setStyleSheet(
            """
            QListWidget {
              background: #f9fafb;
              border: 1px solid #e5e7eb;
              border-radius: 8px;
              padding: 4px;
            }
            QFrame#TicketLineRow {
              background: #ffffff;
              border: 1px solid #e5e7eb;
              border-radius: 8px;
            }
            QLabel#TicketLineTitle {
              font-weight: 650;
              font-size: 13px;
              color: #111827;
            }
            QLabel#TicketLineMeta {
              font-size: 11px;
              color: #6b7280;
            }
            QLabel#TicketLineBreakdown {
              font-size: 11px;
              color: #6b7280;
            }
            QLabel#TicketLineTotal {
              font-size: 14px;
              font-weight: 700;
              color: #111827;
            }
            QLabel#TicketLineThumbEmpty {
              background: #f3f4f6;
              border-radius: 6px;
              color: #9ca3af;
              font-size: 9px;
            }
            QPushButton#TicketLineRemove {
              border: none;
              border-radius: 6px;
              font-size: 20px;
              font-weight: 400;
              color: #9ca3af;
              background: transparent;
              padding: 0px;
            }
            QPushButton#TicketLineRemove:hover {
              background: #fee2e2;
              color: #b91c1c;
            }
            """
        )

    def _render_ticket(self) -> None:
        self.ticket.clear()
        for ln in self.vm.state.lines:
            it = QListWidgetItem()
            it.setSizeHint(QSize(0, 64))
            self.ticket.addItem(it)

            row = QFrame()
            row.setObjectName("TicketLineRow")
            lay = QHBoxLayout(row)
            lay.setContentsMargins(8, 8, 6, 8)
            lay.setSpacing(10)

            thumb = QLabel()
            thumb.setFixedSize(44, 44)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic = self._product_icon(getattr(ln, "image_url", None))
            if ic:
                thumb.setPixmap(ic.pixmap(44, 44))
            else:
                thumb.setObjectName("TicketLineThumbEmpty")
                thumb.setText("·")
            lay.addWidget(thumb, 0, Qt.AlignmentFlag.AlignTop)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            title = QLabel(ln.name)
            title.setObjectName("TicketLineTitle")
            title.setWordWrap(True)
            ul = ln.unit_label or "—"
            bn = getattr(ln, "brand_name", "") or "—"
            meta = QLabel(f"{bn} · {ul}")
            meta.setObjectName("TicketLineMeta")
            text_col.addWidget(title)
            text_col.addWidget(meta)
            lay.addLayout(text_col, 1)

            qty = QDoubleSpinBox()
            qty.setDecimals(0)
            qty.setRange(1, 1_000_000)
            qty.setValue(float(ln.quantity))
            qty.setFixedWidth(72)
            qty.setToolTip("Quantity")

            breakdown = QLabel(self._ticket_price_breakdown(ln.unit_price, ln.quantity))
            breakdown.setObjectName("TicketLineBreakdown")
            breakdown.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            line_total = QLabel(f"Bs {ln.line_total:.2f}")
            line_total.setObjectName("TicketLineTotal")
            line_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            money = QVBoxLayout()
            money.setSpacing(0)
            money.addWidget(breakdown)
            money.addWidget(line_total)

            rm = QPushButton("×")
            rm.setObjectName("TicketLineRemove")
            rm.setFixedSize(32, 32)
            rm.setToolTip("Remove line")
            rm.setCursor(Qt.CursorShape.PointingHandCursor)

            lay.addWidget(qty, 0, Qt.AlignmentFlag.AlignVCenter)
            lay.addLayout(money)
            lay.addWidget(rm, 0, Qt.AlignmentFlag.AlignVCenter)

            def on_qty_change(
                _v: float,
                *,
                product_offering_id: int = ln.product_offering_id,
                unit_price: float = ln.unit_price,
            ) -> None:
                qv = float(qty.value())
                self.vm.set_line_quantity(product_offering_id=product_offering_id, quantity=qv)
                breakdown.setText(self._ticket_price_breakdown(unit_price, qv))
                line_total.setText(f"Bs {round(qv * float(unit_price), 2):.2f}")
                self._refresh_payment_ui()

            def on_remove(
                _checked: bool = False,
                product_offering_id: int = ln.product_offering_id,
            ) -> None:
                self.vm.set_line_quantity(product_offering_id=product_offering_id, quantity=0)
                self._render_ticket()

            qty.valueChanged.connect(on_qty_change)
            rm.clicked.connect(on_remove)

            self.ticket.setItemWidget(it, row)
        doc = self.vm.state.customer_doc or "—"
        self.cust_lbl.setText(f"Client: {self.vm.state.customer_name}  ·  ID: {doc}")
        self._sync_payment_widgets_from_vm()

    def _add_clicked(self, item: QListWidgetItem) -> None:
        w = self.products.itemWidget(item)
        if isinstance(w, ProductCard):
            self.vm.add_product(w.current_listing(), quantity=1)
            self._render_ticket()

    def _quick_add(self) -> None:
        code = self.code.text().strip()
        if not code:
            return
        listings = self.vm._svc.listings_for_product_code(code)
        if not listings:
            QMessageBox.information(self, "Not found", f"No product with code: {code}")
            return
        picked = self._pick_listing_dialog(listings, title=f"Code: {code}")
        if picked is None:
            return
        self.vm.add_product(picked, quantity=1)
        self.code.setText("")
        self._render_ticket()

    def _clear(self) -> None:
        self.vm.clear_ticket()
        self._render_ticket()

    def _pick_customer(self) -> None:
        dlg = CustomerDialog(self.vm, self)
        dlg.exec()
        self._render_ticket()

    @staticmethod
    def _parse_money(s: str) -> float | None:
        t = (s or "").strip().replace(",", ".")
        if not t:
            return 0.0
        try:
            return float(t)
        except ValueError:
            return None

    def _on_pay_method_changed(self, button_id: int) -> None:
        self._apply_payment_method("CASH" if int(button_id) == 0 else "QR")

    def _apply_payment_method(self, method: str) -> None:
        self.vm.state.payment_method = method.upper()
        is_cash = self.vm.state.payment_method == "CASH"
        self.cash_panel.setVisible(is_cash)
        self.qr_panel.setVisible(not is_cash)
        self._refresh_payment_ui()

    def _on_tender_edited(self, _s: str) -> None:
        if self._tender_block:
            return
        self._refresh_payment_ui()

    def _on_exact_tender(self) -> None:
        total = self.vm.state.total
        self._tender_block = True
        try:
            self.pay_tender.setText(f"{total:.2f}" if total else "")
        finally:
            self._tender_block = False
        self.vm.state.amount_received = float(total)
        self._refresh_payment_ui()

    def _add_quick_tender(self, amt: float) -> None:
        raw = self.pay_tender.text().strip()
        cur = self._parse_money(raw)
        base = float(cur) if cur is not None else self.vm.state.amount_received
        new_v = max(0.0, base + float(amt))
        self._tender_block = True
        try:
            self.pay_tender.setText(f"{new_v:.2f}")
        finally:
            self._tender_block = False
        self.vm.state.amount_received = new_v
        self._refresh_payment_ui()

    def _refresh_payment_ui(self) -> None:
        total = self.vm.state.total
        self.due_lbl.setText(f"Amount due: Bs {total:.2f}")
        if not self.vm.state.lines:
            self.btn_complete.setEnabled(False)
            self.pay_status.setText("Add products to the ticket.")
            self.pay_status.setStyleSheet("color: #6b7280;")
            return

        if self.vm.state.payment_method.upper() == "QR":
            self.btn_complete.setEnabled(True)
            self.pay_status.setText("QR / digital — verify payment, then complete.")
            self.pay_status.setStyleSheet("")
            return

        raw = self.pay_tender.text().strip()
        parsed = self._parse_money(raw)
        if raw and parsed is None:
            self.btn_complete.setEnabled(False)
            self.pay_status.setText("Enter a valid cash amount.")
            self.pay_status.setStyleSheet("color: #b45309;")
            return

        tender = float(parsed if parsed is not None else 0.0)
        self.vm.state.amount_received = tender

        if tender + 1e-9 < total:
            self.btn_complete.setEnabled(False)
            self.pay_status.setText(f"Short by Bs {total - tender:.2f}")
            self.pay_status.setStyleSheet("color: #b91c1c;")
            return

        change = round(tender - total, 2)
        self.btn_complete.setEnabled(True)
        if abs(change) < 0.005:
            self.pay_status.setText("Exact amount — no change.")
            self.pay_status.setStyleSheet("color: #15803d;")
        else:
            self.pay_status.setText(f"Change due: Bs {change:.2f}")
            self.pay_status.setStyleSheet("color: #15803d;")

    def _sync_payment_widgets_from_vm(self) -> None:
        self._tender_block = True
        try:
            ar = float(self.vm.state.amount_received or 0.0)
            if ar > 0:
                self.pay_tender.setText(f"{ar:.2f}")
            else:
                self.pay_tender.clear()
        finally:
            self._tender_block = False

        self.pay_method_group.blockSignals(True)
        try:
            if self.vm.state.payment_method.upper() == "QR":
                self.btn_pay_qr.setChecked(True)
            else:
                self.btn_pay_cash.setChecked(True)
        finally:
            self.pay_method_group.blockSignals(False)

        is_cash = self.vm.state.payment_method.upper() == "CASH"
        self.cash_panel.setVisible(is_cash)
        self.qr_panel.setVisible(not is_cash)
        self._refresh_payment_ui()

    def _complete_sale(self) -> None:
        if not self.vm.state.lines:
            QMessageBox.information(self, "Empty ticket", "Add at least one product.")
            return
        self._refresh_payment_ui()
        if not self.btn_complete.isEnabled():
            return

        total = self.vm.state.total
        pm = self.vm.state.payment_method.upper()
        if pm == "CASH":
            tender = float(self.vm.state.amount_received or 0.0)
            change = round(max(0.0, tender - total), 2)
            msg = (
                f"Complete this sale?\n\n"
                f"Total: Bs {total:.2f}\n"
                f"Cash received: Bs {tender:.2f}\n"
                f"Change: Bs {change:.2f}"
            )
        else:
            msg = f"Complete this sale?\n\nTotal: Bs {total:.2f}\nPayment: QR / digital"

        if (
            QMessageBox.question(
                self,
                "Confirm sale",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            oid = self.vm.submit()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot complete", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Submit failed", str(e))
            return

        QMessageBox.information(self, "Order saved", f"Order #{oid} saved.\nTotal: Bs {total:.2f}")
        self.vm.clear_ticket()
        self._render_ticket()
        self._reload_products()


def run_app() -> None:
    app = QApplication(sys.argv)
    w = PosWindow()
    w.show()
    raise SystemExit(app.exec())

