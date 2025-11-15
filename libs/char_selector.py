import logging
import types
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PyQt5.QtCore import QObject, QPoint, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyledItemDelegate,
)

try:
    from bidi.algorithm import get_display
except Exception:  # pragma: no cover - optional dependency
    get_display = None

logger = logging.getLogger("PPOCRLabel")


def enable_candidate_extraction(text_recognizer, top_k: int = 5) -> None:
    """
    Monkey patches the PaddleOCR text recognizer to retain per-character
    candidate probabilities that can later be surfaced by the GUI.
    """

    predictor = getattr(text_recognizer, "paddlex_predictor", None)
    if predictor is None:
        logger.warning("Candidate extraction skipped: predictor not ready")
        return

    if getattr(predictor, "_candidate_patch_enabled", False):
        predictor._candidate_top_k = max(1, top_k)
        return

    predictor._candidate_patch_enabled = True
    predictor._candidate_top_k = max(1, top_k)

    def _process_with_candidates(self, batch_data, return_word_box: bool = False):
        batch_raw_imgs = self.pre_tfs["Read"](imgs=batch_data.instances)
        width_list = []
        for img in batch_raw_imgs:
            width_list.append(img.shape[1] / float(img.shape[0]))
        indices = np.argsort(np.array(width_list))
        batch_imgs = self.pre_tfs["ReisizeNorm"](imgs=batch_raw_imgs)
        x = self.pre_tfs["ToBatch"](imgs=batch_imgs)
        batch_preds = self.infer(x=x)
        batch_num = self.batch_sampler.batch_size
        img_num = len(batch_raw_imgs)
        rec_image_shape = next(
            op["RecResizeImg"]["image_shape"]
            for op in self.config["PreProcess"]["transform_ops"]
            if "RecResizeImg" in op
        )
        imgC, imgH, imgW = rec_image_shape[:3]
        max_wh_ratio = imgW / imgH
        end_img_no = min(img_num, batch_num)
        wh_ratio_list = []
        for ino in range(0, end_img_no):
            h, w = batch_raw_imgs[indices[ino]].shape[0:2]
            wh_ratio = w * 1.0 / h
            max_wh_ratio = max(max_wh_ratio, wh_ratio)
            wh_ratio_list.append(wh_ratio)

        want_word_box = return_word_box or self.return_word_box
        decoded_texts, scores = self.post_op(
            batch_preds,
            return_word_box=True,
            wh_ratio_list=wh_ratio_list,
            max_wh_ratio=max_wh_ratio,
        )

        plain_texts: List[str] = []
        metadata: List[Optional[Sequence]] = []
        for entry in decoded_texts:
            if isinstance(entry, tuple):
                plain_texts.append(entry[0])
                metadata.append(entry[1])
            else:
                plain_texts.append(entry)
                metadata.append(None)

        char_candidates = _build_candidate_sequences(
            np.array(batch_preds[0]),
            plain_texts,
            metadata,
            self.post_op.character,
            self.post_op.get_ignored_tokens(),
            getattr(self, "_candidate_top_k", 5),
        )

        if self.model_name in (
            "arabic_PP-OCRv3_mobile_rec",
            "arabic_PP-OCRv5_mobile_rec",
        ):
            if get_display is not None:
                plain_texts = [get_display(s) for s in plain_texts]

        if want_word_box:
            rec_texts = [
                (text, meta) if meta is not None else text
                for text, meta in zip(plain_texts, metadata)
            ]
        else:
            rec_texts = plain_texts

        result = {
            "input_path": batch_data.input_paths,
            "page_index": getattr(
                batch_data, "page_indexes", [None] * len(batch_raw_imgs)
            ),
            "input_img": batch_raw_imgs,
            "rec_text": rec_texts,
            "rec_score": scores,
            "vis_font": [self.vis_font] * len(batch_raw_imgs),
            "char_candidates": char_candidates,
        }
        return result

    predictor.process = types.MethodType(_process_with_candidates, predictor)


def _build_candidate_sequences(
    logits_batch: np.ndarray,
    texts: Sequence[str],
    metadata: Sequence[Optional[Sequence]],
    character_list: Sequence[str],
    ignored_tokens: Iterable[int],
    top_k: int,
) -> List[List[dict]]:
    ignored = set(ignored_tokens)
    sequences: List[List[dict]] = []

    for sample_idx, (text, meta) in enumerate(zip(texts, metadata)):
        if not isinstance(text, str) or not text or meta is None:
            sequences.append([])
            continue

        try:
            _, grouped_chars, grouped_cols, _ = meta
        except Exception:
            sequences.append([])
            continue

        flat_chars: List[str] = []
        flat_cols: List[int] = []
        for chars, cols in zip(grouped_chars, grouped_cols):
            flat_chars.extend(chars)
            flat_cols.extend([int(c) for c in cols])

        if len(flat_chars) != len(text):
            flat_chars = list(text)

        valid_len = min(len(flat_chars), len(flat_cols), len(text))
        sample_logits = logits_batch[sample_idx]
        char_entries: List[dict] = []

        for idx in range(valid_len):
            column = flat_cols[idx]
            if column >= sample_logits.shape[0]:
                continue
            probs = sample_logits[column]
            sorted_indices = np.argsort(probs)[::-1]
            options: List[dict] = []
            for cls in sorted_indices:
                if cls in ignored:
                    continue
                char = character_list[cls]
                if not char or char == "blank":
                    continue
                options.append({"char": char, "score": float(probs[cls])})
                if len(options) >= top_k:
                    break
            char_entries.append(
                {
                    "char": flat_chars[idx],
                    "position": int(column),
                    "candidates": options,
                }
            )
        sequences.append(char_entries)

    return sequences


class CandidatePopup(QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_editor: Optional["CandidateLineEdit"] = None
        self._char_index: Optional[int] = None

    def show_options(
        self,
        editor: "CandidateLineEdit",
        char_index: int,
        options: Sequence[dict],
        current_char: str,
    ):
        self.clear()
        self._current_editor = editor
        self._char_index = char_index

        for opt in options:
            char = opt.get("char", "")
            if not char:
                continue
            score = opt.get("score", None)
            title = f"{char}"
            if isinstance(score, (float, int)):
                title = f"{char}  ({score:.2f})"
            action = QAction(title, self)
            action.setData(char)
            if char == current_char:
                font = QFont(action.font())
                font.setBold(True)
                action.setFont(font)
            self.addAction(action)

        if not self.actions():
            return

        cursor_rect = editor.cursorRect()
        global_point = editor.mapToGlobal(cursor_rect.bottomRight())
        action = self.exec_(global_point)
        if action and self._current_editor and self._char_index is not None:
            new_char = action.data()
            if isinstance(new_char, str):
                self._current_editor.replace_char(self._char_index, new_char)


class CandidateLineEdit(QLineEdit):
    def __init__(self, controller: "CharacterCandidateController", parent=None):
        super().__init__(parent)
        self._controller = controller
        self._item: Optional[QListWidgetItem] = None

    def set_item(self, item: QListWidgetItem):
        self._item = item

    def item(self) -> Optional[QListWidgetItem]:
        return self._item

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._controller.handle_click(self, event.pos())
        super().mouseDoubleClickEvent(event)

    def replace_char(self, index: int, new_char: str):
        text = self.text()
        if not text or index < 0 or index >= len(text):
            return
        if text[index] == new_char:
            return
        new_text = text[:index] + new_char + text[index + 1 :]
        cursor = index + 1
        block_state = self.blockSignals(True)
        self.setText(new_text)
        self.blockSignals(block_state)
        if self._item is not None:
            self._item.setText(new_text)
        self.setCursorPosition(cursor)


class CandidateDelegate(QStyledItemDelegate):
    def __init__(self, controller: "CharacterCandidateController"):
        super().__init__(controller.list_widget)
        self._controller = controller

    def createEditor(self, parent, option, index):
        editor = CandidateLineEdit(self._controller, parent)
        item = self._controller.list_widget.item(index.row())
        editor.set_item(item)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        editor.setText(value or "")

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), Qt.EditRole)


class CharacterCandidateController(QObject):
    """
    Bridges the label list editor with per-character candidate data.
    """

    def __init__(
        self,
        list_widget: QListWidget,
        resolve_shape: Callable[[Optional[QListWidgetItem]], object],
        candidate_loader: Optional[Callable[[object], bool]] = None,
        parent=None,
    ):
        super().__init__(parent or list_widget)
        self.list_widget = list_widget
        self._resolve_shape = resolve_shape
        self._candidate_loader = candidate_loader
        self._popup = CandidatePopup(list_widget)
        self._delegate = CandidateDelegate(self)
        self.list_widget.setItemDelegate(self._delegate)

    def handle_click(self, editor: CandidateLineEdit, local_pos: QPoint):
        item = editor.item()
        if item is None:
            return

        cursor_index = editor.cursorPositionAt(local_pos)
        text = editor.text()
        if not text:
            return
        if cursor_index >= len(text):
            cursor_index = len(text) - 1
        if cursor_index < 0:
            return

        shape = self._resolve_shape(item)
        if shape is None:
            return

        sequence = getattr(shape, "char_candidates", None)
        if (not sequence) and self._candidate_loader:
            try:
                if self._candidate_loader(shape):
                    sequence = getattr(shape, "char_candidates", None)
            except Exception as exc:  # pragma: no cover - GUI helper
                logger.warning("Failed to load candidate list: %s", exc)
        if not sequence:
            return

        if cursor_index >= len(sequence):
            cursor_index = len(sequence) - 1

        entry = sequence[cursor_index]
        options = entry.get("candidates", [])
        filtered = [opt for opt in options if opt.get("char")]
        current_char = text[cursor_index]
        if not filtered:
            return
        if len(filtered) == 1 and filtered[0].get("char") == current_char:
            return

        editor.setCursorPosition(cursor_index)
        self._popup.show_options(editor, cursor_index, filtered, current_char)
