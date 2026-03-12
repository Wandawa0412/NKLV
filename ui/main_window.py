"""Main window — the primary interface for Work Log Manager."""
from __future__ import annotations

import os
from datetime import date

from PySide6.QtCore import QDate, QSignalBlocker, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QFontMetrics, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGraphicsDropShadowEffect,
    QBoxLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedLayout,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from core.app_metadata import APP_DISPLAY_NAME
from core.date_utils import format_display_date
from core.excel_engine import ExcelEngine
from core.models import WorkLog
from core.services import (
    GroupService,
    ImportExportService,
    PreferencesService,
    WorkLogService,
)
from ui.widgets.autocomplete_combo import AutoCompleteCombo
from ui.widgets.cyber_footer import CyberFooter
from ui.widgets.font_settings import FontSettingsDialog
from ui.widgets.group_tree import GroupTree
from ui.widgets.item_table import ItemTable
from ui.widgets.toast import Toast


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setMinimumSize(1060, 720)
        self.resize(1380, 860)

        self._set_window_icon()

        self.db = Database()
        self.worklog_service = WorkLogService(self.db)
        self.group_service = GroupService(self.db)
        self.preferences_service = PreferencesService(self.db)
        self.import_export_service = ImportExportService(self.db, ExcelEngine())

        self.current_log_id: int | None = None
        self._working_dir = self.preferences_service.get_working_directory()
        self._current_source_path = ""
        self._responsive_mode = ""
        self._source_label_raw_text = "Chưa có"
        self._sidebar_actions_mode = ""
        self._customer_autofill_timer = QTimer(self)
        self._customer_autofill_timer.setSingleShot(True)
        self._customer_autofill_timer.setInterval(200)
        self._customer_autofill_timer.timeout.connect(self._refresh_autofill)

        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_shortcuts()

        self.toast = Toast(self)
        self._load_font_settings()
        self._refresh_sidebar()
        self._new_log()
        self._update_workdir_display()

    def _set_window_icon(self):
        icon_candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "icon", "business.png"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "icon", "business.png"),
        ]
        for raw_path in icon_candidates:
            icon_path = os.path.abspath(raw_path)
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                return

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        stack = QStackedLayout(central)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setStackingMode(QStackedLayout.StackingMode.StackAll)

        from ui.widgets.wave_background import WaveBackground

        self._wave_bg = WaveBackground(duck_count=4)
        stack.addWidget(self._wave_bg)

        content = QWidget()
        content.setObjectName("contentLayer")
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        stack.addWidget(content)
        stack.setCurrentWidget(content)

        self._root_layout = QVBoxLayout(content)
        self._root_layout.setContentsMargins(10, 10, 10, 8)
        self._root_layout.setSpacing(8)

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setObjectName("mainSplitter")
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.setHandleWidth(8)
        self._main_splitter.splitterMoved.connect(lambda *_args: self._update_responsive_layout())
        self._root_layout.addWidget(self._main_splitter)

        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setMinimumWidth(260)
        self._sidebar.setMaximumWidth(330)
        self._sidebar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(16, 14, 14, 14)
        sidebar_layout.setSpacing(8)

        sidebar_title = QLabel("Phiếu công việc")
        sidebar_title.setObjectName("sidebarTitle")
        sidebar_layout.addWidget(sidebar_title)

        sidebar_subtitle = QLabel("Tìm kiếm, lọc theo tháng và tổ chức theo nhóm.")
        sidebar_subtitle.setObjectName("sidebarSubtitle")
        sidebar_subtitle.setWordWrap(True)
        sidebar_layout.addWidget(sidebar_subtitle)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tìm khách hàng hoặc nội dung")
        self.search_input.setObjectName("searchInput")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search)
        sidebar_layout.addWidget(self.search_input)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.filter_status = QComboBox()
        self.filter_status.addItems(["Tất cả", "Đã gửi", "Chưa gửi"])
        self.filter_status.setObjectName("filterStatus")
        self.filter_status.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.filter_status)

        self.filter_month = QComboBox()
        self.filter_month.setObjectName("filterMonth")
        self.filter_month.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.filter_month)
        self._populate_month_filter()

        sidebar_layout.addLayout(filter_row)

        self.sidebar_meta = QLabel("0 phiếu")
        self.sidebar_meta.setObjectName("sidebarMeta")
        sidebar_layout.addWidget(self.sidebar_meta)

        self.sidebar_context = QLabel("Phiếu mới chưa lưu. Nhập khách hàng hoặc dùng Nhập Excel để bắt đầu.")
        self.sidebar_context.setObjectName("sidebarContext")
        self.sidebar_context.setWordWrap(True)
        sidebar_layout.addWidget(self.sidebar_context)

        self.group_tree = GroupTree(self.group_service)
        self.group_tree.setObjectName("groupTree")
        self.group_tree.log_selected.connect(self._on_log_selected)
        self.group_tree.group_changed.connect(self._refresh_sidebar)
        self.group_tree.currentItemChanged.connect(self._update_sidebar_context)
        sidebar_layout.addWidget(self.group_tree, 1)

        self.btn_new = QPushButton("Phiếu mới")
        self.btn_new.setObjectName("btnPrimary")
        self.btn_new.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_new.clicked.connect(self._new_log)

        self.btn_new_group = QPushButton("Nhóm mới")
        self.btn_new_group.setObjectName("btnSecondary")
        self.btn_new_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_new_group.clicked.connect(self._create_new_group)

        self.btn_delete = QPushButton("Xóa")
        self.btn_delete.setObjectName("btnDanger")
        self.btn_delete.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_delete.clicked.connect(self._delete_log)

        self._sidebar_actions_wrap = QWidget()
        self._sidebar_actions_wrap.setObjectName("sidebarActions")
        self._sidebar_actions_layout = QGridLayout(self._sidebar_actions_wrap)
        self._sidebar_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._sidebar_actions_layout.setHorizontalSpacing(0)
        self._sidebar_actions_layout.setVerticalSpacing(8)
        sidebar_layout.addWidget(self._sidebar_actions_wrap)
        self._apply_panel_effect(self._sidebar, blur_radius=18, y_offset=8)

        self._main_splitter.addWidget(self._sidebar)

        self._form_container = QWidget()
        self._form_container.setObjectName("formContainer")
        self._form_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._form_layout = QVBoxLayout(self._form_container)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(6)

        self._info_title = QLabel("Thông tin phiếu")
        self._info_title.setObjectName("sectionHeader")
        self._form_layout.addWidget(self._info_title)

        self.info_group = QFrame()
        self.info_group.setObjectName("metadataStrip")
        self.info_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._info_layout = QGridLayout(self.info_group)
        self._info_layout.setContentsMargins(16, 12, 16, 12)
        self._info_layout.setHorizontalSpacing(12)
        self._info_layout.setVerticalSpacing(8)
        self.customer_combo = AutoCompleteCombo(placeholder="Nhập tên khách hàng")
        self.customer_combo.item_selected.connect(self._on_customer_selected)
        self.customer_combo.currentTextChanged.connect(self._schedule_customer_autofill_refresh)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setMinimumWidth(108)
        self.date_edit.setDate(QDate.currentDate())
        self.sent_checkbox = QCheckBox("Đã gửi hóa đơn")
        self.btn_open_dir = QPushButton("Mở thư mục nguồn")
        self.btn_open_dir.setObjectName("btnSecondary")
        self.btn_open_dir.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.btn_open_dir.clicked.connect(self._open_working_dir)
        self.source_label = QLabel("Chưa có")
        self.source_label.setObjectName("sourceLabel")
        self.source_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.source_label.setWordWrap(False)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._source_actions = QWidget()
        self._source_actions.setObjectName("sourceActions")
        self._source_actions.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._source_actions_layout = QHBoxLayout(self._source_actions)
        self._source_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._source_actions_layout.setSpacing(10)
        self._source_actions_layout.addWidget(self.source_label, 1)
        self._source_actions_layout.addWidget(self.btn_open_dir, 0, Qt.AlignmentFlag.AlignVCenter)

        self.customer_panel = self._build_field_panel("Khách hàng", self.customer_combo, "customerPanel")
        self.date_panel = self._build_field_panel("Ngày phiếu", self.date_edit, "datePanel")
        self.status_panel = self._build_field_panel("Trạng thái", self.sent_checkbox, "statusPanel")
        self.source_panel = self._build_field_panel("Nguồn dữ liệu", self._source_actions, "sourcePanel")

        self._form_layout.addWidget(self.info_group)
        self._apply_panel_effect(self.info_group, blur_radius=14, y_offset=6)

        self._table_title = QLabel("Danh sách công việc")
        self._table_title.setObjectName("sectionHeader")
        self._table_title.setProperty("tablePrimary", True)
        self._form_layout.addWidget(self._table_title)

        self.table_group = QFrame()
        self.table_group.setObjectName("tableSurface")
        self.table_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table_layout = QVBoxLayout(self.table_group)
        self._table_layout.setContentsMargins(14, 12, 14, 14)
        self._table_layout.setSpacing(10)

        self._table_toolbar = QWidget()
        self._table_toolbar.setObjectName("tableToolbar")
        self._table_toolbar_layout = QGridLayout(self._table_toolbar)
        self._table_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self._table_toolbar_layout.setHorizontalSpacing(12)
        self._table_toolbar_layout.setVerticalSpacing(6)

        self._table_buttons_wrap = QWidget()
        self._table_buttons_layout = QHBoxLayout(self._table_buttons_wrap)
        self._table_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self._table_buttons_layout.setSpacing(8)

        self.btn_add_row = QPushButton("Thêm dòng")
        self.btn_add_row.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.btn_add_row.clicked.connect(self._add_row)
        self._table_buttons_layout.addWidget(self.btn_add_row)

        self.btn_remove_row = QPushButton("Xóa dòng")
        self.btn_remove_row.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.btn_remove_row.clicked.connect(self._remove_row)
        self._table_buttons_layout.addWidget(self.btn_remove_row)

        self.btn_duplicate = QPushButton("Nhân đôi phiếu")
        self.btn_duplicate.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.btn_duplicate.clicked.connect(self._duplicate_log)
        self._table_buttons_layout.addWidget(self.btn_duplicate)

        self._table_search_wrap = QWidget()
        self._table_search_layout = QHBoxLayout(self._table_search_wrap)
        self._table_search_layout.setContentsMargins(0, 0, 0, 0)
        self._table_search_layout.setSpacing(8)

        self.table_search_input = QLineEdit()
        self.table_search_input.setObjectName("tableSearchInput")
        self.table_search_input.setPlaceholderText("Tìm trong bảng")
        self.table_search_input.setClearButtonEnabled(True)
        self.table_search_input.setMinimumWidth(0)
        self.table_search_input.setMaximumWidth(240)
        self.table_search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.table_search_input.textChanged.connect(self._on_table_search)
        self._table_search_layout.addWidget(self.table_search_input, 1)

        self.table_search_count = QLabel("")
        self.table_search_count.setObjectName("searchCount")
        self._table_search_layout.addWidget(self.table_search_count, 0, Qt.AlignmentFlag.AlignRight)
        self._table_layout.addWidget(self._table_toolbar)

        self._table_frame = QFrame()
        self._table_frame.setObjectName("tableFrame")
        self._table_frame_layout = QVBoxLayout(self._table_frame)
        self._table_frame_layout.setContentsMargins(1, 1, 1, 1)
        self._table_frame_layout.setSpacing(0)

        self.item_table = ItemTable()
        self.item_table.setObjectName("itemTable")
        self.item_table.total_changed.connect(self._on_total_changed)
        self.item_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table_frame_layout.addWidget(self.item_table)
        self._table_layout.addWidget(self._table_frame, 1)
        self._form_layout.addWidget(self.table_group, 1)
        self._apply_panel_effect(self.table_group, blur_radius=18, y_offset=8)

        self._action_bar = QFrame()
        self._action_bar.setObjectName("actionBar")
        self._action_layout = QGridLayout(self._action_bar)
        self._action_layout.setContentsMargins(12, 6, 12, 6)
        self._action_layout.setHorizontalSpacing(10)
        self._action_layout.setVerticalSpacing(6)

        self.total_label = QLabel("Tổng cộng: 0 đ")
        self.total_label.setObjectName("totalLabel")
        self._action_layout.addWidget(self.total_label, 0, 0, 1, 1, Qt.AlignmentFlag.AlignVCenter)

        self._action_buttons_wrap = QWidget()
        self._action_buttons_layout = QHBoxLayout(self._action_buttons_wrap)
        self._action_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self._action_buttons_layout.setSpacing(8)
        self._action_buttons_layout.addStretch()

        self.btn_save = QPushButton("Lưu phiếu")
        self.btn_save.setObjectName("btnPrimary")
        self.btn_save.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.btn_save.clicked.connect(self._save_log)
        self._action_buttons_layout.addWidget(self.btn_save)

        self.btn_export = QPushButton("Xuất Excel")
        self.btn_export.setObjectName("btnSecondary")
        self.btn_export.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.btn_export.clicked.connect(self._export_single)
        self._action_buttons_layout.addWidget(self.btn_export)
        self._action_layout.addWidget(self._action_buttons_wrap, 0, 1, 1, 1)

        self._form_layout.addWidget(self._action_bar)
        self._apply_panel_effect(self._action_bar, blur_radius=14, y_offset=5)

        self._main_splitter.addWidget(self._form_container)
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([286, 1094])

        self._footer_bar = QFrame()
        self._footer_bar.setObjectName("footerBar")
        self._footer_bar.setMinimumHeight(44)
        self._footer_bar.setMaximumHeight(52)
        self._footer_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._footer_stack = QStackedLayout(self._footer_bar)
        self._footer_stack.setContentsMargins(0, 0, 0, 0)
        self._footer_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self._footer_wave = WaveBackground(
            duck_count=10,
            duck_size_range=(10, 18),
            duck_opacity_range=(0.24, 0.52),
            backdrop_alpha_scale=0.80,
        )
        self._footer_wave.setObjectName("footerWave")
        self._footer_stack.addWidget(self._footer_wave)

        self._footer_content = QWidget()
        self._footer_content.setObjectName("footerContentLayer")
        self._footer_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._footer_stack.addWidget(self._footer_content)
        self._footer_stack.setCurrentWidget(self._footer_content)

        self._footer_layout = QHBoxLayout(self._footer_content)
        self._footer_layout.setContentsMargins(12, 3, 12, 3)
        self._footer_layout.setSpacing(6)
        self._footer_layout.addStretch()
        self.cyber_footer = CyberFooter("Copyright Sang@ecos minuszero369@gmail.com")
        self.cyber_footer.setMinimumWidth(0)
        self.cyber_footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._footer_layout.addWidget(self.cyber_footer, 0, Qt.AlignmentFlag.AlignCenter)
        self._footer_layout.addStretch()
        self._root_layout.addWidget(self._footer_bar)
        self._apply_panel_effect(self._footer_bar, blur_radius=10, y_offset=4)

        self.setAcceptDrops(True)
        self._update_source_label("")
        self._update_opendir_tooltip()
        self._update_export_tooltip()
        QTimer.singleShot(0, self._update_responsive_layout)

    def _apply_panel_effect(self, widget: QWidget, blur_radius: int = 24, y_offset: int = 12):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur_radius)
        shadow.setOffset(0, y_offset)
        shadow.setColor(QColor(5, 10, 24, 140))
        widget.setGraphicsEffect(shadow)

    def _build_field_panel(self, title: str, body: QWidget, object_name: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setProperty("panelRole", "metaField")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(title)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(body)
        return panel

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_layout()
        self._refresh_source_label_text()

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()

    def _update_responsive_layout(self) -> None:
        splitter_sizes = self._main_splitter.sizes()
        sidebar_width = max(
            self._sidebar.width(),
            splitter_sizes[0] if splitter_sizes else 0,
            self._sidebar.minimumWidth(),
        )
        form_width = max(
            self._form_container.width(),
            splitter_sizes[1] if len(splitter_sizes) > 1 else 0,
            self.width() - sidebar_width - 56,
        )

        if form_width >= 980:
            mode = "wide"
        elif form_width >= 760:
            mode = "medium"
        else:
            mode = "compact"

        self._responsive_mode = mode
        self._apply_info_layout(mode)
        self._apply_source_panel_layout(mode)
        self._apply_table_toolbar_layout(mode)
        self._apply_action_bar_layout(mode)
        self._apply_footer_layout(mode)
        self._apply_sidebar_actions_layout(mode, sidebar_width)
        self.group_tree.apply_layout_mode(mode)
        self.item_table.apply_layout_mode(mode)
        self._refresh_source_label_text()

    def _apply_info_layout(self, mode: str) -> None:
        self._clear_layout(self._info_layout)
        panels = (
            self.customer_panel,
            self.date_panel,
            self.status_panel,
            self.source_panel,
        )
        for panel in panels:
            panel.show()

        for column in range(4):
            self._info_layout.setColumnStretch(column, 0)

        if mode == "wide":
            self.info_group.setMaximumHeight(98)
            self._info_layout.addWidget(self.customer_panel, 0, 0)
            self._info_layout.addWidget(self.date_panel, 0, 1)
            self._info_layout.addWidget(self.status_panel, 0, 2)
            self._info_layout.addWidget(self.source_panel, 0, 3)
            self._info_layout.setColumnStretch(0, 5)
            self._info_layout.setColumnStretch(1, 2)
            self._info_layout.setColumnStretch(2, 2)
            self._info_layout.setColumnStretch(3, 4)
        elif mode == "medium":
            self.info_group.setMaximumHeight(118)
            self._info_layout.addWidget(self.customer_panel, 0, 0, 1, 2)
            self._info_layout.addWidget(self.date_panel, 0, 2)
            self._info_layout.addWidget(self.status_panel, 0, 3)
            self._info_layout.addWidget(self.source_panel, 1, 0, 1, 4)
            self._info_layout.setColumnStretch(0, 4)
            self._info_layout.setColumnStretch(1, 2)
            self._info_layout.setColumnStretch(2, 2)
            self._info_layout.setColumnStretch(3, 3)
        else:
            self.info_group.setMaximumHeight(126)
            self._info_layout.addWidget(self.customer_panel, 0, 0, 1, 2)
            self._info_layout.addWidget(self.date_panel, 1, 0)
            self._info_layout.addWidget(self.status_panel, 1, 1)
            self._info_layout.addWidget(self.source_panel, 2, 0, 1, 2)
            self._info_layout.setColumnStretch(0, 3)
            self._info_layout.setColumnStretch(1, 2)

    def _apply_table_toolbar_layout(self, mode: str) -> None:
        self._clear_layout(self._table_toolbar_layout)
        self._table_buttons_wrap.show()
        self._table_search_wrap.show()
        self.table_search_input.setMaximumWidth(240 if mode == "wide" else 220 if mode == "medium" else 16777215)

        if mode in {"wide", "medium"}:
            self._table_toolbar_layout.addWidget(self._table_buttons_wrap, 0, 0, 1, 1, Qt.AlignmentFlag.AlignLeft)
            self._table_toolbar_layout.addWidget(self._table_search_wrap, 0, 1, 1, 1, Qt.AlignmentFlag.AlignRight)
            self._table_toolbar_layout.setColumnStretch(0, 0)
            self._table_toolbar_layout.setColumnStretch(1, 1)
        else:
            self._table_toolbar_layout.addWidget(self._table_buttons_wrap, 0, 0)
            self._table_toolbar_layout.addWidget(self._table_search_wrap, 1, 0)
            self._table_toolbar_layout.setColumnStretch(0, 1)
            self._table_toolbar_layout.setColumnStretch(1, 0)

    def _apply_source_panel_layout(self, mode: str) -> None:
        self._source_actions_layout.setDirection(QBoxLayout.Direction.LeftToRight)
        self._source_actions_layout.setSpacing(8 if mode == "compact" else 10)

    def _apply_action_bar_layout(self, mode: str) -> None:
        self._clear_layout(self._action_layout)
        self.total_label.show()
        self._action_buttons_wrap.show()

        if mode == "compact":
            self._action_layout.addWidget(self.total_label, 0, 0, 1, 1, Qt.AlignmentFlag.AlignLeft)
            self._action_layout.addWidget(self._action_buttons_wrap, 1, 0, 1, 1)
            self._action_layout.setColumnStretch(0, 1)
            self._action_layout.setColumnStretch(1, 0)
        else:
            self._action_layout.addWidget(self.total_label, 0, 0, 1, 1, Qt.AlignmentFlag.AlignVCenter)
            self._action_layout.addWidget(self._action_buttons_wrap, 0, 1, 1, 1)
            self._action_layout.setColumnStretch(0, 1)
            self._action_layout.setColumnStretch(1, 0)

    def _apply_sidebar_actions_layout(self, _mode: str, _sidebar_width: int) -> None:
        layout_mode = "single-column"
        if layout_mode == self._sidebar_actions_mode:
            return

        self._sidebar_actions_mode = layout_mode
        self._clear_layout(self._sidebar_actions_layout)
        self.btn_new.show()
        self.btn_new_group.show()
        self.btn_delete.show()
        self._sidebar_actions_layout.setColumnStretch(0, 1)
        self._sidebar_actions_layout.addWidget(self.btn_new, 0, 0)
        self._sidebar_actions_layout.addWidget(self.btn_new_group, 1, 0)
        self._sidebar_actions_layout.addWidget(self.btn_delete, 2, 0)

    def _apply_footer_layout(self, mode: str) -> None:
        if mode == "compact":
            self._footer_bar.setMinimumHeight(46)
            self._footer_bar.setMaximumHeight(54)
            margins = (12, 3, 12, 3)
        elif mode == "medium":
            self._footer_bar.setMinimumHeight(48)
            self._footer_bar.setMaximumHeight(56)
            margins = (14, 4, 14, 4)
        else:
            self._footer_bar.setMinimumHeight(48)
            self._footer_bar.setMaximumHeight(58)
            margins = (16, 4, 16, 4)
        self._footer_layout.setContentsMargins(*margins)
        self.cyber_footer.apply_layout_mode(mode)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(14, 14))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.setMinimumHeight(44)
        toolbar.setMaximumHeight(48)
        self.addToolBar(toolbar)

        toolbar.addAction("Tạo mới", self._new_log)
        toolbar.addAction("Nhập Excel", self._import_excel)
        toolbar.addAction("Xuất chưa gửi", self._export_unsent)
        toolbar.addSeparator()
        toolbar.addAction("Thư mục làm việc", self._choose_working_dir)
        toolbar.addAction("Cài font", self._show_font_settings)
        toolbar.addSeparator()
        toolbar.addAction("Trợ giúp", self._show_help)
        self._toolbar = toolbar

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.statusbar.setSizeGripEnabled(False)
        self.setStatusBar(self.statusbar)
        self.workdir_hint = QLabel("")
        self.workdir_hint.setObjectName("workdirHint")
        self.statusbar.addPermanentWidget(self.workdir_hint)

    def _setup_shortcuts(self):
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_log)
        self.addAction(save_action)

        export_action = QAction("Export", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export_single)
        self.addAction(export_action)

        new_action = QAction("New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_log)
        self.addAction(new_action)

        import_action = QAction("Import", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._import_excel)
        self.addAction(import_action)

    def _populate_month_filter(self):
        current = self.filter_month.currentText()
        self.filter_month.blockSignals(True)
        self.filter_month.clear()
        self.filter_month.addItem("Mọi tháng")
        today = date.today()
        month = today.month
        year = today.year
        for _ in range(18):
            self.filter_month.addItem(f"{year}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        if current:
            index = self.filter_month.findText(current)
            if index >= 0:
                self.filter_month.setCurrentIndex(index)
        self.filter_month.blockSignals(False)

    def _update_workdir_display(self):
        if self._working_dir:
            self.statusbar.showMessage(f"Thư mục làm việc: {self._working_dir}")
            self.workdir_hint.setText(self._working_dir)
        else:
            self.statusbar.showMessage("Chưa chọn thư mục làm việc.")
            self.workdir_hint.setText("Chưa cấu hình thư mục làm việc")
        self._update_opendir_tooltip()

    def _choose_working_dir(self):
        start_dir = self._working_dir or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục làm việc",
            start_dir,
            self._qt_file_dialog_options(
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
            ),
        )
        if folder:
            self._working_dir = folder
            self.preferences_service.set_working_directory(folder)
            self._update_workdir_display()
            self.toast.show_toast(f"Đã lưu thư mục làm việc: {folder}", "success")

    @property
    def _browse_dir(self) -> str:
        if self._working_dir and os.path.isdir(self._working_dir):
            return self._working_dir
        return os.path.expanduser("~")

    @staticmethod
    def _qt_file_dialog_options(extra: QFileDialog.Option = QFileDialog.Option(0)) -> QFileDialog.Option:
        return QFileDialog.Option.DontUseNativeDialog | extra

    def _open_working_dir(self):
        target = None
        if self._current_source_path and os.path.isdir(self._current_source_path):
            target = self._current_source_path
        elif self._working_dir and os.path.isdir(self._working_dir):
            target = self._working_dir

        if target:
            os.startfile(target)
            return
        self.toast.show_toast("Chưa có thư mục nguồn hoặc thư mục làm việc.", "warning")

    def _update_opendir_tooltip(self):
        if self._current_source_path and os.path.isdir(self._current_source_path):
            self.btn_open_dir.setToolTip(f"Mở thư mục nguồn: {self._current_source_path}")
        elif self._working_dir:
            self.btn_open_dir.setToolTip(f"Mở thư mục làm việc: {self._working_dir}")
        else:
            self.btn_open_dir.setToolTip("Chưa cấu hình thư mục")

    def _current_export_snapshot(self) -> WorkLog:
        return WorkLog(id=self.current_log_id, source_path=self._current_source_path)

    def _update_export_tooltip(self):
        default_dir = self.import_export_service.resolve_export_dir(
            self._current_export_snapshot()
        )
        self.btn_export.setToolTip(f"Thư mục xuất mặc định: {default_dir}")

    def _refresh_sidebar(self):
        self._apply_filters()

    def _apply_filters(self, _index: int = 0):
        status_idx = self.filter_status.currentIndex()
        is_sent: bool | None = None
        if status_idx == 1:
            is_sent = True
        elif status_idx == 2:
            is_sent = False

        month = None
        if self.filter_month.currentIndex() > 0:
            month = self.filter_month.currentText()

        logs = self.worklog_service.list_logs(
            search=self.search_input.text(),
            is_sent=is_sent,
            month=month,
        )
        self.sidebar_meta.setText(f"{len(logs)} phiếu")
        self.group_tree.reload(logs)
        self._update_sidebar_context()

    def _update_sidebar_context(self, current=None, previous=None):
        if self.group_tree.currentItem() is not None:
            self.sidebar_context.setText(self.group_tree.current_selection_summary())
            return

        if self.current_log_id is None:
            self.sidebar_context.setText("Phiếu mới chưa lưu. Nhập khách hàng hoặc dùng Nhập Excel để bắt đầu.")
            return

        self.sidebar_context.setText("Chưa chọn phiếu hoặc nhóm.")

    def _on_search(self, text: str):
        self._apply_filters()

    def _on_table_search(self, query: str):
        query_lower = query.strip().lower()
        self.item_table.set_search_query(query)

        match_count = 0
        if query_lower:
            for row in range(self.item_table.rowCount()):
                for col in range(self.item_table.columnCount()):
                    cell = self.item_table.item(row, col)
                    if cell and query_lower in cell.text().lower():
                        match_count += 1

        self.table_search_count.setText(f"{match_count} kết quả" if query_lower else "")

    def _on_log_selected(self, log_id: int):
        self._load_log(log_id)

    def _schedule_customer_autofill_refresh(self, _text: str):
        self._customer_autofill_timer.start()

    def _refresh_autofill(self):
        self._customer_autofill_timer.stop()
        data = self.worklog_service.get_autofill_data(self.customer_combo.currentText())
        blocker = QSignalBlocker(self.customer_combo)
        self.customer_combo.set_items(data.customers)
        del blocker
        self.item_table.set_content_suggestions(data.contents, data.price_map)

    def _update_source_label(self, source_path: str):
        self._source_label_raw_text = source_path or "Chưa có"
        self._refresh_source_label_text()

    def _refresh_source_label_text(self):
        text = self._source_label_raw_text or "Chưa có"
        available_width = max(120, self.source_label.width() - 4)
        elided = QFontMetrics(self.source_label.font()).elidedText(
            text,
            Qt.TextElideMode.ElideMiddle,
            available_width,
        )
        self.source_label.setText(elided)
        self.source_label.setToolTip("" if text == "Chưa có" else text)

    @staticmethod
    def _to_qdate(value: date) -> QDate:
        return QDate(value.year, value.month, value.day)

    @staticmethod
    def _from_qdate(value: QDate) -> date:
        return date(value.year(), value.month(), value.day())

    def _apply_log_to_form(self, log: WorkLog, *, log_id: int | None):
        self.current_log_id = log_id
        self._customer_autofill_timer.stop()
        blocker = QSignalBlocker(self.customer_combo)
        self.customer_combo.setCurrentText(log.customer_name)
        del blocker
        self.date_edit.setDate(self._to_qdate(log.work_date))
        self.sent_checkbox.setChecked(log.is_sent)
        self._current_source_path = log.source_path
        self._update_source_label(log.source_path)
        self.item_table.load_items(log.items)
        if not log.items:
            self.item_table.add_empty_row(default_date=log.work_date_display)
        self._on_total_changed(log.grand_total)
        self._update_opendir_tooltip()
        self._update_export_tooltip()
        self._refresh_autofill()

    def _new_log(self):
        empty_log = WorkLog(work_date=date.today())
        self._apply_log_to_form(empty_log, log_id=None)
        self.group_tree.blockSignals(True)
        self.group_tree.clearSelection()
        self.group_tree.setCurrentItem(None)
        self.group_tree.blockSignals(False)
        self._update_sidebar_context()
        self.statusbar.showMessage("Phiếu mới")

    def _build_form_log_snapshot(self) -> WorkLog:
        return WorkLog(
            id=self.current_log_id,
            customer_name=self.customer_combo.currentText().strip(),
            items=self.item_table.get_items(),
            work_date=self._from_qdate(self.date_edit.date()),
            is_sent=self.sent_checkbox.isChecked(),
            source_path=self._current_source_path,
        )

    def _load_log(self, log_id: int):
        log = self.worklog_service.get_log(log_id)
        if not log:
            return
        self._apply_log_to_form(log, log_id=log.id)
        self.statusbar.showMessage(f"Đã tải phiếu #{log_id}")

    def _save_log(self):
        try:
            saved = self.worklog_service.save_log(
                customer_name=self.customer_combo.currentText(),
                work_date=self._from_qdate(self.date_edit.date()),
                items=self.item_table.get_items(),
                is_sent=self.sent_checkbox.isChecked(),
                source_path=self._current_source_path,
                log_id=self.current_log_id,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Thiếu thông tin", str(exc))
            self.customer_combo.setFocus()
            return
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi lưu phiếu", str(exc))
            return

        self._apply_log_to_form(saved, log_id=saved.id)
        self._refresh_sidebar()
        self.group_tree.select_log(saved.id or 0)
        self._update_sidebar_context()
        self.toast.show_toast(f"Đã lưu phiếu #{saved.id}", "success")
        self.statusbar.showMessage(f"Phiếu #{saved.id} đã được lưu")

    def _create_new_group(self):
        self.group_tree.create_group_root()

    def _delete_log(self):
        if not self.current_log_id:
            return

        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            "Bạn có chắc muốn xóa phiếu này?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.worklog_service.delete_log(self.current_log_id)
        self._refresh_sidebar()
        self._new_log()
        self.toast.show_toast("Đã xóa phiếu", "warning")
        self.statusbar.showMessage("Đã xóa phiếu")

    def _duplicate_log(self):
        snapshot = self._build_form_log_snapshot()
        duplicated = self.worklog_service.duplicate_log(snapshot)
        self._apply_log_to_form(duplicated, log_id=None)
        self.toast.show_toast("Đã nhân đôi phiếu. Hãy rà lại ngày phiếu rồi lưu.", "info")
        self.statusbar.showMessage("Phiếu đã được nhân đôi")

    def _on_customer_selected(self, name: str):
        # Customer selection only updates the editor state.
        return

    def _on_total_changed(self, total: float):
        self.total_label.setText(f"Tổng cộng: {total:,.0f} đ")

    def _add_row(self):
        self.item_table.add_empty_row(default_date=format_display_date(self._from_qdate(self.date_edit.date())))

    def _remove_row(self):
        self.item_table.remove_selected_rows()

    def _load_font_settings(self):
        settings = self.preferences_service.get_table_font_settings()
        if settings:
            self.item_table.apply_font_settings(settings)

    def _show_font_settings(self):
        current = self.preferences_service.get_table_font_settings()
        dialog = FontSettingsDialog(current_settings=current, parent=self)
        if dialog.exec():
            settings = dialog.get_settings()
            self.item_table.apply_font_settings(settings)
            self.preferences_service.set_table_font_settings(settings)
            self.toast.show_toast("Đã cập nhật font bảng", "success")

    def _show_help(self):
        help_text = (
            "PHÍM TẮT BẢNG\n"
            "Enter: thêm dòng mới sau dòng hiện tại\n"
            "Ctrl+Enter: thêm dòng nội dung nối tiếp cho cụm ngày hiện tại\n"
            "Alt+Enter: thêm dòng mới và giữ ngày hiện tại\n"
            "Delete: xóa dòng đang chọn\n"
            "Ctrl+Z: hoàn tác xóa dòng\n\n"
            "PHÍM TẮT CHUNG\n"
            "Ctrl+S: lưu phiếu\n"
            "Ctrl+E: xuất Excel\n"
            "Ctrl+I: nhập Excel\n"
            "Ctrl+N: phiếu mới\n\n"
            "LƯU Ý\n"
            "- Ngày phiếu được lưu riêng, dùng cho lọc tháng, sidebar và tên file xuất.\n"
            "- NVKT là dữ liệu quản lý nội bộ của phiếu, không đi ra file Excel.\n"
            "- Dòng có ký hiệu ↳ là dòng nội dung nối tiếp, thuộc cùng ngày với dòng chính phía trên.\n"
            "- Kéo thả nhóm để đổi parent thật sự.\n"
            "- Kéo phiếu sang nhóm hoặc về vùng trống để bỏ phân loại."
        )
        QMessageBox.information(self, "Hướng dẫn sử dụng", help_text)

    def _import_excel(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn file Excel để nhập",
            self._browse_dir,
            "Excel Files (*.xlsx *.xls)",
            "",
            self._qt_file_dialog_options(),
        )
        if files:
            self._import_files(files)

    def _export_single(self):
        if not self.current_log_id:
            self._save_log()
            if not self.current_log_id:
                return

        log = self.worklog_service.get_log(self.current_log_id)
        if not log:
            return

        default_dir = self.import_export_service.resolve_export_dir(log)
        default_path = os.path.join(default_dir, self.import_export_service.default_filename(log))
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu file Excel",
            default_path,
            "Excel Files (*.xlsx)",
            "",
            self._qt_file_dialog_options(),
        )
        if not save_path:
            return

        if os.path.exists(save_path):
            reply = QMessageBox.question(
                self,
                "Xác nhận ghi đè",
                f"File đã tồn tại:\n{os.path.basename(save_path)}\n\nGhi đè?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            path = self.import_export_service.export_log(log, save_path)
        except PermissionError as exc:
            QMessageBox.warning(self, "Lỗi ghi file", str(exc))
            return

        self._update_export_tooltip()
        self.statusbar.showMessage(f"Đã xuất file: {path}")
        reply = QMessageBox.question(
            self,
            "Xuất Excel thành công",
            f"File đã được lưu tại:\n{path}\n\nMở file ngay?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.startfile(path)
            except OSError:
                pass

    def _export_unsent(self):
        logs = self.worklog_service.get_unsent_logs()
        if not logs:
            QMessageBox.information(self, "Không có dữ liệu", "Không có phiếu chưa gửi để xuất.")
            return

        reply = QMessageBox.question(
            self,
            "Xuất phiếu chưa gửi",
            f"Sẽ xuất {len(logs)} phiếu chưa gửi.\n\nYes: mỗi phiếu một file\nNo: gom nhiều sheet",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return

        try:
            if reply == QMessageBox.StandardButton.Yes:
                output_dir = QFileDialog.getExistingDirectory(
                    self,
                    "Chọn thư mục xuất các phiếu",
                    self.import_export_service.resolve_batch_export_dir(logs, self.current_log_id),
                    self._qt_file_dialog_options(
                        QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
                    ),
                )
                if not output_dir:
                    return
                paths = self.import_export_service.export_logs(logs, output_dir)
                self._update_export_tooltip()
                QMessageBox.information(
                    self,
                    "Xuất thành công",
                    f"Đã xuất {len(paths)} phiếu vào:\n{output_dir}",
                )
                try:
                    os.startfile(output_dir)
                except OSError:
                    pass
                self.statusbar.showMessage(f"Đã xuất {len(paths)} phiếu chưa gửi")
                return

            default_path = os.path.join(
                self.import_export_service.resolve_batch_export_dir(logs, self.current_log_id),
                f"NKLV_chua_gui_{date.today().strftime('%Y%m%d')}.xlsx",
            )
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Lưu file tổng hợp",
                default_path,
                "Excel Files (*.xlsx)",
                "",
                self._qt_file_dialog_options(),
            )
            if not save_path:
                return
            path = self.import_export_service.export_logs_multi_sheet(logs, save_path)
            self._update_export_tooltip()
            QMessageBox.information(self, "Xuất thành công", f"File đã được lưu tại:\n{path}")
            try:
                os.startfile(path)
            except OSError:
                pass
            self.statusbar.showMessage(f"Đã xuất file tổng hợp: {path}")
        except PermissionError as exc:
            QMessageBox.warning(self, "Lỗi ghi file", str(exc))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".xlsx", ".xls")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.toLocalFile().lower().endswith((".xlsx", ".xls"))
        ]
        if files:
            self._import_files(files)

    def _import_files(self, files: list[str]):
        result = self.import_export_service.import_files(files)
        self._refresh_sidebar()
        self._refresh_autofill()

        message = f"Đã nhập thành công {result.imported_count}/{len(files)} phiếu."
        if result.errors:
            message += "\n\nLỗi:\n" + "\n".join(result.errors)
        QMessageBox.information(self, "Kết quả nhập phiếu", message)

        if result.imported_ids:
            self._load_log(result.imported_ids[-1])
        self.statusbar.showMessage(f"Đã nhập {result.imported_count} phiếu từ Excel")

    def closeEvent(self, event):
        self.worklog_service.close()
        super().closeEvent(event)



