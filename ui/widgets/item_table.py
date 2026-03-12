"""Work items table widget with inline editing, date picker, and auto-fill."""
import unicodedata

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDateEdit, QStyledItemDelegate, QStyleOptionViewItem, QLineEdit,
    QCompleter, QStyle,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, QDate, QModelIndex, QRectF
from PySide6.QtGui import (
    QKeyEvent, QFont, QPainter, QColor, QPen, QFontMetrics, QBrush,
)
from core.models import WorkItem


class SearchHighlightDelegate(QStyledItemDelegate):
    """Delegate that highlights matching substrings with amber glow.
    
    Wraps an original delegate for editor operations while overriding paint().
    """

    def __init__(self, parent=None, wrapped=None):
        super().__init__(parent)
        self._wrapped = wrapped  # Original delegate to forward editor ops to
        self._query: str = ""
        self._highlight_bg = QColor(255, 193, 7, 90)     # amber/gold bg
        self._highlight_fg = QColor(255, 255, 255)         # white text for match
        self._highlight_border = QColor(255, 193, 7, 140)  # amber border

    def set_query(self, query: str):
        self._query = query.strip().lower()

    def createEditor(self, parent, option, index):
        if self._wrapped:
            return self._wrapped.createEditor(parent, option, index)
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        if self._wrapped:
            return self._wrapped.setEditorData(editor, index)
        return super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if self._wrapped:
            return self._wrapped.setModelData(editor, model, index)
        return super().setModelData(editor, model, index)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # Let Qt draw selection, focus, grid, and background
        self.initStyleOption(option, index)
        text = option.text or ""
        query = self._query

        # If no query or no match → use default painting
        if not query or query not in text.lower():
            super().paint(painter, option, index)
            return

        # Draw the base (selection highlight, alternating rows, etc.) WITHOUT text
        option_copy = QStyleOptionViewItem(option)
        option_copy.text = ""
        style = option.widget.style() if option.widget else None
        if style:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option_copy, painter, option.widget)

        painter.save()
        painter.setClipRect(option.rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate text area (respecting padding)
        text_rect = option.rect.adjusted(6, 0, -4, 0)
        fm = QFontMetrics(option.font)

        # Determine vertical centering
        y_text = text_rect.top() + (text_rect.height() + fm.ascent() - fm.descent()) // 2

        # Paint text segments with highlight
        x = text_rect.left()
        text_lower = text.lower()
        pos = 0

        while pos < len(text):
            match_start = text_lower.find(query, pos)
            if match_start < 0:
                # No more matches — draw the rest normally
                segment = text[pos:]
                painter.setPen(QPen(QColor(240, 240, 255)))
                painter.setFont(option.font)
                painter.drawText(x, y_text, segment)
                break

            # Draw text before the match
            if match_start > pos:
                before = text[pos:match_start]
                painter.setPen(QPen(QColor(240, 240, 255)))
                painter.setFont(option.font)
                painter.drawText(x, y_text, before)
                x += fm.horizontalAdvance(before)

            # Draw the highlighted match
            match_text = text[match_start:match_start + len(query)]
            match_width = fm.horizontalAdvance(match_text)

            # Highlight rectangle
            highlight_rect = QRectF(x - 1, text_rect.top() + 2,
                                     match_width + 2, text_rect.height() - 4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._highlight_bg))
            painter.drawRoundedRect(highlight_rect, 3, 3)
            # Border
            painter.setPen(QPen(self._highlight_border, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(highlight_rect, 3, 3)

            # Match text (bold white)
            bold_font = QFont(option.font)
            bold_font.setBold(True)
            painter.setFont(bold_font)
            painter.setPen(QPen(self._highlight_fg))
            painter.drawText(x, y_text, match_text)
            x += match_width

            pos = match_start + len(query)

        painter.restore()


COL_DATE = 0
COL_CONTENT = 1
COL_QTY = 2
COL_PRICE = 3
COL_TOTAL = 4
COL_NVKT = 5
HEADERS = ["Ngày", "Nội dung", "Số lượng", "Đơn giá", "Thành tiền", "NVKT"]


class DateDelegate(QStyledItemDelegate):
    """Delegate that shows a QDateEdit for the date column."""

    def createEditor(self, parent, option, index):
        editor = QDateEdit(parent)
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("dd/MM/yyyy")
        editor.setMinimumWidth(130)  # H06: prevent date truncation
        editor.setDate(QDate.currentDate())
        return editor

    def setEditorData(self, editor, index):
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if not text.strip():
            # Empty date cell (e.g. Ctrl+Enter continuation row) — keep empty
            editor.setSpecialValueText(" ")
            editor.setDate(editor.minimumDate())
            return
        parts = text.split("/")
        if len(parts) == 3:
            try:
                editor.setDate(QDate(int(parts[2]), int(parts[1]), int(parts[0])))
                return
            except (ValueError, IndexError):
                pass
        editor.setDate(QDate.currentDate())

    def setModelData(self, editor, model, index):
        # If user didn't change from special "empty" state, keep cell empty
        if editor.date() == editor.minimumDate():
            model.setData(index, "", Qt.ItemDataRole.EditRole)
        else:
            model.setData(index, editor.date().toString("dd/MM/yyyy"), Qt.ItemDataRole.EditRole)


class NumericDelegate(QStyledItemDelegate):
    """Delegate that only accepts numeric input and formats with comma separators."""

    def __init__(self, is_integer: bool = False, parent=None):
        super().__init__(parent)
        self.is_integer = is_integer

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignmentFlag.AlignRight)
        # Block non-numeric input at keyboard level (Fix #5)
        if self.is_integer:
            from PySide6.QtGui import QIntValidator
            editor.setValidator(QIntValidator(0, 999999999, editor))
        else:
            from PySide6.QtGui import QDoubleValidator
            validator = QDoubleValidator(0, 999999999, 2, editor)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            editor.setValidator(validator)
        return editor

    def setEditorData(self, editor, index):
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        # Remove formatting for editing
        raw = text.replace(",", "").replace(" ", "")
        editor.setText(raw)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        raw = editor.text().replace(",", "").replace(" ", "")
        if not raw:
            model.setData(index, "", Qt.ItemDataRole.EditRole)
            return
        try:
            if self.is_integer:
                val = int(float(raw))
                model.setData(index, f"{val:,}", Qt.ItemDataRole.EditRole)
            else:
                val = float(raw)
                model.setData(index, f"{val:,.0f}", Qt.ItemDataRole.EditRole)
        except ValueError:
            # Reject invalid input — clear the cell (Fix #5)
            model.setData(index, "", Qt.ItemDataRole.EditRole)


class ContentDelegate(QStyledItemDelegate):
    """Delegate with QCompleter for content auto-complete suggestions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suggestions: list[str] = []

    def set_suggestions(self, suggestions: list[str]):
        self._suggestions = suggestions

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        if self._suggestions:
            completer = QCompleter(self._suggestions, editor)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            editor.setCompleter(completer)
        return editor

    def setEditorData(self, editor, index):
        """Load existing cell text into editor without triggering completer."""
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        # Block completer from firing during programmatic text set
        completer = editor.completer() if hasattr(editor, 'completer') else None
        if completer:
            completer.blockSignals(True)
        editor.setText(str(text))
        if completer:
            completer.blockSignals(False)

    def setModelData(self, editor, model, index):
        """Write editor text back to model."""
        model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)


class ItemTable(QTableWidget):
    """Table for editing work items with auto-calculation."""

    total_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(0, 6, parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalHeaderLabels(HEADERS)
        self._content_suggestions: list[str] = []
        self._price_lookup: dict[str, float] = {}
        self._normalized_content_lookup: dict[str, tuple[str, float]] = {}
        self._ordered_content_keys: list[tuple[str, str]] = []
        self._deleted_rows_stack: list[list[dict]] = []  # Light undo stack
        self._custom_color: str = ""  # Set by apply_font_settings

        # Column sizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(COL_DATE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_CONTENT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_QTY, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_PRICE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_TOTAL, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_NVKT, QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(64)
        header.setFixedHeight(42)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        vertical_header = self.verticalHeader()
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vertical_header.setDefaultSectionSize(46)
        vertical_header.setMinimumSectionSize(42)
        vertical_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        vertical_header.setFixedWidth(42)

        self.apply_layout_mode("wide")

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)

        # Set delegates for proper input validation
        self.setItemDelegateForColumn(COL_DATE, DateDelegate(self))
        self._content_delegate = ContentDelegate(self)
        self.setItemDelegateForColumn(COL_CONTENT, self._content_delegate)
        self.setItemDelegateForColumn(COL_QTY, NumericDelegate(is_integer=True, parent=self))
        self.setItemDelegateForColumn(COL_PRICE, NumericDelegate(is_integer=False, parent=self))

        # Search highlight delegate — wraps each column delegate for paint override
        self._search_query: str = ""
        self._highlight_delegates: list[SearchHighlightDelegate] = []

        for col in range(5):
            original = self.itemDelegateForColumn(col)
            wrapper = SearchHighlightDelegate(self, wrapped=original)
            self.setItemDelegateForColumn(col, wrapper)
            self._highlight_delegates.append(wrapper)

        self.cellChanged.connect(self._on_cell_changed)

    def set_search_query(self, query: str):
        """Update search highlight query and repaint."""
        self._search_query = query
        for d in self._highlight_delegates:
            d.set_query(query)
        self.viewport().update()  # Trigger repaint for highlight

    def apply_layout_mode(self, mode: str) -> None:
        header = self.horizontalHeader()
        vertical_header = self.verticalHeader()

        if mode == "compact":
            header.setFixedHeight(38)
            vertical_header.setDefaultSectionSize(42)
            vertical_header.setMinimumSectionSize(38)
            vertical_header.setFixedWidth(38)
            self.setColumnWidth(COL_DATE, 112)
            self.setColumnWidth(COL_QTY, 74)
            self.setColumnWidth(COL_PRICE, 96)
            self.setColumnWidth(COL_TOTAL, 108)
            self.setColumnWidth(COL_NVKT, 102)
        elif mode == "medium":
            header.setFixedHeight(40)
            vertical_header.setDefaultSectionSize(44)
            vertical_header.setMinimumSectionSize(40)
            vertical_header.setFixedWidth(40)
            self.setColumnWidth(COL_DATE, 120)
            self.setColumnWidth(COL_QTY, 78)
            self.setColumnWidth(COL_PRICE, 104)
            self.setColumnWidth(COL_TOTAL, 116)
            self.setColumnWidth(COL_NVKT, 112)
        else:
            header.setFixedHeight(42)
            vertical_header.setDefaultSectionSize(46)
            vertical_header.setMinimumSectionSize(42)
            vertical_header.setFixedWidth(42)
            self.setColumnWidth(COL_DATE, 132)
            self.setColumnWidth(COL_QTY, 84)
            self.setColumnWidth(COL_PRICE, 112)
            self.setColumnWidth(COL_TOTAL, 124)
            self.setColumnWidth(COL_NVKT, 124)

    def apply_font_settings(self, settings: dict):
        """Apply font settings (family, size, color) to table display only.

        Uses setFont + per-item foreground instead of setStyleSheet
        to avoid overriding global QSS rules (M05).
        """
        family = settings.get("family", "Segoe UI")
        size = settings.get("size", 14)
        color = settings.get("color", "#f0f0ff")
        font = QFont(family, size)
        self.setFont(font)
        # Store color for applying to items
        self._custom_color = color
        # Apply color to all existing rows
        for row in range(self.rowCount()):
            self._apply_color_to_row(row)
        self._refresh_row_affordances()

    def _apply_color_to_row(self, row: int):
        """Apply custom font color to all cells in a row."""
        if not self._custom_color:
            return
        brush = QBrush(QColor(self._custom_color))
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setForeground(brush)

    def set_content_suggestions(self, suggestions: list[str], price_map: dict[str, float]):
        """Set suggestions for work content auto-complete."""
        ordered_unique: list[str] = []
        seen: set[str] = set()

        for raw_content in [*suggestions, *price_map.keys()]:
            content = raw_content.strip()
            if not content or content in seen:
                continue
            seen.add(content)
            ordered_unique.append(content)

        self._content_suggestions = ordered_unique
        self._price_lookup = {content.strip(): price for content, price in price_map.items() if content.strip()}
        self._normalized_content_lookup = {}
        self._ordered_content_keys = []

        for content in ordered_unique:
            normalized = self._normalize_content_key(content)
            if not normalized:
                continue
            price = self._price_lookup.get(content, 0.0)
            self._normalized_content_lookup.setdefault(normalized, (content, price))
            self._ordered_content_keys.append((normalized, content))

        self._content_delegate.set_suggestions(ordered_unique)

    def _insert_row(
        self,
        row: int,
        *,
        date_text: str = "",
        content_text: str = "",
        qty_text: str = "1",
        price_text: str = "",
        nvkt_text: str = "",
        focus_content: bool = True,
    ) -> int:
        row = max(0, min(row, self.rowCount()))
        was_blocked = self.signalsBlocked()
        self.blockSignals(True)
        self.insertRow(row)

        # Date cell
        date_item = QTableWidgetItem(date_text)
        date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, COL_DATE, date_item)

        # Content cell
        self.setItem(row, COL_CONTENT, QTableWidgetItem(content_text))

        # Quantity cell — default 1
        qty_item = QTableWidgetItem(qty_text)
        qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, COL_QTY, qty_item)

        # Price cell
        price_item = QTableWidgetItem(price_text)
        price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, COL_PRICE, price_item)

        # Total cell — read-only
        total_item = QTableWidgetItem("0")
        total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, COL_TOTAL, total_item)

        # NVKT cell
        nvkt_item = QTableWidgetItem(nvkt_text)
        nvkt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, COL_NVKT, nvkt_item)

        self.blockSignals(was_blocked)
        self._apply_color_to_row(row)
        self._recalc_row(row)
        self._refresh_row_affordances()
        if focus_content:
            self.setCurrentCell(row, COL_CONTENT)
        return row

    def add_empty_row(self, default_date: str = "", insert_after: int = -1) -> int:
        """Add a new empty row and return its index."""
        row = insert_after + 1 if insert_after >= 0 else self.rowCount()
        return self._insert_row(row, date_text=default_date)

    def add_continuation_row(self, insert_after: int = -1) -> int:
        """Add a continuation content row for the current date cluster."""
        if insert_after < 0:
            return self.add_empty_row(default_date="")

        target_after = self._find_continuation_insert_after(insert_after)
        return self._insert_row(target_after + 1, date_text="")

    def load_items(self, items: list[WorkItem]):
        """Load work items into the table."""
        self.blockSignals(True)
        self.setRowCount(0)

        for item in items:
            self._insert_row(
                self.rowCount(),
                date_text=item.date,
                content_text=item.content,
                qty_text=f"{item.quantity:,}",
                price_text=f"{item.unit_price:,.0f}" if item.unit_price else "",
                nvkt_text=item.nvkt,
                focus_content=False,
            )

        self.blockSignals(False)
        self._refresh_row_affordances()
        self._emit_total()

    def get_items(self) -> list[WorkItem]:
        """Extract work items from the table."""
        items = []
        for row in range(self.rowCount()):
            date = self._cell_text(row, COL_DATE)
            content = self._cell_text(row, COL_CONTENT)
            qty_raw = self._cell_text(row, COL_QTY).replace(",", "")
            price_raw = self._cell_text(row, COL_PRICE).replace(",", "")

            # Rows without content are placeholders / incomplete input.
            if not content:
                continue

            try:
                qty = int(float(qty_raw)) if qty_raw else 1
            except ValueError:
                qty = 1
            try:
                price = float(price_raw) if price_raw else 0.0
            except ValueError:
                price = 0.0

            items.append(WorkItem(date=date, content=content, quantity=qty, unit_price=price, nvkt=self._cell_text(row, COL_NVKT)))
        return items

    def remove_selected_rows(self):
        """Remove currently selected rows (saves data + position for undo)."""
        rows = sorted(set(idx.row() for idx in self.selectedIndexes()), reverse=True)
        if not rows:
            return
        # Save row data AND original position for undo
        saved = []
        for row in rows:
            saved.append({
                "position": row,
                "date": self._cell_text(row, COL_DATE),
                "content": self._cell_text(row, COL_CONTENT),
                "qty": self._cell_text(row, COL_QTY),
                "price": self._cell_text(row, COL_PRICE),
            })
        self._deleted_rows_stack.append(saved)
        # Keep max 10 undo levels
        if len(self._deleted_rows_stack) > 10:
            self._deleted_rows_stack.pop(0)
        for row in rows:
            self.removeRow(row)
        self._refresh_row_affordances()
        self._emit_total()

    def undo_delete(self):
        """Restore last deleted rows at their original positions (Ctrl+Z)."""
        if not self._deleted_rows_stack:
            return
        saved = self._deleted_rows_stack.pop()
        # Restore in ascending position order so indices stay valid
        for row_data in sorted(saved, key=lambda d: d["position"]):
            pos = row_data["position"]
            insert_at = min(pos, self.rowCount())
            self._insert_row(
                insert_at,
                date_text=row_data["date"],
                content_text=row_data["content"],
                qty_text=row_data["qty"] or "1",
                price_text=row_data["price"],
            )
        self._refresh_row_affordances()
        self._emit_total()

    def _cell_text(self, row: int, col: int) -> str:
        item = self.item(row, col)
        return item.text().strip() if item else ""

    def _resolve_group_anchor_row(self, row: int) -> int | None:
        for current in range(min(row, self.rowCount() - 1), -1, -1):
            if self._cell_text(current, COL_DATE):
                return current
        return None

    def _resolve_group_date(self, row: int) -> str:
        anchor_row = self._resolve_group_anchor_row(row)
        if anchor_row is None:
            return ""
        return self._cell_text(anchor_row, COL_DATE)

    _resolve_row_date = _resolve_group_date  # alias for key handler

    def _is_continuation_row(self, row: int) -> bool:
        return bool(row >= 0 and not self._cell_text(row, COL_DATE) and self._resolve_group_anchor_row(row) is not None)

    def _find_continuation_insert_after(self, row: int) -> int:
        anchor_row = self._resolve_group_anchor_row(row)
        if anchor_row is None:
            return row
        if row != anchor_row:
            return row

        scan_row = anchor_row + 1
        while scan_row < self.rowCount() and not self._cell_text(scan_row, COL_DATE):
            scan_row += 1
        return scan_row - 1

    def _refresh_row_affordances(self) -> None:
        active_group_date = ""
        child_fill = QBrush(QColor(86, 118, 170, 34))
        clear_fill = QBrush(QColor(0, 0, 0, 0))

        for row in range(self.rowCount()):
            date_text = self._cell_text(row, COL_DATE)
            if date_text:
                active_group_date = date_text
            is_child = bool(active_group_date and not date_text)

            header_item = self.verticalHeaderItem(row) or QTableWidgetItem()
            header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            header_item.setText("↳" if is_child else str(row + 1))
            header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            header_item.setToolTip(
                f"Dòng nội dung nối tiếp ngày {active_group_date}"
                if is_child and active_group_date
                else "Dòng ngày chính"
            )
            self.setVerticalHeaderItem(row, header_item)

            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item is None:
                    continue

                item.setBackground(child_fill if is_child else clear_fill)
                if col == COL_CONTENT:
                    font = item.font()
                    font.setItalic(is_child)
                    item.setFont(font)
                    if is_child and active_group_date:
                        item.setToolTip(f"Dòng nội dung nối tiếp ngày {active_group_date}")
                    else:
                        item.setToolTip("")
                elif col == COL_DATE:
                    font = item.font()
                    font.setBold(bool(date_text))
                    item.setFont(font)
                    if is_child and active_group_date:
                        item.setToolTip(f"Cùng ngày {active_group_date}")
                    else:
                        item.setToolTip("")

    def _parse_number(self, text: str) -> float:
        """Parse a number from formatted text (with commas)."""
        raw = text.replace(",", "").replace(" ", "").strip()
        try:
            return float(raw) if raw else 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def _normalize_content_key(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.casefold())
        normalized = normalized.replace("đ", "d").replace("Ð", "d")
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return " ".join(normalized.split())

    def _resolve_content_autofill(self, text: str) -> tuple[str, float] | None:
        normalized = self._normalize_content_key(text)
        if not normalized:
            return None

        exact = self._normalized_content_lookup.get(normalized)
        if exact is not None:
            return exact

        prefix_matches = [
            canonical
            for candidate_key, canonical in self._ordered_content_keys
            if candidate_key.startswith(normalized)
        ]
        if len(prefix_matches) == 1:
            content = prefix_matches[0]
            return content, self._price_lookup.get(content, 0.0)

        return None

    def _on_cell_changed(self, row: int, col: int):
        """Auto-calculate total when qty, price, or content changes."""
        if col == COL_CONTENT:
            # Auto-fill content + unit price from history using normalized / unique-prefix match.
            content = self._cell_text(row, COL_CONTENT)
            resolved = self._resolve_content_autofill(content)
            if resolved is not None:
                canonical_content, price = resolved
                content_item = self.item(row, COL_CONTENT)
                price_item = self.item(row, COL_PRICE)
                content_changed = content_item is not None and content != canonical_content
                price_changed = price_item is not None and not price_item.text().strip()
                if content_changed or price_changed:
                    self.blockSignals(True)
                    if content_changed and content_item is not None:
                        content_item.setText(canonical_content)
                    if price_changed and price_item is not None:
                        price_item.setText(f"{price:,.0f}")
                    self.blockSignals(False)
                    self._recalc_row(row)
                    self._emit_total()

        if col in (COL_QTY, COL_PRICE):
            self._recalc_row(row)
            self._emit_total()

        if col in (COL_DATE, COL_CONTENT, COL_QTY, COL_PRICE):
            self._refresh_row_affordances()

    def _recalc_row(self, row: int):
        """Recalculate total for a row."""
        qty = self._parse_number(self._cell_text(row, COL_QTY))
        price = self._parse_number(self._cell_text(row, COL_PRICE))
        total = qty * price

        self.blockSignals(True)
        total_item = self.item(row, COL_TOTAL)
        if total_item:
            total_item.setText(f"{total:,.0f}")
        self.blockSignals(False)

    def _emit_total(self):
        """Calculate and emit grand total."""
        grand = 0.0
        for row in range(self.rowCount()):
            grand += self._parse_number(self._cell_text(row, COL_TOTAL))
        self.total_changed.emit(grand)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts."""
        key = event.key()
        mods = event.modifiers()
        row = self.currentRow()

        # F1-F4: Quick edit specific columns
        hotkey_map: dict[int, int] = {
            Qt.Key.Key_F1: COL_DATE,
            Qt.Key.Key_F2: COL_CONTENT,
            Qt.Key.Key_F3: COL_QTY,
            Qt.Key.Key_F4: COL_PRICE,
        }

        if key in hotkey_map and row >= 0:
            col = hotkey_map[key]
            idx = self.model().index(row, col)
            self.setCurrentIndex(idx)
            self.edit(idx)
        elif key == Qt.Key.Key_Z and mods & Qt.KeyboardModifier.ControlModifier:
            self.undo_delete()
        elif key == Qt.Key.Key_Delete:
            self.remove_selected_rows()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & Qt.KeyboardModifier.ControlModifier:
                # Ctrl+Enter: append a continuation content row to the current date cluster.
                self.add_continuation_row(insert_after=row)
            elif mods & Qt.KeyboardModifier.AltModifier:
                # Alt+Enter: new row with date resolved from anchor
                date_str = self._resolve_row_date(row)
                self.add_empty_row(default_date=date_str, insert_after=row)
            else:
                # Enter: new row with date resolved from anchor
                date_str = self._resolve_row_date(row)
                self.add_empty_row(default_date=date_str, insert_after=row)
        else:
            super().keyPressEvent(event)
