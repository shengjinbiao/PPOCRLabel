# -*- coding: utf-8 -*-
import os
from pathlib import Path

import yaml
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
    QGridLayout,
)


def has_inference_files(directory):
    try:
        entries = os.listdir(directory)
    except OSError:
        return False
    model_suffixes = (".pdmodel", ".json", ".model")
    params_suffixes = (".pdiparams", ".pdparams", ".params", ".bin")
    has_model = any(name.lower().endswith(model_suffixes) for name in entries)
    has_params = any(name.lower().endswith(params_suffixes) for name in entries)
    return has_model and has_params


def read_inference_meta(directory):
    info = {}
    if not directory:
        return info
    yml_path = os.path.join(directory, "inference.yml")
    if not os.path.exists(yml_path):
        return info
    try:
        with open(yml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return info
    if not isinstance(data, dict):
        return info
    info["model_name"] = (
        data.get("model_name")
        or data.get("Global", {}).get("model_name")
        or data.get("Model", {}).get("model_name")
    )
    info["model_type"] = (
        data.get("model_type")
        or data.get("Global", {}).get("model_type")
        or data.get("Model", {}).get("model_type")
        or data.get("Architecture", {}).get("model_type")
    )
    return info


def normalize_model_type(value):
    if not value or not isinstance(value, str):
        return None
    lower = value.lower()
    det_tokens = ["det", "layout", "structure", "table"]
    rec_tokens = ["rec", "svtr", "recognition"]
    if any(token in lower for token in det_tokens):
        return "det"
    if any(token in lower for token in rec_tokens):
        return "rec"
    return None


def infer_type_from_path(directory):
    if not directory:
        return None
    parts = [os.path.basename(directory).lower()]
    parent = os.path.basename(os.path.dirname(directory)).lower()
    parts.append(parent)
    for part in parts:
        t = normalize_model_type(part)
        if t:
            return t
    return None


def resolve_model_dir(directory):
    if not directory or not os.path.isdir(directory):
        return None
    if has_inference_files(directory):
        return directory
    for name in ("inference", "deploy", "output"):
        candidate = os.path.join(directory, name)
        if os.path.isdir(candidate) and has_inference_files(candidate):
            return candidate
    return None


def validate_model_dir(directory):
    if not directory:
        return False, None
    if not has_inference_files(directory):
        return False, None
    meta = read_inference_meta(directory)
    model_type = normalize_model_type(meta.get("model_type"))
    if not model_type:
        model_type = infer_type_from_path(directory)
    return True, model_type


def discover_model_entries(official_dir, extra_dir):
    entries = {"det": [], "rec": []}
    bases = []
    if official_dir and os.path.isdir(official_dir):
        bases.append(("[Official]", official_dir))
    if extra_dir and os.path.isdir(extra_dir):
        bases.append(("[Custom]", extra_dir))
    seen = set()
    for prefix, base in bases:
        try:
            subdirs = sorted(
                [
                    name
                    for name in os.listdir(base)
                    if os.path.isdir(os.path.join(base, name))
                ]
            )
        except OSError:
            continue
        for name in subdirs:
            resolved = resolve_model_dir(os.path.join(base, name))
            if not resolved or resolved in seen:
                continue
            seen.add(resolved)
            valid, model_type = validate_model_dir(resolved)
            if not valid:
                continue
            label = f"{prefix} {name}"
            if model_type == "det":
                entries["det"].append((label, resolved))
            elif model_type == "rec":
                entries["rec"].append((label, resolved))
    return entries


class ModelSelectDialog(QDialog):
    def __init__(
        self,
        parent,
        get_str,
        official_dir,
        extra_dir,
        entries,
        current_det,
        current_rec,
    ):
        super(ModelSelectDialog, self).__init__(parent)
        self.setWindowTitle(get_str("customModelDialogTitle"))
        self.get_str = get_str
        self.official_dir = official_dir
        self.extra_dir = extra_dir
        self.detCombo = QComboBox()
        self.recCombo = QComboBox()
        self.default_label = get_str("customModelDefault")
        self.entries = entries or {"det": [], "rec": []}
        self._populate(current_det, current_rec)

        infoLayout = QGridLayout()
        self.officialLabel = QLabel(
            f"{get_str('customModelOfficialDir')}: {official_dir or '-'}"
        )
        self.extraLabel = QLabel(
            f"{get_str('customModelSearchDir')}: {extra_dir or '-'}"
        )
        changeExtraBtn = QPushButton(get_str("customModelBrowse"))
        changeExtraBtn.clicked.connect(self._change_extra_dir)
        infoLayout.addWidget(self.officialLabel, 0, 0, 1, 2)
        infoLayout.addWidget(self.extraLabel, 1, 0)
        infoLayout.addWidget(changeExtraBtn, 1, 1)

        detBrowse = QPushButton(get_str("customModelBrowse"))
        detBrowse.clicked.connect(lambda: self._browse("det"))
        recBrowse = QPushButton(get_str("customModelBrowse"))
        recBrowse.clicked.connect(lambda: self._browse("rec"))

        detLayout = QHBoxLayout()
        detLayout.addWidget(QLabel(get_str("customModelDetLabel")))
        detLayout.addWidget(self.detCombo, 1)
        detLayout.addWidget(detBrowse)

        recLayout = QHBoxLayout()
        recLayout.addWidget(QLabel(get_str("customModelRecLabel")))
        recLayout.addWidget(self.recCombo, 1)
        recLayout.addWidget(recBrowse)

        buttonLayout = QHBoxLayout()
        okBtn = QPushButton(get_str("ok"))
        cancelBtn = QPushButton(get_str("cancel"))
        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.reject)
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(okBtn)
        buttonLayout.addWidget(cancelBtn)

        layout = QVBoxLayout()
        layout.addLayout(infoLayout)
        layout.addLayout(detLayout)
        layout.addLayout(recLayout)
        layout.addLayout(buttonLayout)
        self.setLayout(layout)

    def _populate(self, current_det, current_rec):
        self.detCombo.clear()
        self.detCombo.addItem(self.default_label, None)
        for label, path in self.entries.get("det", []):
            self.detCombo.addItem(label, path)
        if current_det:
            idx = self.detCombo.findData(current_det)
            if idx != -1:
                self.detCombo.setCurrentIndex(idx)

        self.recCombo.clear()
        self.recCombo.addItem(self.default_label, None)
        for label, path in self.entries.get("rec", []):
            self.recCombo.addItem(label, path)
        if current_rec:
            idx = self.recCombo.findData(current_rec)
            if idx != -1:
                self.recCombo.setCurrentIndex(idx)

    def _browse(self, mode):
        base = self.extra_dir or self.official_dir or "."
        path = QFileDialog.getExistingDirectory(
            self,
            self.get_str("customModelDetLabel")
            if mode == "det"
            else self.get_str("customModelRecLabel"),
            base,
        )
        if not path:
            return
        resolved = resolve_model_dir(path)
        if not resolved:
            QMessageBox.warning(self, "Warning", self.get_str("customModelInvalid"))
            return
        valid, model_type = validate_model_dir(resolved)
        expected = "det" if mode == "det" else "rec"
        if not valid or (model_type and model_type != expected):
            QMessageBox.warning(
                self,
                "Warning",
                self.get_str("customModelTypeMismatch").format(
                    model_type or "Unknown",
                    self.get_str("customModelDetLabel")
                    if mode == "det"
                    else self.get_str("customModelRecLabel"),
                ),
            )
            return
        combo = self.detCombo if mode == "det" else self.recCombo
        idx = combo.findData(resolved)
        if idx == -1:
            combo.addItem(os.path.basename(resolved), resolved)
            idx = combo.count() - 1
        combo.setCurrentIndex(idx)

    def _change_extra_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, self.get_str("customModelSearchDir"), self.extra_dir or "."
        )
        if not path:
            return
        self.extra_dir = path
        self.entries = discover_model_entries(self.official_dir, self.extra_dir)
        self.extraLabel.setText(
            f"{self.get_str('customModelSearchDir')}: {self.extra_dir}"
        )
        self._populate(self.detCombo.currentData(), self.recCombo.currentData())

    def selected_paths(self):
        return (
            self.detCombo.currentData(),
            self.recCombo.currentData(),
            self.extra_dir,
        )
