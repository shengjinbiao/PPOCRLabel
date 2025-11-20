import copy
from typing import Iterable, List, Optional

from PyQt5.QtCore import Qt, QSize, QEvent
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
    QToolButton,
    QSlider,
    QSpinBox,
)


class ProofreadDialog(QDialog):
    """
    Dialog that mimics the eScriptorium single-line proofreading workflow.
    Shows a cropped line image, editable text, review stage selector, history list,
    and offers keyboard navigation for adjacent lines.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strings = {
            "title": "Line Proofread",
            "stage": "Review stage",
            "history": "History",
            "apply": "Apply selection",
            "text_placeholder": "Enter corrected text...",
            "history_empty": "No history records yet.",
            "prev": "Previous line",
            "next": "Next line",
            "zoom": "Zoom",
            "font": "Font size",
        }
        self._history_entries: List[dict] = []
        self._pixmap: Optional[QPixmap] = None
        self._nav_direction = 0
        self._image_scale = 1.0
        self._font_size = 20

        self.setMinimumSize(QSize(640, 520))

        self.imageLabel = QLabel()
        self.imageLabel.setAlignment(Qt.AlignCenter)
        self.imageLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.imageLabel.setMinimumHeight(160)

        self.textEdit = QPlainTextEdit()
        self.textEdit.setPlaceholderText(self._strings["text_placeholder"])
        self.textEdit.setTabChangesFocus(True)
        self.textEdit.installEventFilter(self)
        self._apply_font_size(self._font_size)

        self.stageCombo = QComboBox()
        self.stageCombo.setEditable(True)
        self.stageCombo.setInsertPolicy(QComboBox.NoInsert)

        self.historyList = QListWidget()
        self.historyList.setSelectionMode(QListWidget.SingleSelection)
        self.historyList.itemDoubleClicked.connect(self._apply_history_to_editor)

        self.applyHistoryButton = QPushButton(self._strings["apply"])
        self.applyHistoryButton.clicked.connect(self._apply_history_to_editor)

        stageLayout = QHBoxLayout()
        self.stageLabel = QLabel(self._strings["stage"])
        stageLayout.addWidget(self.stageLabel)
        stageLayout.addWidget(self.stageCombo, 1)
        stageLayout.addWidget(self.applyHistoryButton)

        editorLayout = QVBoxLayout()
        editorLayout.addWidget(self.textEdit)
        editorLayout.addLayout(stageLayout)

        historyLayout = QVBoxLayout()
        self.historyLabel = QLabel(self._strings["history"])
        historyLayout.addWidget(self.historyLabel)
        historyLayout.addWidget(self.historyList)

        textAndHistory = QSplitter(Qt.Vertical)
        editorContainer = QWidget()
        editorContainer.setLayout(editorLayout)
        historyContainer = QWidget()
        historyContainer.setLayout(historyLayout)
        textAndHistory.addWidget(editorContainer)
        textAndHistory.addWidget(historyContainer)
        textAndHistory.setStretchFactor(0, 3)
        textAndHistory.setStretchFactor(1, 2)

        self.prevButton = QToolButton()
        self.nextButton = QToolButton()
        self.prevButton.clicked.connect(lambda: self._commit_and_navigate(-1))
        self.nextButton.clicked.connect(lambda: self._commit_and_navigate(1))

        self.zoomSlider = QSlider(Qt.Horizontal)
        self.zoomSlider.setRange(50, 300)
        self.zoomSlider.setValue(100)
        self.zoomSlider.setSingleStep(10)
        self.zoomSlider.valueChanged.connect(self._handle_zoom_changed)
        self.fontSizeSpin = QSpinBox()
        self.fontSizeSpin.setRange(12, 72)
        self.fontSizeSpin.setValue(self._font_size)
        self.fontSizeSpin.valueChanged.connect(self._apply_font_size)

        navLayout = QHBoxLayout()
        navLayout.addWidget(self.prevButton)
        navLayout.addWidget(self.nextButton)
        navLayout.addStretch(1)
        self.zoomLabel = QLabel(self._strings["zoom"])
        navLayout.addWidget(self.zoomLabel)
        navLayout.addWidget(self.zoomSlider, 2)
        self.fontLabel = QLabel(self._strings["font"])
        navLayout.addWidget(self.fontLabel)
        navLayout.addWidget(self.fontSizeSpin)

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addLayout(navLayout)
        layout.addWidget(self.imageLabel, 2)
        layout.addWidget(textAndHistory, 3)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

        self.setLayout(layout)

    def retranslate(self, strings: Optional[dict] = None):
        if strings:
            self._strings.update(strings)
        self.setWindowTitle(self._strings.get("title", "Line Proofread"))
        self.stageLabel.setText(self._strings.get("stage", "Review stage"))
        self.historyLabel.setText(self._strings.get("history", "History"))
        self.applyHistoryButton.setText(self._strings.get("apply", "Apply selection"))
        self.prevButton.setText(self._strings.get("prev", "Previous line"))
        self.nextButton.setText(self._strings.get("next", "Next line"))
        self.zoomLabel.setText(self._strings.get("zoom", "Zoom"))
        self.fontLabel.setText(self._strings.get("font", "Font size"))
        self.textEdit.setPlaceholderText(
            self._strings.get("text_placeholder", "Enter corrected text...")
        )
        self._refresh_history()

    def prepare_for_shape(self):
        self._nav_direction = 0

    def set_stage_options(self, options: Iterable[str], current: str = ""):
        self.stageCombo.clear()
        seen = []
        for opt in options or []:
            if opt and opt not in seen:
                seen.append(opt)
                self.stageCombo.addItem(opt)
        self.stageCombo.setCurrentText(current or (seen[0] if seen else ""))

    def set_text(self, text: str):
        self.textEdit.setPlainText(text or "")
        cursor = self.textEdit.textCursor()
        cursor.movePosition(cursor.End)
        self.textEdit.setTextCursor(cursor)

    def set_pixmap(self, pixmap: Optional[QPixmap]):
        self._pixmap = pixmap
        self._update_scaled_pixmap()

    def set_history(self, history: Optional[List[dict]]):
        self._history_entries = copy.deepcopy(history or [])
        self._refresh_history()

    def set_zoom(self, percent: int):
        percent = max(10, min(percent, 400))
        self.zoomSlider.blockSignals(True)
        self.zoomSlider.setValue(percent)
        self.zoomSlider.blockSignals(False)
        self._image_scale = percent / 100.0
        self._update_scaled_pixmap()

    def take_navigation_direction(self):
        direction = self._nav_direction
        self._nav_direction = 0
        return direction

    def _refresh_history(self):
        self.historyList.clear()
        if not self._history_entries:
            empty = QListWidgetItem(self._strings.get("history_empty", "No history"))
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
            self.historyList.addItem(empty)
            return
        for entry in self._history_entries:
            stamp = entry.get("timestamp", "")
            stage = entry.get("stage") or ""
            action = entry.get("type") or ""
            new_text = entry.get("text") or ""
            old_text = entry.get("previous_text") or ""
            summary = f"{stamp}"
            details = []
            if stage:
                details.append(stage)
            if action:
                details.append(action)
            if details:
                summary += f" [{' / '.join(details)}]"
            summary += f": {new_text}"
            if old_text and old_text != new_text:
                summary += f"  ← {old_text}"
            item = QListWidgetItem(summary)
            item.setToolTip(summary)
            self.historyList.addItem(item)

    def _apply_history_to_editor(self):
        current = self.historyList.currentRow()
        if current < 0 or current >= len(self._history_entries):
            return
        text = self._history_entries[current].get("text") or ""
        self.textEdit.setPlainText(text)

    def _update_scaled_pixmap(self):
        if not self._pixmap:
            self.imageLabel.clear()
            return
        target_size = self.imageLabel.size() * self._image_scale
        scaled = self._pixmap.scaled(
            target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.imageLabel.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def get_result(self):
        return self.textEdit.toPlainText().strip(), self.stageCombo.currentText().strip()

    def eventFilter(self, obj, event):
        if obj == self.textEdit and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Up, Qt.Key_PageUp):
                self._commit_and_navigate(-1)
                return True
            if event.key() in (Qt.Key_Down, Qt.Key_PageDown):
                self._commit_and_navigate(1)
                return True
        return super().eventFilter(obj, event)

    def _handle_zoom_changed(self, value):
        self._image_scale = value / 100.0
        self._update_scaled_pixmap()

    def _apply_font_size(self, value):
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = self._font_size
        size = max(8, min(size, 96))
        self._font_size = size
        font = QFont(self.textEdit.font())
        font.setPointSize(size)
        self.textEdit.setFont(font)
        if hasattr(self, "fontSizeSpin") and self.fontSizeSpin.value() != size:
            self.fontSizeSpin.blockSignals(True)
            self.fontSizeSpin.setValue(size)
            self.fontSizeSpin.blockSignals(False)

    def _commit_and_navigate(self, direction):
        if direction not in (-1, 1):
            return
        self._nav_direction = direction
        self.accept()
