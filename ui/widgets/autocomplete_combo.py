"""Auto-complete combo box widget with search-as-you-type."""
from PySide6.QtWidgets import QComboBox, QCompleter
from PySide6.QtCore import QSignalBlocker, Qt, Signal, QStringListModel


class AutoCompleteCombo(QComboBox):
    """Editable combo box with filtered auto-complete suggestions."""

    item_selected = Signal(str)

    def __init__(self, parent=None, placeholder: str = ""):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lineEdit().setPlaceholderText(placeholder)

        self._completer = QCompleter([], self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        # Popup styling handled by styles.qss QListView rules
        self.setCompleter(self._completer)

        self._items_set: set[str] = set()
        self.currentTextChanged.connect(self._on_text_changed)

    def set_items(self, items: list[str]):
        """Update the available items for auto-complete."""
        current_text = self.currentText()
        blocker = QSignalBlocker(self)
        self.clear()
        self.addItems(items)
        self._items_set = set(items)  # L03: O(1) lookup cache
        model = QStringListModel(items, self)
        self._completer.setModel(model)
        if current_text:
            self.setCurrentText(current_text)
        else:
            self.setCurrentIndex(-1)
            self.setEditText("")
        del blocker

    def _on_text_changed(self, text: str):
        if text and text in self._items_set:
            self.item_selected.emit(text)
