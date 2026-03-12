"""Tree widget for organizing work logs into hierarchical groups."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
)

from core.date_utils import format_display_date, parse_date
from core.services import GroupService


NODE_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1
NODE_ID_ROLE = Qt.ItemDataRole.UserRole
NODE_LABEL_ROLE = Qt.ItemDataRole.UserRole + 2
NODE_META_ROLE = Qt.ItemDataRole.UserRole + 3
GROUP_TYPE = "group"
LOG_TYPE = "log"

ICON_CHOICES = [
    "📁", "📂", "🏠", "🏢", "🏗️", "🔧", "⚡", "🎯",
    "🔴", "🟢", "🔵", "🟡", "🟣", "⭐", "💼", "📋",
    "🚀", "🛠️", "📦", "🎨", "💡", "🔑", "📌", "🏷️",
]


class GroupTree(QTreeWidget):
    """Hierarchical tree for grouping work logs."""

    log_selected = Signal(int)
    group_changed = Signal()

    def __init__(self, group_service: GroupService, parent=None):
        super().__init__(parent)
        self.group_service = group_service
        self._group_row_height = 42
        self._log_row_height = 38
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setAnimated(False)
        self.setExpandsOnDoubleClick(True)
        self.setIndentation(24)
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.currentItemChanged.connect(self._on_item_changed)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(7, 13, 25, 40))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(193, 214, 250, 8))
        palette.setColor(QPalette.ColorRole.Text, QColor(231, 237, 248))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(96, 142, 230, 72))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        self.setPalette(palette)

    def apply_layout_mode(self, mode: str) -> None:
        if mode == "compact":
            self.setIndentation(18)
            self._group_row_height = 38
            self._log_row_height = 34
        elif mode == "medium":
            self.setIndentation(22)
            self._group_row_height = 40
            self._log_row_height = 36
        else:
            self.setIndentation(24)
            self._group_row_height = 42
            self._log_row_height = 38

        self._refresh_item_density(self.invisibleRootItem())

    def reload(self, logs: list[dict]):
        """Rebuild entire tree from groups + logs data."""
        self.blockSignals(True)

        selected_item = self.currentItem()
        selected_ref: tuple[str, int | None] | None = None
        if selected_item is not None:
            selected_ref = (
                selected_item.data(0, NODE_TYPE_ROLE),
                selected_item.data(0, NODE_ID_ROLE),
            )

        expanded_groups = set()
        ungrouped_expanded = False
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if (
                item.data(0, NODE_TYPE_ROLE) == GROUP_TYPE
                and item.data(0, NODE_ID_ROLE) is None
                and item.isExpanded()
            ):
                ungrouped_expanded = True
            self._collect_expanded(item, expanded_groups)

        self.clear()
        groups = self.group_service.get_all_groups()
        group_map: dict[int, QTreeWidgetItem] = {}
        log_map: dict[int, QTreeWidgetItem] = {}
        ungrouped_item: QTreeWidgetItem | None = None

        def build_group_items(parent_id: int | None, parent_widget: QTreeWidgetItem | None):
            for group in groups:
                if group["parent_id"] != parent_id:
                    continue
                item = self._make_group_item(group)
                if parent_widget is None:
                    self.addTopLevelItem(item)
                else:
                    parent_widget.addChild(item)
                group_map[group["id"]] = item
                build_group_items(group["id"], item)

        build_group_items(None, None)

        ungrouped_logs: list[dict] = []
        grouped_logs: dict[int, list[dict]] = {}
        for log in logs:
            group_id = log.get("group_id")
            if group_id is not None and group_id in group_map:
                grouped_logs.setdefault(group_id, []).append(log)
            else:
                ungrouped_logs.append(log)

        for group_id, log_list in grouped_logs.items():
            parent_item = group_map[group_id]
            for log in log_list:
                log_item = self._make_log_item(log)
                parent_item.addChild(log_item)
                log_map[log["id"]] = log_item

        if ungrouped_logs:
            ungrouped = QTreeWidgetItem()
            ungrouped.setText(0, f"Chưa phân loại ({len(ungrouped_logs)})")
            ungrouped.setData(0, NODE_TYPE_ROLE, GROUP_TYPE)
            ungrouped.setData(0, NODE_ID_ROLE, None)
            ungrouped.setData(0, NODE_LABEL_ROLE, "Chưa phân loại")
            self._style_group_bucket(ungrouped, QColor(148, 166, 194, 64), italic=True)
            ungrouped.setFlags(ungrouped.flags() | Qt.ItemFlag.ItemIsDropEnabled)
            ungrouped.setFlags(ungrouped.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            self.addTopLevelItem(ungrouped)
            for log in ungrouped_logs:
                log_item = self._make_log_item(log)
                ungrouped.addChild(log_item)
                log_map[log["id"]] = log_item
            ungrouped.setExpanded(ungrouped_expanded)
            ungrouped_item = ungrouped

        for item in group_map.values():
            self._update_group_count(item)

        for group_id in expanded_groups:
            if group_id in group_map:
                group_map[group_id].setExpanded(True)

        if selected_ref is not None:
            selected_type, selected_id = selected_ref
            target_item = None
            if selected_type == GROUP_TYPE and selected_id is not None:
                target_item = group_map.get(selected_id)
            elif selected_type == GROUP_TYPE and selected_id is None:
                target_item = ungrouped_item
            elif selected_type == LOG_TYPE and selected_id is not None:
                target_item = log_map.get(selected_id)
            if target_item is not None:
                self._expand_ancestors(target_item)
                self.setCurrentItem(target_item)
                self.scrollToItem(target_item)

        self.blockSignals(False)

    def select_log(self, log_id: int):
        item = self._find_log_item(self.invisibleRootItem(), log_id)
        if item:
            self.blockSignals(True)
            self._expand_ancestors(item)
            self.setCurrentItem(item)
            self.scrollToItem(item)
            self.blockSignals(False)

    def describe_item(self, item: QTreeWidgetItem | None) -> str:
        if item is None:
            return "Chưa chọn phiếu hoặc nhóm."

        labels: list[str] = []
        current = item
        while current is not None:
            label = current.data(0, NODE_LABEL_ROLE) or current.text(0)
            if label:
                labels.append(str(label))
            current = current.parent()
        path_text = " / ".join(reversed(labels))

        meta = item.data(0, NODE_META_ROLE)
        if meta:
            return f"{path_text}\n{meta}"
        return path_text

    def current_selection_summary(self) -> str:
        return self.describe_item(self.currentItem())

    def handle_drop(self, source_item: QTreeWidgetItem, target_item: QTreeWidgetItem | None) -> bool:
        source_type = source_item.data(0, NODE_TYPE_ROLE)
        if source_type == LOG_TYPE:
            log_id = source_item.data(0, NODE_ID_ROLE)
            group_id = self._resolve_target_group_id(target_item)
            return self.group_service.move_log(log_id, group_id)

        if source_type == GROUP_TYPE:
            source_group_id = source_item.data(0, NODE_ID_ROLE)
            if source_group_id is None:
                return False
            target_group_id = self._resolve_target_group_id(target_item)
            return self.group_service.move_group(source_group_id, target_group_id)

        return False

    def _resolve_target_group_id(self, target_item: QTreeWidgetItem | None) -> int | None:
        if target_item is None:
            return None

        target_type = target_item.data(0, NODE_TYPE_ROLE)
        if target_type == GROUP_TYPE:
            return target_item.data(0, NODE_ID_ROLE)

        parent = target_item.parent()
        while parent is not None:
            if parent.data(0, NODE_TYPE_ROLE) == GROUP_TYPE:
                return parent.data(0, NODE_ID_ROLE)
            parent = parent.parent()
        return None

    def _make_group_item(self, group_data: dict) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        icon = group_data.get("icon", "📁")
        name = group_data.get("name", "")
        label = f"{icon} {name}"
        item.setText(0, label)
        item.setToolTip(0, label)
        item.setData(0, NODE_TYPE_ROLE, GROUP_TYPE)
        item.setData(0, NODE_ID_ROLE, group_data["id"])
        item.setData(0, NODE_LABEL_ROLE, label)
        self._style_group_bucket(item, QColor(group_data.get("color", "#6c63ff")))
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsDropEnabled
            | Qt.ItemFlag.ItemIsDragEnabled
        )
        return item

    def _make_log_item(self, log: dict) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        work_date = format_display_date(parse_date(log.get("work_date")))
        status_text = "Đã gửi" if log.get("is_sent") else "Chưa gửi"
        total = log.get("total", 0)
        count = log.get("item_count", 0)
        customer_name = log.get("customer_name") or "Khách chưa đặt tên"
        label = f"{customer_name} · {work_date}"
        meta = f"{count} mục · {total:,.0f}đ · {status_text}"
        item.setText(0, label)
        item.setToolTip(0, f"{customer_name}\n{work_date} · {meta}")
        item.setData(0, NODE_TYPE_ROLE, LOG_TYPE)
        item.setData(0, NODE_ID_ROLE, log["id"])
        item.setData(0, NODE_LABEL_ROLE, customer_name)
        item.setData(0, NODE_META_ROLE, f"{work_date} · {meta}")
        item.setForeground(0, QBrush(QColor(229, 237, 248)))
        item.setSizeHint(0, QSize(0, self._log_row_height))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
        return item

    def _style_group_bucket(self, item: QTreeWidgetItem, color: QColor, *, italic: bool = False):
        tint = QColor(color)
        tint.setAlpha(58)
        item.setBackground(0, QBrush(tint))
        item.setForeground(0, QBrush(QColor(244, 248, 255)))
        font = item.font(0)
        font.setBold(True)
        font.setItalic(italic)
        item.setFont(0, font)
        item.setSizeHint(0, QSize(0, self._group_row_height))

    def _refresh_item_density(self, parent: QTreeWidgetItem):
        for index in range(parent.childCount()):
            child = parent.child(index)
            node_type = child.data(0, NODE_TYPE_ROLE)
            if node_type == GROUP_TYPE:
                child.setSizeHint(0, QSize(0, self._group_row_height))
            elif node_type == LOG_TYPE:
                child.setSizeHint(0, QSize(0, self._log_row_height))
            self._refresh_item_density(child)

    @staticmethod
    def _expand_ancestors(item: QTreeWidgetItem):
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()

    def _update_group_count(self, item: QTreeWidgetItem):
        if item.data(0, NODE_TYPE_ROLE) != GROUP_TYPE:
            return
        group_id = item.data(0, NODE_ID_ROLE)
        if group_id is None:
            return
        count = self._count_logs_recursive(item)
        base_text = item.data(0, NODE_LABEL_ROLE) or item.text(0)
        item.setText(0, f"{base_text} ({count})")

    def _count_logs_recursive(self, item: QTreeWidgetItem) -> int:
        count = 0
        for i in range(item.childCount()):
            child = item.child(i)
            if child.data(0, NODE_TYPE_ROLE) == LOG_TYPE:
                count += 1
            elif child.data(0, NODE_TYPE_ROLE) == GROUP_TYPE:
                count += self._count_logs_recursive(child)
        return count

    def _collect_expanded(self, item: QTreeWidgetItem | None, expanded_set: set[int]):
        if item is None:
            return
        if item.isExpanded() and item.data(0, NODE_TYPE_ROLE) == GROUP_TYPE:
            group_id = item.data(0, NODE_ID_ROLE)
            if group_id is not None:
                expanded_set.add(group_id)
        for i in range(item.childCount()):
            self._collect_expanded(item.child(i), expanded_set)

    def _find_log_item(self, parent: QTreeWidgetItem, log_id: int) -> QTreeWidgetItem | None:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.data(0, NODE_TYPE_ROLE) == LOG_TYPE and child.data(0, NODE_ID_ROLE) == log_id:
                return child
            found = self._find_log_item(child, log_id)
            if found:
                return found
        return None

    def _on_item_changed(self, current, previous):
        if not current:
            return
        if current.data(0, NODE_TYPE_ROLE) == LOG_TYPE:
            log_id = current.data(0, NODE_ID_ROLE)
            if log_id is not None:
                self.log_selected.emit(log_id)

    def dropEvent(self, event):
        source_item = self.currentItem()
        target_item = self.itemAt(event.position().toPoint())
        if source_item and self.handle_drop(source_item, target_item):
            self.group_changed.emit()
            event.acceptProposedAction()
            return
        event.ignore()

    def dragEnterEvent(self, event):
        if event.source() == self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() == self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)

        if item and item.data(0, NODE_TYPE_ROLE) == GROUP_TYPE:
            group_id = item.data(0, NODE_ID_ROLE)
            if group_id is not None:
                menu.addAction("Tạo nhóm con", lambda: self._create_subgroup(group_id))
                menu.addAction("Đổi tên", lambda: self._rename_group(group_id))
                menu.addAction("Đổi màu", lambda: self._change_color(group_id))
                menu.addAction("Đổi icon", lambda: self._change_icon(group_id))
                menu.addSeparator()
                menu.addAction("Xóa nhóm", lambda: self._delete_group(group_id))
            menu.addSeparator()

        if item and item.data(0, NODE_TYPE_ROLE) == LOG_TYPE:
            log_id = item.data(0, NODE_ID_ROLE)
            move_menu = menu.addMenu("Chuyển sang nhóm")
            groups = self.group_service.get_all_groups()
            move_menu.addAction("Chưa phân loại", lambda: self._move_log(log_id, None))
            for group in groups:
                label = f"{group['icon']} {group['name']}"
                move_menu.addAction(label, lambda _group_id=group["id"]: self._move_log(log_id, _group_id))
            menu.addSeparator()

        menu.addAction("Tạo nhóm mới", self._create_group_root)
        menu.exec(self.viewport().mapToGlobal(pos))

    def _create_group_root(self):
        name, ok = QInputDialog.getText(self, "Tạo nhóm", "Tên nhóm:")
        if ok and name.strip():
            self.group_service.create_group(name.strip())
            self.group_changed.emit()

    def create_group_root(self):
        self._create_group_root()

    def _create_subgroup(self, parent_id: int):
        name, ok = QInputDialog.getText(self, "Tạo nhóm con", "Tên nhóm con:")
        if ok and name.strip():
            self.group_service.create_group(name.strip(), parent_id=parent_id)
            self.group_changed.emit()

    def _rename_group(self, group_id: int):
        name, ok = QInputDialog.getText(self, "Đổi tên nhóm", "Tên mới:")
        if ok and name.strip():
            self.group_service.rename_group(group_id, name.strip())
            self.group_changed.emit()

    def _change_color(self, group_id: int):
        dialog = QColorDialog(QColor("#6c63ff"), self)
        dialog.setWindowTitle("Chọn màu nhóm")
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        if dialog.exec():
            self.group_service.set_group_color(group_id, dialog.currentColor().name())
            self.group_changed.emit()

    def _change_icon(self, group_id: int):
        icon, ok = QInputDialog.getItem(self, "Chọn icon", "Icon:", ICON_CHOICES, 0, False)
        if ok and icon:
            self.group_service.set_group_icon(group_id, icon)
            self.group_changed.emit()

    def _delete_group(self, group_id: int):
        reply = QMessageBox.question(
            self,
            "Xóa nhóm",
            "Xóa nhóm này? Các phiếu bên trong sẽ về 'Chưa phân loại'.\n(Nhóm con cũng bị xóa)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.group_service.delete_group(group_id)
            self.group_changed.emit()

    def _move_log(self, log_id: int, group_id: int | None):
        if self.group_service.move_log(log_id, group_id):
            self.group_changed.emit()
