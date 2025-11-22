# Copyright (c) <2015-Present> Tzutalin
# Copyright (C) 2013  MIT, Computer Science and Artificial Intelligence Laboratory. Bryan Russell, Antonio Torralba,
# William T. Freeman. Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction, including without
# limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
# NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# !/usr/bin/env python
# -*- coding: utf-8 -*-
# pyrcc5 -o libs/resources.py resources.qrc
import argparse
import ast
import codecs
import datetime
import json
import os
import platform
import subprocess
import sys
import tempfile
import shutil
import copy
import uuid
from pathlib import Path
from functools import partial

import openpyxl
import cv2
import numpy as np
import requests

from PyQt5.QtCore import (
    QSize,
    Qt,
    QPoint,
    QByteArray,
    QTimer,
    QFileInfo,
    QPointF,
    QProcess,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QImage,
    QCursor,
    QPixmap,
    QImageReader,
    QColor,
    QIcon,
    QFontDatabase,
    QTextCursor,
    QBrush,
)
from PyQt5.QtWidgets import (
    QMainWindow,
    QListWidget,
    QVBoxLayout,
    QSpinBox,
    QToolButton,
    QHBoxLayout,
    QDockWidget,
    QWidget,
    QSlider,
    QGraphicsOpacityEffect,
    QMessageBox,
    QListView,
    QScrollArea,
    QWidgetAction,
    QApplication,
    QLabel,
    QGridLayout,
    QFileDialog,
    QListWidgetItem,
    QComboBox,
    QDialog,
    QAbstractItemView,
    QMenu,
    QAction,
    QActionGroup,
    QPushButton,
    QPlainTextEdit,
    QInputDialog,
    QProgressDialog,
)

__dir__ = os.path.dirname(__file__)

from pandas.io.sql import has_table

sys.path.append(os.path.join(__dir__, ""))

import paddle
from paddleocr import PaddleOCR, PPStructureV3, TextRecognition, TextDetection
import libs.resources
from libs.constants import (
    SETTING_ADVANCE_MODE,
    SETTING_DRAW_SQUARE,
    SETTING_FILENAME,
    SETTING_FILL_COLOR,
    SETTING_LAST_OPEN_DIR,
    SETTING_LINE_COLOR,
    SETTING_PAINT_INDEX,
    SETTING_PAINT_LABEL,
    SETTING_RECENT_FILES,
    SETTING_SAVE_DIR,
    SETTING_WIN_POSE,
    SETTING_WIN_SIZE,
    SETTING_WIN_STATE,
    SETTING_TEXT_LAYOUT_MODE,
    SETTING_TRAIN_REPO_DIR,
    SETTING_TRAIN_DATASET_DIR,
    SETTING_TRAIN_OUTPUT_DIR,
    SETTING_TRAIN_CONFIG_PATH,
    SETTING_TRAIN_BATCH_SIZE,
    SETTING_TRAIN_EPOCHS,
    SETTING_DET_MODEL_PATH,
    SETTING_REC_MODEL_PATH,
    SETTING_MODEL_SEARCH_DIR,
    SETTING_TRAIN_AUTO_EXPORT,
    SETTING_READING_ORDER,
    SETTING_RESULT_FONT_SIZE,
    SETTING_DET_PANEL_VISIBLE,
    SETTING_PROOFREAD_ENDPOINT,
    SETTING_PROOFREAD_STYLE,
    SETTING_PROOFREAD_MODEL,
    SETTING_PROOFREAD_API_KEY,
)
from libs.model_selector import (
    ModelSelectDialog,
    discover_model_entries,
    resolve_model_dir,
    validate_model_dir,
    read_inference_meta,
)
from libs.utils import (
    addActions,
    boxPad,
    convert_token,
    expand_list,
    fmtShortcut,
    get_rotate_crop_image,
    have_qstring,
    keysInfo,
    natural_sort,
    newAction,
    newIcon,
    rebuild_html_from_ppstructure_label,
    stepsInfo,
    polygon_bounding_box_center_and_area,
    map_value,
    struct,
)
from libs.labelColor import label_colormap
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR, DEFAULT_LOCK_COLOR
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.autoDialog import AutoDialog
from libs.labelDialog import LabelDialog
from libs.proofreadDialog import ProofreadDialog
from libs.colorDialog import ColorDialog
from libs.hashableQListWidgetItem import HashableQListWidgetItem
from libs.editinlist import EditInList
from libs.unique_label_qlist_widget import UniqueLabelQListWidget
from libs.keyDialog import KeyDialog
from libs.char_selector import (
    CharacterCandidateController,
    enable_candidate_extraction,
)
from libs.lexicon_manager import LexiconLanguageModel

import logging

logger = logging.getLogger("PPOCRLabel")

DEFAULT_PROOFREAD_URL = os.getenv(
    "PPOCRLABEL_PROOFREAD_URL", "http://192.168.1.103:1234"
)
DEFAULT_PROOFREAD_STYLE = os.getenv("PPOCRLABEL_PROOFREAD_STYLE", "json").lower()
DEFAULT_PROOFREAD_MODEL = os.getenv("PPOCRLABEL_PROOFREAD_MODEL", "")
DEFAULT_PROOFREAD_API_KEY = os.getenv("PPOCRLABEL_PROOFREAD_API_KEY", "")


__appname__ = "PPOCRLabel"

LABEL_COLORMAP = label_colormap()


class TrainingLogDialog(QDialog):
    stopRequested = pyqtSignal()

    def __init__(self, parent=None, title="PaddleOCR Training", stop_label="Stop", close_label="Close"):
        super(TrainingLogDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 420)
        self.logView = QPlainTextEdit(self)
        self.logView.setReadOnly(True)
        self.stopButton = QPushButton(stop_label, self)
        self.closeButton = QPushButton(close_label, self)
        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(self.stopButton)
        buttonLayout.addWidget(self.closeButton)
        layout = QVBoxLayout()
        layout.addWidget(self.logView)
        layout.addLayout(buttonLayout)
        self.setLayout(layout)
        self.stopButton.clicked.connect(self._handle_stop)
        self.closeButton.clicked.connect(self.reject)
        self._stop_enabled = True

    def _handle_stop(self):
        if not self._stop_enabled:
            return
        self.stopButton.setEnabled(False)
        self._stop_enabled = False
        self.stopRequested.emit()

    def append_text(self, text):
        if not text:
            return
        self.logView.moveCursor(QTextCursor.End)
        self.logView.insertPlainText(text)
        self.logView.moveCursor(QTextCursor.End)

    def set_running(self, running):
        self._stop_enabled = running
        self.stopButton.setEnabled(running)
class MainWindow(QMainWindow):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(
        self,
        lang="ch",
        gpu=False,
        img_list_natural_sort=True,
        bbox_auto_zoom_center=False,
        kie_mode=False,
        default_filename=None,
        default_predefined_class_file=None,
        default_save_dir=None,
        det_model_dir=None,
        rec_model_dir=None,
        cls_model_dir=None,
        label_font_path=None,
        selected_shape_color=(255, 255, 0),
        text_layout_mode=None,
        proofread_url=None,
        proofread_style=None,
        proofread_model=None,
        proofread_api_key=None,
    ):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)
        self.setWindowState(Qt.WindowMaximized)  # set window max
        self.activateWindow()  # PPOCRLabel goes to the front when activate

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings
        stored_font_size = settings.get(SETTING_RESULT_FONT_SIZE, 18)
        try:
            stored_font_size = int(stored_font_size)
        except (TypeError, ValueError):
            stored_font_size = 18
        self.result_font_size = max(8, min(48, stored_font_size))
        stored_box_panel_visibility = settings.get(SETTING_DET_PANEL_VISIBLE, False)
        if isinstance(stored_box_panel_visibility, str):
            stored_box_panel_visibility = stored_box_panel_visibility.lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
        else:
            stored_box_panel_visibility = bool(stored_box_panel_visibility)
        self.box_panel_visible = stored_box_panel_visibility
        auto_export = settings.get(SETTING_TRAIN_AUTO_EXPORT)
        if auto_export is None:
            auto_export = True
        self.auto_export_trained_model = bool(auto_export)
        self.settings[SETTING_TRAIN_AUTO_EXPORT] = self.auto_export_trained_model
        self.lang = lang
        self.gpu = "gpu" if paddle.is_compiled_with_cuda() and gpu else "cpu"
        self.img_list_natural_sort = img_list_natural_sort
        self.bbox_auto_zoom_center = bbox_auto_zoom_center
        self.det_model_dir = det_model_dir
        self.rec_model_dir = rec_model_dir
        self.cls_model_dir = cls_model_dir

        # Load string bundle for i18n
        if lang not in ["ch", "en"]:
            lang = "en"
        self.stringBundle = StringBundle.getBundle(
            localeStr="zh-CN" if lang == "ch" else "en"
        )  # 'en'

        def get_str(str_id):
            return self.stringBundle.getString(str_id)
        self.get_str = get_str

        # KIE setting
        self.kie_mode = kie_mode
        self.key_previous_text = ""
        self.existed_key_cls_set = set()
        self.key_dialog_tip = get_str("keyDialogTip")

        self.defaultSaveDir = default_save_dir

        stored_layout_mode = settings.get(SETTING_TEXT_LAYOUT_MODE)
        if text_layout_mode is not None:
            self.text_layout_mode = text_layout_mode
        elif stored_layout_mode is not None:
            self.text_layout_mode = stored_layout_mode
        else:
            self.text_layout_mode = "horizontal"
        self.use_vertical_text = self.text_layout_mode == "vertical"
        self.settings[SETTING_TEXT_LAYOUT_MODE] = self.text_layout_mode
        stored_reading_order = settings.get(SETTING_READING_ORDER, "horizontal")
        if stored_reading_order not in ("horizontal", "vertical"):
            stored_reading_order = "horizontal"
        self.reading_mode = stored_reading_order
        self.settings[SETTING_READING_ORDER] = self.reading_mode
        stored_proofreader_endpoint = settings.get(SETTING_PROOFREAD_ENDPOINT)
        if proofread_url:
            self.proofreader_endpoint = proofread_url
            settings[SETTING_PROOFREAD_ENDPOINT] = proofread_url
        elif stored_proofreader_endpoint:
            self.proofreader_endpoint = stored_proofreader_endpoint
        else:
            self.proofreader_endpoint = DEFAULT_PROOFREAD_URL
        stored_proofreader_style = settings.get(SETTING_PROOFREAD_STYLE)
        chosen_style = proofread_style or stored_proofreader_style or DEFAULT_PROOFREAD_STYLE
        if not isinstance(chosen_style, str):
            chosen_style = "json"
        chosen_style = chosen_style.lower()
        if chosen_style not in ("json", "openai"):
            chosen_style = "json"
        self.proofreader_style = chosen_style
        settings[SETTING_PROOFREAD_STYLE] = self.proofreader_style
        stored_proofreader_model = settings.get(SETTING_PROOFREAD_MODEL, DEFAULT_PROOFREAD_MODEL)
        if proofread_model is not None:
            self.proofreader_model = proofread_model
            settings[SETTING_PROOFREAD_MODEL] = proofread_model
        else:
            self.proofreader_model = stored_proofreader_model or DEFAULT_PROOFREAD_MODEL
            settings[SETTING_PROOFREAD_MODEL] = self.proofreader_model
        stored_proofreader_api_key = settings.get(
            SETTING_PROOFREAD_API_KEY, DEFAULT_PROOFREAD_API_KEY
        )
        if proofread_api_key is not None:
            self.proofreader_api_key = proofread_api_key
            settings[SETTING_PROOFREAD_API_KEY] = proofread_api_key
        else:
            self.proofreader_api_key = stored_proofreader_api_key or ""
        self.proofreader_timeout = 45

        self.lexicon_manager = LexiconLanguageModel(
            Path(__dir__) / "data" / "custom_words.txt",
            Path(__dir__) / "data" / "custom_corpus.txt",
        )

        self._reload_ocr_backends()
        rec_kwargs = {
            "device": self.gpu,
            "model_name": self._infer_model_name(
                self.rec_model_dir, "PP-OCRv5_mobile_rec"
            ),
        }
        if self.rec_model_dir:
            rec_kwargs["model_dir"] = self.rec_model_dir
        self.text_recognizer = TextRecognition(**rec_kwargs)
        enable_candidate_extraction(self.text_recognizer, top_k=10)

        det_kwargs = {
            "device": self.gpu,
            "model_name": self._infer_model_name(
                self.det_model_dir, "PP-OCRv5_mobile_det"
            ),
        }
        if self.det_model_dir:
            det_kwargs["model_dir"] = self.det_model_dir
        self.text_detector = TextDetection(**det_kwargs)

        if os.path.exists("./data/paddle.png"):
            self.ocr.predict("./data/paddle.png")
            self.table_ocr.predict("./data/paddle.png")

        # For loading all image under a directory
        self.mImgList = []
        self.mImgList5 = []
        self.dirname = None
        self.labelHist = []
        self.lastOpenDir = None
        self.result_dic = []
        self.result_dic_locked = []
        self._candidate_cache = {}
        self._score_cache = {}
        self._cache_owner = None
        self.changeFileFolder = False
        self.haveAutoReced = False
        self.trainingProcess = None
        self.trainingDialog = None
        self.labelFile = None
        self.currIndex = 0
        self._currentAutoSplitDir = None
        self._pendingTrainJob = None
        self._exportProcess = None
        self._pendingExportInfo = None
        self._exportLogBuffer = ""

        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False
        self._beginner = True
        self.screencastViewer = self.getAvailableScreencastViewer()
        self.screencast = "https://github.com/PFCCLab/PPOCRLabel"

        # Load predefined classes to the list
        self.loadPredefinedClasses(default_predefined_class_file)

        # Main widgets and related state.
        self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist)
        self.lineProofDialog = ProofreadDialog(parent=self)
        self.autoDialog = AutoDialog(parent=self)

        self.lineProofDialog.retranslate(
            {
                "title": get_str("manualProofreadDialogTitle"),
                "stage": get_str("manualProofreadStageLabel"),
                "history": get_str("manualProofreadHistoryLabel"),
                "apply": get_str("manualProofreadApplyHistory"),
                "text_placeholder": get_str("manualProofreadPlaceholder"),
                "history_empty": get_str("manualProofreadHistoryEmpty"),
            }
        )
        self._review_stage_options = ["初较", "二较", "终较"]

        self.itemsToShapes = {}
        self.shapesToItems = {}
        self.itemsToShapesbox = {}
        self.shapesToItemsbox = {}
        self.prevLabelText = get_str("tempLabel")
        self.noLabelText = get_str("nullLabel")
        self.model = "paddle"
        self.PPreader = None
        self.autoSaveNum = 5
        self.low_confidence_threshold = 0.85
        self._low_confidence_brush = QBrush(QColor("#c62828"))
        self._default_label_brush = QBrush(QColor("#000000"))
        self._ai_edit_brush = QBrush(QColor("#1565c0"))

        #  ================== File List  ==================

        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(0, 0, 0, 0)

        self.fileListWidget = QListWidget()
        self.fileListWidget.itemClicked.connect(self.fileitemDoubleClicked)
        self.fileListWidget.setIconSize(QSize(25, 25))
        filelistLayout.addWidget(self.fileListWidget)

        fileListContainer = QWidget()
        fileListContainer.setLayout(filelistLayout)
        self.fileListName = get_str("fileList")
        self.fileDock = QDockWidget(self.fileListName, self)
        self.fileDock.setObjectName(get_str("files"))
        self.fileDock.setWidget(fileListContainer)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.fileDock)

        #  ================== Key List  ==================
        if self.kie_mode:
            self.keyList = UniqueLabelQListWidget()

            # set key list height
            key_list_height = int(QApplication.desktop().height() // 4)
            if key_list_height < 50:
                key_list_height = 50
            self.keyList.setMaximumHeight(key_list_height)

            self.keyListDockName = get_str("keyListTitle")
            self.keyListDock = QDockWidget(self.keyListDockName, self)
            self.keyListDock.setWidget(self.keyList)
            self.keyListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)
            filelistLayout.addWidget(self.keyListDock)

        self.auto_recognition_num = 1

        self.AutoRecognitionNum = QSpinBox()
        self.AutoRecognitionNum.valueChanged.connect(self.autoRecognitionNum)
        self.AutoRecognitionNum.setFixedWidth(80)

        self.AutoRecognition = QToolButton()
        self.AutoRecognition.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.AutoRecognition.setIcon(newIcon("Auto"))
        autoRecLayout = QHBoxLayout()
        autoRecLayout.setContentsMargins(0, 0, 0, 0)
        autoRecLayout.addWidget(self.AutoRecognitionNum)
        autoRecLayout.addWidget(self.AutoRecognition)
        autoRecContainer = QWidget()
        autoRecContainer.setLayout(autoRecLayout)
        filelistLayout.addWidget(autoRecContainer)

        #  ================== Right Area  ==================
        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(0, 0, 0, 0)

        # Buttons
        self.editButton = QToolButton()
        self.reRecogButton = QToolButton()
        self.reRecogButton.setIcon(newIcon("reRec", 30))
        self.reRecogButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.proofreadButton = QToolButton()
        self.proofreadButton.setIcon(newIcon("done", 30))
        self.proofreadButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.manualProofButton = QToolButton()
        self.manualProofButton.setIcon(newIcon("edit", 30))
        self.manualProofButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.addLexiconButton = QToolButton()
        self.addLexiconButton.setIcon(newIcon("save", 30))
        self.addLexiconButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.tableRecButton = QToolButton()
        self.tableRecButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.newButton = QToolButton()
        self.newButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.createpolyButton = QToolButton()
        self.createpolyButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.SaveButton = QToolButton()
        self.SaveButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.DelButton = QToolButton()
        self.DelButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.ResortButton = QToolButton()
        self.ResortButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        leftTopToolBox = QGridLayout()
        leftTopToolBox.addWidget(self.newButton, 0, 0, 1, 1)
        leftTopToolBox.addWidget(self.createpolyButton, 0, 1, 1, 1)
        leftTopToolBox.addWidget(self.reRecogButton, 1, 0, 1, 1)
        leftTopToolBox.addWidget(self.proofreadButton, 1, 1, 1, 1)
        leftTopToolBox.addWidget(self.manualProofButton, 1, 2, 1, 1)
        leftTopToolBox.addWidget(self.addLexiconButton, 2, 0, 1, 1)
        leftTopToolBox.addWidget(self.tableRecButton, 2, 1, 1, 2)

        leftTopToolBoxContainer = QWidget()
        leftTopToolBoxContainer.setLayout(leftTopToolBox)
        listLayout.addWidget(leftTopToolBoxContainer)

        #  ================== Label List  ==================
        labelIndexListlBox = QHBoxLayout()

        # Create and add a widget for showing current label item index
        self.indexList = QListWidget()
        self.indexList.setMaximumSize(30, 16777215)  # limit max width
        self.indexList.setEditTriggers(QAbstractItemView.NoEditTriggers)  # no editable
        self.indexList.itemSelectionChanged.connect(self.indexSelectionChanged)
        self.indexList.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )  # no scroll Bar
        self.indexListDock = QDockWidget("No.", self)
        self.indexListDock.setWidget(self.indexList)
        self.indexListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        labelIndexListlBox.addWidget(self.indexListDock, 1)
        # no margin between two boxes
        labelIndexListlBox.setSpacing(0)

        # Create and add a widget for showing current label items
        self.labelList = EditInList()
        self.charCandidateController = CharacterCandidateController(
            self.labelList,
            lambda item: self._shape_from_label_item(item),
            candidate_loader=self._ensure_shape_candidates,
            low_threshold=self.low_confidence_threshold,
            low_color=self._low_confidence_brush.color(),
            parent=self,
        )
        self._apply_result_font_size(self.result_font_size)
        labelListContainer = QWidget()
        labelListContainer.setLayout(listLayout)
        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.clicked.connect(self.labelList.item_clicked)

        # Connect to itemChanged to detect checkbox changes.
        self.labelList.itemChanged.connect(self.labelItemChanged)
        self.labelListDockName = get_str("recognitionResult")
        self.labelListDock = QDockWidget(self.labelListDockName, self)
        self.labelListDock.setWidget(self.labelList)
        self.labelListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        labelIndexListlBox.addWidget(
            self.labelListDock, 10
        )  # label list is wider than index list

        # enable labelList drag_drop to adjust bbox order
        # Set selection mode to single selection
        self.labelList.setSelectionMode(QAbstractItemView.SingleSelection)
        # Enable drag functionality
        self.labelList.setDragEnabled(True)
        # Set to accept drops
        self.labelList.viewport().setAcceptDrops(True)
        # Show drop indicator position
        self.labelList.setDropIndicatorShown(True)
        # Set drag-drop mode to move items, if not set, default is copy items
        self.labelList.setDragDropMode(QAbstractItemView.InternalMove)
        # Trigger drop event
        self.labelList.model().rowsMoved.connect(self.drag_drop_happened)

        fontControlLayout = QHBoxLayout()
        fontControlLayout.addWidget(QLabel(get_str("resultFontSizeLabel")))
        self.resultFontSizeSpin = QSpinBox()
        self.resultFontSizeSpin.setRange(8, 48)
        self.resultFontSizeSpin.setValue(self.result_font_size)
        self.resultFontSizeSpin.valueChanged.connect(self._on_result_font_size_changed)
        fontControlLayout.addWidget(self.resultFontSizeSpin)
        fontControlLayout.addStretch(1)
        listLayout.addLayout(fontControlLayout)

        labelIndexListContainer = QWidget()
        labelIndexListContainer.setLayout(labelIndexListlBox)
        listLayout.addWidget(labelIndexListContainer)

        # Synchronize scrolling between labelList and indexList
        self.labelListBar = self.labelList.verticalScrollBar()
        self.indexListBar = self.indexList.verticalScrollBar()

        self.labelListBar.valueChanged.connect(self.move_scrollbar)
        self.indexListBar.valueChanged.connect(self.move_scrollbar)

        #  ================== Detection Box  ==================
        self.BoxList = QListWidget()

        # self.BoxList.itemActivated.connect(self.boxSelectionChanged)
        self.BoxList.itemSelectionChanged.connect(self.boxSelectionChanged)
        self.BoxList.itemDoubleClicked.connect(self.editBox)
        # Connect to itemChanged to detect checkbox changes.
        self.BoxList.itemChanged.connect(self.boxItemChanged)
        self.BoxListDockName = get_str("detectionBoxposition")
        self.BoxListDock = QDockWidget(self.BoxListDockName, self)
        self.BoxListDock.setWidget(self.BoxList)
        self.BoxListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.BoxListDock.setVisible(self.box_panel_visible)
        listLayout.addWidget(self.BoxListDock)

        #  ================== Lower Right Area  ==================
        leftbtmtoolbox = QHBoxLayout()
        leftbtmtoolbox.addWidget(self.SaveButton)
        leftbtmtoolbox.addWidget(self.DelButton)
        leftbtmtoolbox.addWidget(self.ResortButton)
        self.toggleBoxPanelButton = QToolButton()
        self.toggleBoxPanelButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggleBoxPanelButton.clicked.connect(self.toggle_box_panel_visibility)
        leftbtmtoolbox.addWidget(self.toggleBoxPanelButton)
        leftbtmtoolboxcontainer = QWidget()
        leftbtmtoolboxcontainer.setLayout(leftbtmtoolbox)
        listLayout.addWidget(leftbtmtoolboxcontainer)
        self._update_box_panel_button_text()

        self.dock = QDockWidget(get_str("boxLabelText"), self)
        self.dock.setObjectName(get_str("labels"))
        self.dock.setWidget(labelListContainer)

        #  ================== Zoom Bar  ==================
        self.imageSlider = QSlider(Qt.Horizontal)
        self.imageSlider.valueChanged.connect(self.CanvasSizeChange)
        self.imageSlider.setMinimum(-9)
        self.imageSlider.setMaximum(510)
        self.imageSlider.setSingleStep(1)
        self.imageSlider.setTickPosition(QSlider.TicksBelow)
        self.imageSlider.setTickInterval(1)

        op = QGraphicsOpacityEffect()
        op.setOpacity(0.2)
        self.imageSlider.setGraphicsEffect(op)

        self.imageSlider.setStyleSheet("background-color:transparent")
        self.imageSliderDock = QDockWidget(get_str("ImageResize"), self)
        self.imageSliderDock.setObjectName(get_str("IR"))
        self.imageSliderDock.setWidget(self.imageSlider)
        self.imageSliderDock.setFeatures(QDockWidget.DockWidgetFloatable)
        self.imageSliderDock.setAttribute(Qt.WA_TranslucentBackground)
        self.addDockWidget(Qt.RightDockWidgetArea, self.imageSliderDock)

        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)
        self.zoomWidgetValue = self.zoomWidget.value()

        self.msgBox = QMessageBox()

        #  ================== Thumbnail ==================
        hlayout = QHBoxLayout()
        m = (0, 0, 0, 0)
        hlayout.setSpacing(0)
        hlayout.setContentsMargins(*m)
        self.preButton = QToolButton()
        self.preButton.setIcon(newIcon("prev", 40))
        self.preButton.setIconSize(QSize(40, 100))
        self.preButton.clicked.connect(self.openPrevImg)
        self.preButton.setStyleSheet("border: none;")
        self.preButton.setShortcut("a")
        self.iconlist = QListWidget()
        self.iconlist.setViewMode(QListView.IconMode)
        self.iconlist.setFlow(QListView.TopToBottom)
        self.iconlist.setSpacing(10)
        self.iconlist.setIconSize(QSize(50, 50))
        self.iconlist.setMovement(QListView.Static)
        self.iconlist.setResizeMode(QListView.Adjust)
        self.iconlist.itemClicked.connect(self.iconitemDoubleClicked)
        self.iconlist.setStyleSheet(
            "QListWidget{ background-color:transparent; border: none;}"
        )
        self.iconlist.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nextButton = QToolButton()
        self.nextButton.setIcon(newIcon("next", 40))
        self.nextButton.setIconSize(QSize(40, 100))
        self.nextButton.setStyleSheet("border: none;")
        self.nextButton.clicked.connect(self.openNextImg)
        self.nextButton.setShortcut("d")

        hlayout.addWidget(self.preButton)
        hlayout.addWidget(self.iconlist)
        hlayout.addWidget(self.nextButton)

        iconListContainer = QWidget()
        iconListContainer.setLayout(hlayout)
        iconListContainer.setFixedHeight(100)

        #  ================== Canvas ==================
        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoomRequest)
        self.canvas.setDrawingShapeToSquare(settings.get(SETTING_DRAW_SQUARE, False))

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar(),
        }
        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(partial(self.newShape, False))
        self.canvas.shapeMoved.connect(self.updateBoxlist)  # self.setDirty
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        centerLayout = QVBoxLayout()
        centerLayout.setContentsMargins(0, 0, 0, 0)
        centerLayout.addWidget(scroll)
        centerLayout.addWidget(iconListContainer, 0, Qt.AlignCenter)
        centerContainer = QWidget()
        centerContainer.setLayout(centerLayout)

        self.setCentralWidget(centerContainer)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)

        self.dock.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        )
        self.fileDock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        #  ================== Actions ==================
        action = partial(newAction, self)
        quit = action(get_str("quit"), self.close, "Ctrl+Q", "quit", get_str("quitApp"))

        opendir = action(
            get_str("openDir"), self.openDirDialog, "Ctrl+u", "open", get_str("openDir")
        )

        import_pdf = action(
            get_str("importPdf"),
            self.importPdfDialog,
            "Ctrl+Shift+U",
            "file",
            get_str("importPdfDetail"),
        )

        open_dataset_dir = action(
            get_str("openDatasetDir"),
            self.openDatasetDirDialog,
            "Ctrl+p",
            "open",
            get_str("openDatasetDir"),
            enabled=False,
        )

        save = action(
            get_str("save"),
            self.saveFile,
            ["Ctrl+V", "end"],
            "verify",
            get_str("saveDetail"),
            enabled=False,
        )

        alcm = action(
            get_str("choosemodel"),
            self.autolcm,
            "Ctrl+M",
            "next",
            get_str("tipchoosemodel"),
        )

        deleteImg = action(
            get_str("deleteImg"),
            self.deleteImg,
            "Ctrl+Shift+D",
            "close",
            get_str("deleteImgDetail"),
            enabled=True,
        )

        resetAll = action(
            get_str("resetAll"),
            self.resetAll,
            None,
            "resetall",
            get_str("resetAllDetail"),
        )

        color1 = action(
            get_str("boxLineColor"),
            self.chooseColor,
            "Ctrl+L",
            "color_line",
            get_str("boxLineColorDetail"),
        )

        createMode = action(
            get_str("crtBox"),
            self.setCreateMode,
            "w",
            "new",
            get_str("crtBoxDetail"),
            enabled=False,
        )
        editMode = action(
            "&Edit\nRectBox",
            self.setEditMode,
            "Ctrl+J",
            "edit",
            "Move and edit Boxs",
            enabled=False,
        )

        create = action(
            get_str("crtBox"),
            self.createShape,
            "w",
            "objects",
            get_str("crtBoxDetail"),
            enabled=False,
        )

        delete = action(
            get_str("delBox"),
            self.deleteSelectedShape,
            ["backspace", "delete"],
            "delete",
            get_str("delBoxDetail"),
            enabled=False,
        )

        copy = action(
            get_str("dupBox"),
            self.copySelectedShape,
            "Ctrl+C",
            "copy",
            get_str("dupBoxDetail"),
            enabled=False,
        )

        hideAll = action(
            get_str("hideBox"),
            partial(self.togglePolygons, False),
            "Ctrl+H",
            "hide",
            get_str("hideAllBoxDetail"),
            enabled=False,
        )
        showAll = action(
            get_str("showBox"),
            partial(self.togglePolygons, True),
            "Ctrl+A",
            "hide",
            get_str("showAllBoxDetail"),
            enabled=False,
        )

        help = action(
            get_str("tutorial"),
            self.showTutorialDialog,
            None,
            "help",
            get_str("tutorialDetail"),
        )
        showInfo = action(
            get_str("info"), self.showInfoDialog, None, "help", get_str("info")
        )
        showSteps = action(
            get_str("steps"), self.showStepsDialog, None, "help", get_str("steps")
        )
        showKeys = action(
            get_str("keys"), self.showKeysDialog, None, "help", get_str("keys")
        )

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            "Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas."
            % (fmtShortcut("Ctrl+[-+]"), fmtShortcut("Ctrl+Wheel"))
        )
        self.zoomWidget.setEnabled(False)

        zoomIn = action(
            get_str("zoomin"),
            partial(self.addZoom, 10),
            "Ctrl++",
            "zoom-in",
            get_str("zoominDetail"),
            enabled=False,
        )
        zoomOut = action(
            get_str("zoomout"),
            partial(self.addZoom, -10),
            "Ctrl+-",
            "zoom-out",
            get_str("zoomoutDetail"),
            enabled=False,
        )
        zoomOrg = action(
            get_str("originalsize"),
            partial(self.setZoom, 100),
            "Ctrl+=",
            "zoom",
            get_str("originalsizeDetail"),
            enabled=False,
        )
        fitWindow = action(
            get_str("fitWin"),
            self.setFitWindow,
            "Ctrl+F",
            "fit-window",
            get_str("fitWinDetail"),
            checkable=True,
            enabled=False,
        )
        fitWidth = action(
            get_str("fitWidth"),
            self.setFitWidth,
            "Ctrl+Shift+F",
            "fit-width",
            get_str("fitWidthDetail"),
            checkable=True,
            enabled=False,
        )
        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut, zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        #  ================== New Actions ==================

        edit = action(
            get_str("editLabel"),
            self.editLabel,
            "Ctrl+E",
            "edit",
            get_str("editLabelDetail"),
            enabled=False,
        )

        AutoRec = action(
            get_str("autoRecognition"),
            self.autoRecognition,
            "",
            "Auto",
            get_str("autoRecognition"),
            enabled=False,
        )
        AutoRecCurrent = action(
            get_str("autoRecognitionCurrent"),
            self.autoRecognitionCurrent,
            "",
            "Auto",
            get_str("autoRecognitionCurrentDetail"),
            enabled=False,
        )
        trainAction = action(
            get_str("startTraining"),
            self.launchPaddleTraining,
            "",
            "next",
            get_str("startTrainingDetail"),
        )
        customModelAction = action(
            get_str("customModelAction"),
            self.chooseCustomModels,
            "",
            "next",
            get_str("customModelActionDetail"),
        )

        reRec = action(
            get_str("reRecognition"),
            self.reRecognition,
            "Ctrl+Shift+R",
            "reRec",
            get_str("reRecognition"),
            enabled=False,
        )

        autoProofread = action(
            get_str("autoProofread"),
            self.autoProofread,
            "",
            "done",
            get_str("autoProofreadDetail"),
            enabled=False,
        )

        manualProofread = action(
            get_str("manualProofread"),
            self.openManualProofreadDialog,
            "Ctrl+Alt+P",
            "edit",
            get_str("manualProofreadDetail"),
            enabled=False,
        )

        addToLexicon = action(
            get_str("addToLexicon"),
            self.addSelectedToLexicon,
            "",
            "save",
            get_str("addToLexiconDetail"),
            enabled=False,
        )

        addPageToLexicon = action(
            get_str("addPageToLexicon"),
            self.addPageToLexicon,
            "",
            "save",
            get_str("addPageToLexiconDetail"),
            enabled=False,
        )

        singleRere = action(
            get_str("singleRe"),
            self.singleRerecognition,
            "Ctrl+R",
            "reRec",
            get_str("singleRe"),
            enabled=False,
        )

        createpoly = action(
            get_str("creatPolygon"),
            self.createPolygon,
            ["q", "home"],
            "new",
            get_str("creatPolygon"),
            enabled=False,
        )

        tableRec = action(
            get_str("TableRecognition"),
            self.TableRecognition,
            "",
            "Auto",
            get_str("TableRecognition"),
            enabled=False,
        )

        cellreRec = action(
            get_str("cellreRecognition"),
            self.cellreRecognition,
            "",
            "reRec",
            get_str("cellreRecognition"),
            enabled=False,
        )

        saveRec = action(
            get_str("saveRec"),
            self.saveRecResult,
            "",
            "save",
            get_str("saveRec"),
            enabled=False,
        )
        exportFullText = action(
            get_str("exportFullText"),
            self.exportFullText,
            "",
            "save",
            get_str("exportFullTextDetail"),
            enabled=False,
        )

        saveLabel = action(
            get_str("saveLabel"),
            self.saveLabelFile,  #
            "Ctrl+S",
            "save",
            get_str("saveLabel"),
            enabled=False,
        )

        exportJSON = action(
            get_str("exportJSON"),
            self.exportJSON,
            "",
            "save",
            get_str("exportJSON"),
            enabled=False,
        )

        undoLastPoint = action(
            get_str("undoLastPoint"),
            self.canvas.undoLastPoint,
            "Ctrl+Z",
            "undo",
            get_str("undoLastPoint"),
            enabled=False,
        )

        rotateLeft = action(
            get_str("rotateLeft"),
            partial(self.rotateImgAction, 1),
            "Ctrl+Alt+L",
            "rotateLeft",
            get_str("rotateLeft"),
            enabled=False,
        )

        rotateRight = action(
            get_str("rotateRight"),
            partial(self.rotateImgAction, -1),
            "Ctrl+Alt+R",
            "rotateRight",
            get_str("rotateRight"),
            enabled=False,
        )

        undo = action(
            get_str("undo"),
            self.undoShapeEdit,
            "Ctrl+Z",
            "undo",
            get_str("undo"),
            enabled=False,
        )

        change_cls = action(
            get_str("keyChange"),
            self.change_box_key,
            "Ctrl+X",
            "edit",
            get_str("keyChange"),
            enabled=False,
        )

        lock = action(
            get_str("lockBox"),
            self.lockSelectedShape,
            None,
            "lock",
            get_str("lockBoxDetail"),
            enabled=False,
        )
        expand = action(
            get_str("expandBox"),
            self.expandSelectedShape,
            "Ctrl+K",
            "expand",
            get_str("expandBoxDetail"),
            enabled=False,
        )
        resort = action(
            get_str("resortposition"),
            self.resortBoxPosition,
            "Ctrl+B",
            "resort",
            get_str("resortpositiondetail"),
            enabled=True,
        )

        self.editButton.setDefaultAction(edit)
        self.newButton.setDefaultAction(create)
        self.createpolyButton.setDefaultAction(createpoly)
        self.DelButton.setDefaultAction(deleteImg)
        self.SaveButton.setDefaultAction(save)
        self.AutoRecognition.setDefaultAction(AutoRec)
        self.autoRecognitionMenu = QMenu(self)
        self.autoRecognitionMenu.addAction(AutoRecCurrent)
        self.AutoRecognition.setMenu(self.autoRecognitionMenu)
        self.AutoRecognition.setPopupMode(QToolButton.MenuButtonPopup)
        self.reRecogButton.setDefaultAction(reRec)
        self.proofreadButton.setDefaultAction(autoProofread)
        self.manualProofButton.setDefaultAction(manualProofread)
        self.addLexiconButton.setDefaultAction(addToLexicon)
        self.tableRecButton.setDefaultAction(tableRec)
        self.ResortButton.setDefaultAction(resort)
        # self.preButton.setDefaultAction(openPrevImg)
        # self.nextButton.setDefaultAction(openNextImg)

        #  ================== Zoom layout ==================
        zoomLayout = QHBoxLayout()
        zoomLayout.addStretch()
        self.zoominButton = QToolButton()
        self.zoominButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoominButton.setDefaultAction(zoomIn)
        self.zoomoutButton = QToolButton()
        self.zoomoutButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoomoutButton.setDefaultAction(zoomOut)
        self.zoomorgButton = QToolButton()
        self.zoomorgButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoomorgButton.setDefaultAction(zoomOrg)
        zoomLayout.addWidget(self.zoominButton)
        zoomLayout.addWidget(self.zoomorgButton)
        zoomLayout.addWidget(self.zoomoutButton)

        zoomContainer = QWidget()
        zoomContainer.setLayout(zoomLayout)
        zoomContainer.setGeometry(0, 0, 30, 150)

        shapeLineColor = action(
            get_str("shapeLineColor"),
            self.chshapeLineColor,
            icon="color_line",
            tip=get_str("shapeLineColorDetail"),
            enabled=False,
        )
        shapeFillColor = action(
            get_str("shapeFillColor"),
            self.chshapeFillColor,
            icon="color",
            tip=get_str("shapeFillColorDetail"),
            enabled=False,
        )

        # Label list context menu.
        labelMenu = QMenu()
        addActions(labelMenu, (edit, delete))

        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(self.popLabelListMenu)

        # Draw squares/rectangles
        self.drawSquaresOption = QAction(get_str("drawSquares"), self)
        self.drawSquaresOption.setCheckable(True)
        self.drawSquaresOption.setChecked(settings.get(SETTING_DRAW_SQUARE, False))
        self.drawSquaresOption.triggered.connect(self.toogleDrawSquare)

        layout_horizontal = action(
            get_str("textLayoutHorizontal"),
            lambda: self.changeTextLayoutMode("horizontal"),
            tip=get_str("textLayoutHorizontalDetail"),
            checkable=True,
        )
        layout_vertical = action(
            get_str("textLayoutVertical"),
            lambda: self.changeTextLayoutMode("vertical"),
            tip=get_str("textLayoutVerticalDetail"),
            checkable=True,
        )
        self.layoutActionGroup = QActionGroup(self)
        self.layoutActionGroup.setExclusive(True)
        self.layoutActionGroup.addAction(layout_horizontal)
        self.layoutActionGroup.addAction(layout_vertical)
        layout_horizontal.setChecked(not self.use_vertical_text)
        layout_vertical.setChecked(self.use_vertical_text)
        self.textLayoutMenu = QMenu(get_str("textLayoutMenu"), self)
        self.textLayoutMenu.addAction(layout_horizontal)
        self.textLayoutMenu.addAction(layout_vertical)
        self.textLayoutMenu.setStatusTip(get_str("textLayoutMenuDetail"))
        reading_horizontal = action(
            get_str("readingOrderHorizontal"),
            lambda: self.changeReadingOrder("horizontal"),
            checkable=True,
        )
        reading_vertical = action(
            get_str("readingOrderVertical"),
            lambda: self.changeReadingOrder("vertical"),
            checkable=True,
        )
        self.readingModeActionGroup = QActionGroup(self)
        self.readingModeActionGroup.setExclusive(True)
        self.readingModeActionGroup.addAction(reading_horizontal)
        self.readingModeActionGroup.addAction(reading_vertical)
        if self.reading_mode == "vertical":
            reading_vertical.setChecked(True)
        else:
            reading_horizontal.setChecked(True)
        self.readingModeMenu = QMenu(get_str("readingOrder"), self)
        self.readingModeMenu.addAction(reading_horizontal)
        self.readingModeMenu.addAction(reading_vertical)
        self.readingModeActions = {
            "horizontal": reading_horizontal,
            "vertical": reading_vertical,
        }

        # Store actions for further handling.
        self.actions = struct(
            save=save,
            resetAll=resetAll,
            deleteImg=deleteImg,
            lineColor=color1,
            create=create,
            createpoly=createpoly,
            tableRec=tableRec,
            delete=delete,
            edit=edit,
            copy=copy,
            saveRec=saveRec,
            exportFullText=exportFullText,
            singleRere=singleRere,
            autoProofread=autoProofread,
            manualProofread=manualProofread,
            addToLexicon=addToLexicon,
            addPageToLexicon=addPageToLexicon,
            AutoRec=AutoRec,
            AutoRecCurrent=AutoRecCurrent,
            reRec=reRec,
            cellreRec=cellreRec,
            train=trainAction,
            customModel=customModelAction,
            createMode=createMode,
            editMode=editMode,
            shapeLineColor=shapeLineColor,
            shapeFillColor=shapeFillColor,
            zoom=zoom,
            zoomIn=zoomIn,
            zoomOut=zoomOut,
            zoomOrg=zoomOrg,
            fitWindow=fitWindow,
            fitWidth=fitWidth,
            zoomActions=zoomActions,
            saveLabel=saveLabel,
            change_cls=change_cls,
            undo=undo,
            undoLastPoint=undoLastPoint,
            open_dataset_dir=open_dataset_dir,
            importPdf=import_pdf,
            rotateLeft=rotateLeft,
            rotateRight=rotateRight,
            lock=lock,
            exportJSON=exportJSON,
            expand=expand,
            resort=resort,
            fileMenuActions=(
                opendir,
                import_pdf,
                open_dataset_dir,
                saveLabel,
                exportJSON,
                resetAll,
                quit,
            ),
            beginner=(),
            advanced=(),
            editMenu=(
                createpoly,
                edit,
                copy,
                delete,
                singleRere,
                cellreRec,
                resort,
                None,
                undo,
                undoLastPoint,
                None,
                rotateLeft,
                rotateRight,
                None,
                color1,
                self.drawSquaresOption,
                lock,
                expand,
                None,
                change_cls,
            ),
            beginnerContext=(
                create,
                createpoly,
                edit,
                copy,
                delete,
                singleRere,
                cellreRec,
                rotateLeft,
                rotateRight,
                lock,
                expand,
                change_cls,
            ),
            advancedContext=(
                createMode,
                editMode,
                edit,
                copy,
                delete,
                shapeLineColor,
                shapeFillColor,
            ),
            onLoadActive=(create, createpoly, createMode, editMode),
            onShapesPresent=(hideAll, showAll),
        )

        # menus
        self.menus = struct(
            file=self.menu("&" + get_str("mfile")),
            edit=self.menu("&" + get_str("medit")),
            view=self.menu("&" + get_str("mview")),
            autolabel=self.menu("&PaddleOCR"),
            help=self.menu("&" + get_str("mhelp")),
            recentFiles=QMenu("Open &Recent"),
            labelList=labelMenu,
        )

        self.lastLabel = None
        # Add option to enable/disable labels being displayed at the top of bounding boxes
        self.displayLabelOption = QAction(get_str("displayLabel"), self)
        self.displayLabelOption.setShortcut("Ctrl+Shift+P")
        self.displayLabelOption.setCheckable(True)
        self.displayLabelOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.displayLabelOption.triggered.connect(self.togglePaintLabelsOption)

        # Add option to enable/disable box index being displayed at the top of bounding boxes
        self.displayIndexOption = QAction(get_str("displayIndex"), self)
        self.displayIndexOption.setCheckable(True)
        self.displayIndexOption.setChecked(settings.get(SETTING_PAINT_INDEX, False))
        self.displayIndexOption.triggered.connect(self.togglePaintIndexOption)

        self.labelDialogOption = QAction(get_str("labelDialogOption"), self)
        self.labelDialogOption.setShortcut("Ctrl+Shift+L")
        self.labelDialogOption.setCheckable(True)
        self.labelDialogOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.displayIndexOption.setChecked(settings.get(SETTING_PAINT_INDEX, False))
        self.labelDialogOption.triggered.connect(self.speedChoose)

        self.autoSaveOption = QAction(get_str("autoSaveMode"), self)
        self.autoSaveOption.setCheckable(True)
        self.autoSaveOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.displayIndexOption.setChecked(settings.get(SETTING_PAINT_INDEX, False))
        self.autoSaveOption.triggered.connect(self.autoSaveFunc)

        self.autoReRecognitionOption = QAction(get_str("autoReRecognition"), self)
        self.autoReRecognitionOption.setCheckable(True)
        self.autoReRecognitionOption.setChecked(
            settings.get(SETTING_PAINT_LABEL, False)
        )
        self.displayIndexOption.setChecked(settings.get(SETTING_PAINT_INDEX, False))
        self.autoReRecognitionOption.triggered.connect(self.autoSaveFunc)

        self.autoSaveUnsavedChangesOption = QAction(
            get_str("autoSaveUnsavedChanges"), self
        )
        self.autoSaveUnsavedChangesOption.setCheckable(True)
        self.autoSaveUnsavedChangesOption.setChecked(
            settings.get(SETTING_PAINT_LABEL, False)
        )
        self.displayIndexOption.setChecked(settings.get(SETTING_PAINT_INDEX, False))
        self.autoSaveUnsavedChangesOption.triggered.connect(self.autoSaveFunc)

        addActions(
            self.menus.file,
            (
                opendir,
                import_pdf,
                open_dataset_dir,
                None,
                saveLabel,
                saveRec,
                exportFullText,
                exportJSON,
                self.autoSaveOption,
                self.autoReRecognitionOption,
                self.autoSaveUnsavedChangesOption,
                None,
                resetAll,
                deleteImg,
                quit,
            ),
        )

        addActions(self.menus.help, (showKeys, showSteps, showInfo))
        addActions(
            self.menus.view,
            (
                self.displayLabelOption,
                self.displayIndexOption,
                self.labelDialogOption,
                None,
                hideAll,
                showAll,
                None,
                zoomIn,
                zoomOut,
                zoomOrg,
                None,
                fitWindow,
                fitWidth,
            ),
        )

        addActions(
            self.menus.autolabel,
            (
                 AutoRec,
                 AutoRecCurrent,
                 reRec,
                 autoProofread,
                 manualProofread,
                 addToLexicon,
                 addPageToLexicon,
                 cellreRec,
                trainAction,
                customModelAction,
                self.readingModeMenu,
                self.textLayoutMenu,
                alcm,
                None,
                help,
            ),
        )

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)

        self.statusBar().showMessage("%s started." % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filePath = default_filename
        self.lastOpenDir = None
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        # Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(SETTING_RECENT_FILES)
                self.recentFiles = [i for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(
                    SETTING_RECENT_FILES
                )

        size = settings.get(SETTING_WIN_SIZE, QSize(1200, 800))

        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)
        self.move(position)
        saveDir = settings.get(SETTING_SAVE_DIR, None)
        logger.debug("Save directory: %s", saveDir)
        self.lastOpenDir = settings.get(SETTING_LAST_OPEN_DIR, None)

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.lineColor = QColor(
            settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR)
        )
        Shape.fill_color = self.fillColor = QColor(
            settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR)
        )
        self.canvas.setDrawingColor(self.lineColor)
        # Add chris
        Shape.difficult = self.difficult

        # ADD:
        # Populate the File menu dynamically.
        self.updateFileMenu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.filePath and os.path.isdir(self.filePath):
            self.queueEvent(partial(self.importDirImages, self.filePath or ""))
        elif self.filePath:
            self.queueEvent(partial(self.loadFile, self.filePath or ""))

        self.keyDialog = None

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # Display cursor coordinates at the right of status bar
        self.labelCoordinates = QLabel("")
        self.statusBar().addPermanentWidget(self.labelCoordinates)

        # Open Dir if deafult file
        if self.filePath and os.path.isdir(self.filePath):
            self.openDirDialog(dirpath=self.filePath, silent=True)

        # load label font
        self.label_font_family = None
        if label_font_path is not None:
            label_font_id = QFontDatabase.addApplicationFont(label_font_path)
            if label_font_id >= 0:
                self.label_font_family = QFontDatabase.applicationFontFamilies(
                    label_font_id
                )[0]

        # selected shape color
        self.selected_shape_color = selected_shape_color

    def _paddleocr_params(self, lang=None):
        params = {
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": self.use_vertical_text,
            "device": self.gpu,
            "lang": lang or self.lang,
            "enable_mkldnn": False,
        }
        det_name = self._infer_model_name(
            self.det_model_dir, default_name="PP-OCRv5_mobile_det"
        )
        rec_name = self._infer_model_name(
            self.rec_model_dir, default_name="PP-OCRv5_mobile_rec"
        )
        params["text_detection_model_name"] = det_name
        params["text_recognition_model_name"] = rec_name
        if self.det_model_dir:
            params["text_detection_model_dir"] = self.det_model_dir
        if self.rec_model_dir:
            params["text_recognition_model_dir"] = self.rec_model_dir
        if self.cls_model_dir is not None:
            params["text_line_orientation_model_dir"] = self.cls_model_dir
        return params

    def _build_table_ocr(self, lang=None):
        kwargs = dict(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_seal_recognition=False,
            use_table_recognition=True,
            use_formula_recognition=False,
            use_chart_recognition=False,
            use_region_detection=False,
            use_textline_orientation=self.use_vertical_text,
            device=self.gpu,
            lang=lang or self.lang,
        )
        if self.cls_model_dir is not None:
            kwargs["textline_orientation_model_dir"] = self.cls_model_dir
        return PPStructureV3(**kwargs)

    def _reload_ocr_backends(self, lang=None):
        if lang is not None:
            self.lang = lang
        self.ocr = PaddleOCR(**self._paddleocr_params(lang=lang))
        self.table_ocr = self._build_table_ocr(lang=lang)

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.canvas.setDrawingShapeToSquare(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            # Draw rectangle if Ctrl is pressed
            self.canvas.setDrawingShapeToSquare(True)

    def noShapes(self):
        return not self.itemsToShapes

    def populateModeActions(self):
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        self.menus.edit.clear()
        actions = (
            self.actions.create,
        )  # if self.beginner() else (self.actions.createMode, self.actions.editMode)
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def setDirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)
        self.actions.createpoly.setEnabled(True)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        self.itemsToShapesbox.clear()  # ADD
        self.shapesToItemsbox.clear()
        self.labelList.clear()
        self.BoxList.clear()
        self.indexList.clear()
        self.filePath = None
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()
        self.labelCoordinates.clear()
        # self.comboBox.cb.clear()
        self.result_dic = []

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def _get_single_active_shape(self):
        if len(self.canvas.selectedShapes) == 1:
            return self.canvas.selectedShapes[0]
        current_item = self.currentItem()
        if current_item:
            return self._shape_from_label_item(current_item)
        return None

    def _shape_from_label_item(self, item):
        """
        Resolve the canvas shape associated with a label list item.

        Some PyQt builds emit brand-new QListWidgetItem wrappers during
        selection/edit events, which are not hashable and therefore cannot be
        used as dictionary keys. We rely on the stored Qt.UserRole payload first,
        then fall back to locating the item by row if needed.
        """
        if item is None:
            return None
        try:
            return self.itemsToShapes[item]
        except TypeError:
            pass
        except KeyError:
            pass

        shape = item.data(Qt.UserRole) if hasattr(item, "data") else None
        if shape is not None:
            return shape

        if hasattr(self, "labelList"):
            index = self.labelList.indexFromItem(item).row()
            if 0 <= index < len(self.canvas.shapes):
                return self.canvas.shapes[index]
        return None

    def currentBox(self):
        items = self.BoxList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def getAvailableScreencastViewer(self):
        osName = platform.system()

        if osName == "Windows":
            return ["C:\\Program Files\\Internet Explorer\\iexplore.exe"]
        elif osName == "Linux":
            return ["xdg-open"]
        elif osName == "Darwin":
            return ["open"]
        return [None]

    ## Callbacks ##
    def showTutorialDialog(self):
        subprocess.Popen(self.screencastViewer + [self.screencast])

    def showInfoDialog(self):
        from libs.__init__ import __version__

        msg = "Name:{0} \nApp Version:{1} \n{2} ".format(
            __appname__, __version__, sys.version_info
        )
        QMessageBox.information(self, "Information", msg)

    def showStepsDialog(self):
        msg = stepsInfo(self.lang)
        QMessageBox.information(self, "Information", msg)

    def showKeysDialog(self):
        msg = keysInfo(self.lang)
        QMessageBox.information(self, "Information", msg)

    def createShape(self):
        assert self.beginner()
        self.canvas.setEditing(False)
        self.actions.create.setEnabled(False)
        self.actions.createpoly.setEnabled(False)
        self.canvas.fourpoint = False

    def createPolygon(self):
        assert self.beginner()
        self.canvas.setEditing(False)
        self.canvas.fourpoint = True
        self.actions.create.setEnabled(False)
        self.actions.createpoly.setEnabled(False)
        self.actions.undoLastPoint.setEnabled(True)

    def rotateImg(self, filename, k, _value):
        self.actions.rotateRight.setEnabled(_value)
        pix = cv2.imdecode(np.fromfile(filename, dtype=np.uint8), cv2.IMREAD_COLOR)
        pix = np.rot90(pix, k)
        ext = os.path.splitext(filename)[1]
        cv2.imencode(ext, pix)[1].tofile(filename)
        self.canvas.update()

        # Remove confirmation status after rotation
        img_idx = self.getImglabelidx(filename)
        if img_idx in self.fileStatedict:
            self.fileStatedict.pop(img_idx)

        # Remove the "done" icon from the file list
        if filename in self.mImgList:
            currIndex = self.mImgList.index(filename)
            item = self.fileListWidget.item(currIndex)
            if item:
                item.setIcon(QIcon())
                item.setIcon(newIcon("close"))

        self.loadFile(filename)

    def rotateImgWarn(self):
        if self.lang == "ch":
            self.msgBox.warning(
                self,
                "提示",
                "\n 该图片已经有标注框,旋转操作会打乱标注,建议清除标注框后旋转。",
            )
        else:
            self.msgBox.warning(
                self,
                "Warn",
                "\n The picture already has a label box, "
                "and rotation will disrupt the label. "
                "It is recommended to clear the label box and rotate it.",
            )

    def rotateImgAction(self, k=1, _value=False):
        filename = self.filePath

        if os.path.exists(filename):
            if self.itemsToShapesbox:
                self.rotateImgWarn()
            else:
                self.saveFile()
                self.dirty = False
                self.rotateImg(filename=filename, k=k, _value=True)
        else:
            self.rotateImgWarn()
            self.actions.rotateRight.setEnabled(False)
            self.actions.rotateLeft.setEnabled(False)

    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            logger.debug("Cancel creation.")
            self.canvas.setEditing(True)
            self.canvas.restoreCursor()
            self.actions.create.setEnabled(True)
            self.actions.createpoly.setEnabled(True)

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def setCreateMode(self):
        assert self.advanced()
        self.toggleDrawMode(False)

    def setEditMode(self):
        assert self.advanced()
        self.toggleDrawMode(True)
        self.labelSelectionChanged()

    def updateFileMenu(self):
        currFilePath = self.filePath

        def exists(filename):
            return os.path.exists(filename)

        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f != currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon("labels")
            action = QAction(icon, "&%d %s" % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def editLabel(self):
        if not self.canvas.editing():
            return
        item = self.currentItem()
        if not item:
            return
        text = self.labelDialog.popUp(item.text())
        if text is not None:
            item.setText(text)
            # item.setBackground(generateColorByText(text))
            self.setDirty()
            self.updateComboBox()

    # =================== detection box related functions ===================
    def boxItemChanged(self, item):
        shape = self.itemsToShapesbox[item]

        box = ast.literal_eval(item.text())
        # print('shape in labelItemChanged is',shape.points)
        if box != [(int(p.x()), int(p.y())) for p in shape.points]:
            # shape.points = box
            shape.points = [QPointF(p[0], p[1]) for p in box]

            # QPointF(x,y)
            # shape.line_color = generateColorByText(shape.label)
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, True)  # item.checkState() == Qt.Checked

    def editBox(self):  # ADD
        if not self.canvas.editing():
            return
        item = self.currentBox()
        if not item:
            return
        text = self.labelDialog.popUp(item.text())

        width, height = self.image.width(), self.image.height()
        if text:
            try:
                text_list = eval(text)
            except Exception:
                msg_box = QMessageBox(
                    QMessageBox.Warning, "Warning", "Please enter the correct format"
                )
                msg_box.exec_()
                return
            if len(text_list) < 4:
                msg_box = QMessageBox(
                    QMessageBox.Warning,
                    "Warning",
                    "Please enter the coordinates of 4 points",
                )
                msg_box.exec_()
                return
            for box in text_list:
                if box[0] > width or box[0] < 0 or box[1] > height or box[1] < 0:
                    msg_box = QMessageBox(
                        QMessageBox.Warning, "Warning", "Out of picture size"
                    )
                    msg_box.exec_()
                    return

            item.setText(text)
            # item.setBackground(generateColorByText(text))
            self.setDirty()
            self.updateComboBox()

    def updateBoxlist(self):
        self.canvas.selectedShapes_hShape = []
        if self.canvas.hShape is not None:
            self.canvas.selectedShapes_hShape = self.canvas.selectedShapes + [
                self.canvas.hShape
            ]
        else:
            self.canvas.selectedShapes_hShape = self.canvas.selectedShapes
        for shape in self.canvas.selectedShapes_hShape:
            if shape in self.shapesToItemsbox.keys():
                item = self.shapesToItemsbox[shape]  # listitem
                text = [(int(p.x()), int(p.y())) for p in shape.points]
                item.setText(str(text))
        self.actions.undo.setEnabled(True)
        self.setDirty()

    def indexTo5Files(self, currIndex):
        if currIndex < 2:
            return self.mImgList[:5]
        elif currIndex > len(self.mImgList) - 3:
            return self.mImgList[-5:]
        else:
            return self.mImgList[currIndex - 2 : currIndex + 3]

    # Tzutalin 20160906 : Add file list and dock to move faster
    def fileitemDoubleClicked(self, item=None):
        self.currIndex = self.mImgList.index(
            os.path.join(os.path.abspath(self.dirname), item.text())
        )
        filename = self.mImgList[self.currIndex]
        if filename:
            self.mImgList5 = self.indexTo5Files(self.currIndex)
            # self.additems5(None)
            self.loadFile(filename)

    def iconitemDoubleClicked(self, item=None):
        self.currIndex = self.mImgList.index(os.path.join(item.toolTip()))
        filename = self.mImgList[self.currIndex]
        if filename:
            self.mImgList5 = self.indexTo5Files(self.currIndex)
            # self.additems5(None)
            self.loadFile(filename)

    def CanvasSizeChange(self):
        if len(self.mImgList) > 0 and self.imageSlider.hasFocus():
            self.zoomWidget.setValue(self.imageSlider.value())

    def shapeSelectionChanged(self, selected_shapes):
        self._noSelectionSlot = True
        for shape in self.canvas.selectedShapes:
            shape.selected = False
        self.labelList.clearSelection()
        self.indexList.clearSelection()
        self.canvas.selectedShapes = selected_shapes
        for shape in self.canvas.selectedShapes:
            shape.selected = True
            self.shapesToItems[shape].setSelected(True)
            self.shapesToItemsbox[shape].setSelected(True)
            index = self.labelList.indexFromItem(self.shapesToItems[shape]).row()
            self.indexList.item(index).setSelected(True)

        self.labelList.scrollToItem(
            self.currentItem()
        )  # QAbstractItemView.EnsureVisible
        # map current label item to index item and select it
        index = self.labelList.indexFromItem(self.currentItem()).row()
        self.indexList.scrollToItem(self.indexList.item(index))
        self.BoxList.scrollToItem(self.currentBox())

        if self.kie_mode:
            if len(self.canvas.selectedShapes) == 1 and self.keyList.count() > 0:
                selected_key_item_row = self.keyList.findItemsByLabel(
                    self.canvas.selectedShapes[0].key_cls, get_row=True
                )
                if (
                    isinstance(selected_key_item_row, list)
                    and len(selected_key_item_row) == 0
                ):
                    key_text = self.canvas.selectedShapes[0].key_cls
                    item = self.keyList.createItemFromLabel(key_text)
                    self.keyList.addItem(item)
                    rgb = self._get_rgb_by_label(key_text, self.kie_mode)
                    self.keyList.setItemLabel(item, key_text, rgb)
                    selected_key_item_row = self.keyList.findItemsByLabel(
                        self.canvas.selectedShapes[0].key_cls, get_row=True
                    )

                self.keyList.setCurrentRow(selected_key_item_row)

        self._noSelectionSlot = False
        n_selected = len(selected_shapes)
        self.actions.singleRere.setEnabled(n_selected)
        self.actions.cellreRec.setEnabled(n_selected)
        self.actions.delete.setEnabled(n_selected)
        self.actions.copy.setEnabled(n_selected)
        self.actions.edit.setEnabled(n_selected == 1)
        self.actions.manualProofread.setEnabled(n_selected == 1)
        self.actions.lock.setEnabled(n_selected)
        self.actions.change_cls.setEnabled(n_selected)
        self.actions.expand.setEnabled(n_selected)

    def addLabel(self, shape):
        shape.paintLabel = self.displayLabelOption.isChecked()
        shape.paintIdx = self.displayIndexOption.isChecked()

        item = HashableQListWidgetItem(shape.label)
        item.setData(Qt.UserRole, shape)
        # current difficult checkbox is disable
        # item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        # item.setCheckState(Qt.Unchecked) if shape.difficult else item.setCheckState(Qt.Checked)

        # Checked means difficult is False
        # item.setBackground(generateColorByText(shape.label))
        self.itemsToShapes[item] = shape
        self.shapesToItems[shape] = item
        # add current label item index before label string
        current_index = QListWidgetItem(str(self.labelList.count()))
        current_index.setTextAlignment(Qt.AlignHCenter)
        self.indexList.addItem(current_index)
        self.labelList.addItem(item)
        self._update_label_item_style(shape)
        # print('item in add label is ',[(p.x(), p.y()) for p in shape.points], shape.label)

        # ADD for box
        item = HashableQListWidgetItem(
            str([(int(p.x()), int(p.y())) for p in shape.points])
        )
        item.setData(Qt.UserRole, shape)
        self.itemsToShapesbox[item] = shape
        self.shapesToItemsbox[shape] = item
        self.BoxList.addItem(item)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)
        self.updateComboBox()

        # update show counting
        self.BoxListDock.setWindowTitle(
            self.BoxListDockName + f" ({self.BoxList.count()})"
        )
        self.labelListDock.setWindowTitle(
            self.labelListDockName + f" ({self.labelList.count()})"
        )

    def remLabels(self, shapes):
        if shapes is None:
            # print('rm empty label')
            return
        for shape in shapes:
            key = self._candidate_key_from_shape(shape)
            self._candidate_cache.pop(key, None)
            self._score_cache.pop(key, None)
            item = self.shapesToItems[shape]
            self.labelList.takeItem(self.labelList.row(item))
            del self.shapesToItems[shape]
            del self.itemsToShapes[item]
            self.updateComboBox()

            # ADD:
            item = self.shapesToItemsbox[shape]
            self.BoxList.takeItem(self.BoxList.row(item))
            del self.shapesToItemsbox[shape]
            del self.itemsToShapesbox[item]
            self.updateComboBox()
        self.updateIndexList()

    def loadLabels(self, shapes):
        s = []
        shape_index = 0
        for entry in shapes:
            if len(entry) >= 6:
                label, points, line_color, key_cls, difficult, extras = entry[:6]
            else:
                label, points, line_color, key_cls, difficult = entry
                extras = {}
            shape = Shape(
                label=label,
                line_color=line_color,
                key_cls=key_cls,
                font_family=self.label_font_family,
            )
            for x, y in points:
                # Ensure the labels are within the bounds of the image. If not, fix them.
                x, y, snapped = self.canvas.snapPointToCanvas(x, y)
                if snapped:
                    self.setDirty()

                shape.addPoint(QPointF(x, y))
            shape.difficult = difficult
            shape.idx = shape_index
            shape_index += 1
            extras = extras or {}
            history = extras.get("history")
            if history:
                shape.history = copy.deepcopy(history)
                for entry in history:
                    stage_name = entry.get("stage")
                    if stage_name:
                        self._remember_stage(stage_name)
            instance_id = extras.get("instance_id")
            if instance_id:
                shape.instance_id = instance_id
            # shape.locked = False
            shape.close()
            s.append(shape)

            self._restore_shape_candidates(shape)
            self._update_shape_color(shape)
            self.addLabel(shape)

        self.updateComboBox()
        self.canvas.loadShapes(s)

    def singleLabel(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapesToItems[shape]
        item.setText(shape.label)
        self._update_label_item_style(shape)
        self.updateComboBox()

        # ADD:
        item = self.shapesToItemsbox[shape]
        item.setText(str([(int(p.x()), int(p.y())) for p in shape.points]))
        self.updateComboBox()

    def updateComboBox(self):
        # Get the unique labels and add them to the Combobox.
        itemsTextList = [
            str(self.labelList.item(i).text()) for i in range(self.labelList.count())
        ]

        uniqueTextList = list(set(itemsTextList))
        # Add a null row for showing all the labels
        uniqueTextList.append("")
        uniqueTextList.sort()

        # self.comboBox.update_items(uniqueTextList)

    def updateIndexList(self):
        self.indexList.clear()
        for i in range(self.labelList.count()):
            string = QListWidgetItem(str(i))
            string.setTextAlignment(Qt.AlignHCenter)
            self.indexList.addItem(string)

    def _candidate_key_from_box(self, box_points):
        return tuple((int(pt[0]), int(pt[1])) for pt in box_points)

    def _candidate_key_from_shape(self, shape):
        return tuple((int(p.x()), int(p.y())) for p in shape.points)

    def _store_shape_candidates(self, shape, box, candidates):
        key = self._candidate_key_from_box(box)
        if candidates:
            self._candidate_cache[key] = copy.deepcopy(candidates)
        else:
            self._candidate_cache.pop(key, None)

    def _restore_shape_candidates(self, shape):
        key = self._candidate_key_from_shape(shape)
        cached = self._candidate_cache.get(key)
        if cached:
            shape.char_candidates = copy.deepcopy(cached)
        else:
            shape.char_candidates = getattr(shape, "char_candidates", [])
        self._restore_shape_confidence(shape)

    def _store_shape_confidence(self, shape, box):
        score = float(getattr(shape, "rec_score", 1.0) or 0.0)
        key = self._candidate_key_from_box(box)
        self._score_cache[key] = score

    def _restore_shape_confidence(self, shape):
        key = self._candidate_key_from_shape(shape)
        if key in self._score_cache:
            shape.rec_score = self._score_cache[key]

    def _ensure_shape_candidates(self, shape):
        if getattr(shape, "char_candidates", None):
            return True
        if not self.filePath or not os.path.exists(self.filePath):
            return False
        img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return False
        box = [[int(p.x()), int(p.y())] for p in shape.points]
        if len(box) > 4:
            box = self.gen_quad_from_poly(np.array(box))
        if len(box) != 4:
            return False
        img_crop = get_rotate_crop_image(img, np.array(box, np.float32))
        if img_crop is None:
            return False
        result = self._decode_with_lexicon(self.text_recognizer.predict(img_crop)[0])
        candidates = result.get("char_candidates")
        if not candidates:
            return False
        shape.char_candidates = candidates
        self._store_shape_candidates(shape, box, candidates)
        return True

    def _candidate_strings_from_char_candidates(self, char_candidates):
        if not isinstance(char_candidates, list):
            return []
        if not char_candidates:
            return []
        best_chars = []
        alt_chars = []
        for entry in char_candidates:
            if not isinstance(entry, dict):
                continue
            char = entry.get("char")
            if char:
                best_chars.append(str(char))
            options = entry.get("candidates") or []
            if options and isinstance(options, list):
                best_alt = options[0].get("char")
                if best_alt:
                    alt_chars.append(str(best_alt))
        extras = []
        joined_best = "".join(best_chars).strip()
        joined_alt = "".join(alt_chars).strip()
        if joined_best:
            extras.append(joined_best)
        if joined_alt and joined_alt != joined_best:
            extras.append(joined_alt)
        return extras

    def _decode_with_lexicon(self, result):
        if not isinstance(result, dict):
            return result
        if not getattr(self, "lexicon_manager", None):
            return result
        rec_text = result.get("rec_text") or ""
        candidates = self._candidate_strings_from_char_candidates(
            result.get("char_candidates", [])
        )
        suggestion = self.lexicon_manager.suggest(
            rec_text,
            base_score=float(result.get("rec_score") or 0.0),
            extra_candidates=candidates,
        )
        if suggestion and suggestion.text != rec_text:
            updated = dict(result)
            updated["raw_rec_text"] = rec_text
            updated["rec_text"] = suggestion.text
            updated["rec_score"] = suggestion.score
            updated["lexicon_reason"] = suggestion.reason
            return updated
        return result

    def _update_label_item_style(self, shape):
        item = self.shapesToItems.get(shape)
        if not item:
            return
        score = getattr(shape, "rec_score", 1.0)
        sequence = getattr(shape, "char_candidates", None)
        has_char_scores = (
            isinstance(sequence, list)
            and len(sequence) == len(shape.label or "")
            and all(isinstance(entry, dict) for entry in sequence)
        )
        if getattr(shape, "is_ai_corrected", False):
            item.setForeground(self._ai_edit_brush)
        elif has_char_scores:
            item.setForeground(self._default_label_brush)
        else:
            if score < self.low_confidence_threshold:
                item.setForeground(self._low_confidence_brush)
            else:
                item.setForeground(self._default_label_brush)
        if isinstance(score, (int, float)):
            tooltip = f"Confidence: {score:.2f}"
            if getattr(shape, "is_ai_corrected", False):
                tooltip += " | AI"
            item.setToolTip(tooltip)

    def saveLabels(self, annotationFilePath, mode="Auto"):
        # Mode is Auto means that labels will be loaded from self.result_dic totally, which is the output of ocr model
        annotationFilePath = annotationFilePath

        def format_shape(s):
            # print('s in saveLabels is ',s)
            return dict(
                label=s.label,  # str
                line_color=s.line_color.getRgb(),
                fill_color=s.fill_color.getRgb(),
                points=[(int(p.x()), int(p.y())) for p in s.points],  # QPonitF
                difficult=s.difficult,
                key_cls=s.key_cls,
                history=copy.deepcopy(getattr(s, "history", [])),
                instance_id=getattr(s, "instance_id", None),
            )  # bool

        if mode == "Auto":
            shapes = []
        else:
            shapes = [
                format_shape(shape)
                for shape in self.canvas.shapes
                if shape.line_color != DEFAULT_LOCK_COLOR
            ]
        # Can add different annotation formats here
        for res in self.result_dic:
            trans_dic = {"label": res[1][0], "points": res[0], "difficult": False}
            if self.kie_mode:
                if len(res) == 3:
                    trans_dic.update({"key_cls": res[2]})
                else:
                    trans_dic.update({"key_cls": "None"})
            if trans_dic["label"] == "" and mode == "Auto":
                continue
            score_val = 0.0
            try:
                score_val = float(res[1][1])
            except Exception:
                score_val = 0.0
            key = self._candidate_key_from_box(trans_dic["points"])
            self._score_cache[key] = score_val
            shapes.append(trans_dic)

        try:
            trans_dic = []
            for box in shapes:
                trans_dict = {
                    "transcription": box["label"],
                    "points": box["points"],
                    "difficult": box["difficult"],
                }
                if self.kie_mode:
                    trans_dict.update({"key_cls": box["key_cls"]})
                history = copy.deepcopy(box.get("history") or [])
                instance_id = box.get("instance_id") or str(uuid.uuid4())
                trans_dict["history"] = history
                trans_dict["instance_id"] = instance_id
                box["instance_id"] = instance_id
                trans_dic.append(trans_dict)
            self.PPlabel[annotationFilePath] = trans_dic
            if mode == "Auto":
                self.Cachelabel[annotationFilePath] = trans_dic

            # else:
            #     self.labelFile.save(annotationFilePath, shapes, self.filePath, self.imageData,
            #                         self.lineColor.getRgb(), self.fillColor.getRgb())
            # print('Image:{0} -> Annotation:{1}'.format(self.filePath, annotationFilePath))
            return True
        except Exception:
            self.errorMessage("Error saving label data", "Error saving label data")
            return False

    def copySelectedShape(self):
        for shape in self.canvas.copySelectedShape():
            self.addLabel(shape)
        # fix copy and delete
        # self.shapeSelectionChanged(True)

    def move_scrollbar(self, value):
        self.labelListBar.setValue(int(value))
        self.indexListBar.setValue(int(value))

    def _apply_result_font_size(self, size):
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = self.result_font_size
        size = max(8, min(48, size))
        self.result_font_size = size
        style = (
            f"QListWidget {{ font-size: {size}px; }} "
            f"QListWidget::item {{ font-size: {size}px; }}"
        )
        if hasattr(self, "labelList"):
            self.labelList.setStyleSheet(style)
        if hasattr(self, "indexList"):
            self.indexList.setStyleSheet(style)

    def _on_result_font_size_changed(self, value):
        self._apply_result_font_size(value)
        self.settings[SETTING_RESULT_FONT_SIZE] = self.result_font_size

    def toggle_box_panel_visibility(self):
        new_visibility = not self.BoxListDock.isVisible()
        self.BoxListDock.setVisible(new_visibility)
        self.settings[SETTING_DET_PANEL_VISIBLE] = new_visibility
        self._update_box_panel_button_text()

    def _update_box_panel_button_text(self):
        if not hasattr(self, "toggleBoxPanelButton"):
            return
        text_id = "showDetectionPanel"
        if self.BoxListDock.isVisible():
            text_id = "hideDetectionPanel"
        self.toggleBoxPanelButton.setText(self.get_str(text_id))

    def labelSelectionChanged(self):
        if self._noSelectionSlot:
            return
        if self.canvas.editing():
            selected_shapes = []
            for item in self.labelList.selectedItems():
                shape = self._shape_from_label_item(item)
                if shape:
                    selected_shapes.append(shape)
            if selected_shapes:
                self.canvas.selectShapes(selected_shapes)
            else:
                self.canvas.deSelectShape()

    def indexSelectionChanged(self):
        if self._noSelectionSlot:
            return
        if self.canvas.editing():
            selected_shapes = []
            for item in self.indexList.selectedItems():
                # map index item to label item
                index = self.indexList.indexFromItem(item).row()
                item = self.labelList.item(index)
                shape = self._shape_from_label_item(item)
                if shape:
                    selected_shapes.append(shape)
            if selected_shapes:
                self.canvas.selectShapes(selected_shapes)
            else:
                self.canvas.deSelectShape()

    def boxSelectionChanged(self):
        if self._noSelectionSlot:
            # self.BoxList.scrollToItem(self.currentBox(), QAbstractItemView.PositionAtCenter)
            return
        if self.canvas.editing():
            selected_shapes = []
            for item in self.BoxList.selectedItems():
                selected_shapes.append(self.itemsToShapesbox[item])
            if selected_shapes:
                self.canvas.selectShapes(selected_shapes)
            else:
                self.canvas.deSelectShape()

    def labelItemChanged(self, item):
        if item is None:
            return

        shape = self._shape_from_label_item(item)
        if shape is None:
            logger.warning(
                "enter labelItemChanged slot with unresolved item: %s %s",
                item,
                item.text() if hasattr(item, "text") else "",
            )
            return

        label = item.text()
        old_label = shape.label or ""
        if label != shape.label:
            shape.label = label
            shape.is_ai_corrected = False
            self._record_shape_history(
                shape,
                shape.label,
                source="list-edit",
                previous_text=old_label,
            )
            self._update_label_item_style(shape)
            # shape.line_color = generateColorByText(shape.label)
            self.setDirty()
        elif not ((item.checkState() == Qt.Unchecked) ^ (not shape.difficult)):
            shape.difficult = True if item.checkState() == Qt.Unchecked else False
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(
                shape, True
            )  # item.checkState() == Qt.Checked
            # self.actions.save.setEnabled(True)

    def drag_drop_happened(self):
        """
        label list drag drop signal slot
        """
        # should only select single item
        for item in self.labelList.selectedItems():
            newIndex = self.labelList.indexFromItem(item).row()

        # only support drag_drop one item
        assert len(self.canvas.selectedShapes) > 0
        for shape in self.canvas.selectedShapes:
            selectedShapeIndex = shape.idx

        if newIndex == selectedShapeIndex:
            return

        # move corresponding item in shape list
        shape = self.canvas.shapes.pop(selectedShapeIndex)
        self.canvas.shapes.insert(newIndex, shape)

        # update bbox index
        self.canvas.updateShapeIndex()

        # boxList update simultaneously
        item = self.BoxList.takeItem(selectedShapeIndex)
        self.BoxList.insertItem(newIndex, item)

        # changes happen
        self.setDirty()

    # Callback functions:
    def newShape(self, value=True):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if len(self.labelHist) > 0:
            self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist)

        if value:
            text = self.labelDialog.popUp(text=self.prevLabelText)
            self.lastLabel = text
        else:
            text = self.prevLabelText

        if text is not None:
            self.prevLabelText = self.stringBundle.getString("tempLabel")

            shape = self.canvas.setLastLabel(
                text, None, None, None
            )  # generate_color, generate_color
            if self.kie_mode:
                key_text, _ = self.keyDialog.popUp(self.key_previous_text)
                if key_text is not None:
                    shape = self.canvas.setLastLabel(
                        text, None, None, key_text
                    )  # generate_color, generate_color
                    self.key_previous_text = key_text
                    if not self.keyList.findItemsByLabel(key_text):
                        item = self.keyList.createItemFromLabel(key_text)
                        self.keyList.addItem(item)
                        rgb = self._get_rgb_by_label(key_text, self.kie_mode)
                        self.keyList.setItemLabel(item, key_text, rgb)

                    self._update_shape_color(shape)
                    self.keyDialog.addLabelHistory(key_text)

            self.addLabel(shape)
            if self.beginner():  # Switch to edit mode.
                self.canvas.setEditing(True)
                self.actions.create.setEnabled(True)
                self.actions.createpoly.setEnabled(True)
                self.actions.undoLastPoint.setEnabled(False)
                self.actions.undo.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.setDirty()

            if self.autoReRecognitionOption.isChecked():
                self.reRecognition()
        else:
            # self.canvas.undoLastLine()
            self.canvas.resetAllLines()

    def _update_shape_color(self, shape):
        r, g, b = self._get_rgb_by_label(shape.key_cls, self.kie_mode)
        shape.line_color = QColor(r, g, b)
        shape.vertex_fill_color = QColor(r, g, b)
        shape.hvertex_fill_color = QColor(255, 255, 255)
        shape.fill_color = QColor(r, g, b, 32)
        shape.select_line_color = QColor(
            self.selected_shape_color[0],
            self.selected_shape_color[1],
            self.selected_shape_color[2],
        )
        shape.select_fill_color = QColor(r, g, b, 32)

    def _get_rgb_by_label(self, label, kie_mode):
        shift_auto_shape_color = 2  # use for random color
        if kie_mode and label != "None":
            item = self.keyList.findItemsByLabel(label)[0]
            label_id = self.keyList.indexFromItem(item).row() + 1
            label_id += shift_auto_shape_color
            return LABEL_COLORMAP[label_id % len(LABEL_COLORMAP)]
        else:
            return 0, 255, 0

    def scrollRequest(self, delta, orientation):
        units = -delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(int(bar.value() + bar.singleStep() * units))

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(int(value))

    def addZoom(self, increment=10):
        self.setZoom(int(self.zoomWidget.value() + increment))
        self.imageSlider.setValue(
            int(self.zoomWidget.value() + increment)
        )  # set zoom slider value

    def zoomRequest(self, delta, pos: QPoint = None):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        if pos is None:
            cursor = QCursor()
            pos = cursor.pos()

        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scrollArea.width()
        h = self.scrollArea.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        h_bar.setValue(int(new_h_bar_value))
        v_bar.setValue(int(new_v_bar_value))

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.items():
            self.canvas.setShapeVisible(shape, value)

    def loadFile(self, filePath=None, isAdjustScale=True):
        """Load the specified file, or the last opened file if None."""
        self.canvas.shape_move_index = None
        if self.dirty:
            self.mayContinue()
        self.resetState()
        self.canvas.setEnabled(False)
        if filePath is None:
            filePath = self.settings.get(SETTING_FILENAME)

        # Make sure that filePath is a regular python string, rather than QString
        filePath = filePath
        # Fix bug: An index error after select a directory when open a new file.
        unicodeFilePath = filePath
        # unicodeFilePath = os.path.abspath(unicodeFilePath)
        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item

        if unicodeFilePath and self.fileListWidget.count() > 0:
            if unicodeFilePath in self.mImgList:
                index = self.mImgList.index(unicodeFilePath)
                fileWidgetItem = self.fileListWidget.item(index)
                logger.debug("unicodeFilePath is %s", unicodeFilePath)
                fileWidgetItem.setSelected(True)
                self.iconlist.clear()
                self.additems5(None)

                for i in range(5):
                    item_tooltip = self.iconlist.item(i).toolTip()
                    # print(i,"---",item_tooltip)
                    if item_tooltip == filePath:
                        t_item = self.iconlist.item(i)
                        t_item.setSelected(True)
                        self.iconlist.scrollToItem(t_item)
                        break
            else:
                self.fileListWidget.clear()
                self.mImgList.clear()
                self.iconlist.clear()

        # if unicodeFilePath and self.iconList.count() > 0:
        #     if unicodeFilePath in self.mImgList:

        if unicodeFilePath and os.path.exists(unicodeFilePath):
            self.canvas.verified = False
            cvimg = cv2.imdecode(
                np.fromfile(unicodeFilePath, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            height, width, depth = cvimg.shape
            cvimg = cv2.cvtColor(cvimg, cv2.COLOR_BGR2RGB)
            image = QImage(
                cvimg.data, width, height, width * depth, QImage.Format_RGB888
            )

            if image.isNull():
                self.errorMessage(
                    "Error opening file",
                    "<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath,
                )
                self.status("Error reading %s" % unicodeFilePath)
                return False
            self.status("Loaded %s" % os.path.basename(unicodeFilePath))
            self.image = image
            self.filePath = unicodeFilePath
            if self._cache_owner != unicodeFilePath:
                self._candidate_cache.clear()
                self._score_cache.clear()
                self._cache_owner = unicodeFilePath
            if unicodeFilePath in self.mImgList:
                self.currIndex = self.mImgList.index(unicodeFilePath)
            self.canvas.loadPixmap(QPixmap.fromImage(image))

            if self.validFilestate(filePath) is True:
                self.setClean()
            else:
                self.dirty = False
                self.actions.save.setEnabled(True)
            if len(self.canvas.lockedShapes) != 0:
                self.actions.save.setEnabled(True)
                self.setDirty()
            self.canvas.setEnabled(True)
            if isAdjustScale:
                self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.filePath)
            self.toggleActions(True)

            self.showBoundingBoxFromPPlabel(filePath)

            self.setWindowTitle(__appname__ + " " + filePath)

            # Default : select last item if there is at least one item
            if self.labelList.count():
                self.labelList.setCurrentItem(
                    self.labelList.item(self.labelList.count() - 1)
                )
                self.labelList.item(self.labelList.count() - 1).setSelected(True)
                self.indexList.item(self.labelList.count() - 1).setSelected(True)

            # show file list image count
            select_indexes = self.fileListWidget.selectedIndexes()
            if len(select_indexes) > 0:
                self.fileDock.setWindowTitle(
                    self.fileListName + f" ({select_indexes[0].row() + 1}"
                    f"/{self.fileListWidget.count()})"
                )
            # update show counting
            self.BoxListDock.setWindowTitle(
                self.BoxListDockName + f" ({self.BoxList.count()})"
            )
            self.labelListDock.setWindowTitle(
                self.labelListDockName + f" ({self.labelList.count()})"
            )

            self.canvas.setFocus(True)

            if self.bbox_auto_zoom_center:
                if len(self.canvas.shapes) > 0:
                    (
                        center_x,
                        center_y,
                        shape_area,
                    ) = polygon_bounding_box_center_and_area(
                        self.canvas.shapes[0].points
                    )
                    if shape_area < 30000:
                        zoom_value = 120 * map_value(shape_area, 100, 30000, 20, 0)
                        self.zoomRequest(zoom_value, QPoint(center_x, center_y))
                        # print(" =========> ", shape_area, " ==> ", zoom_value)
            return True
        return False

    def showBoundingBoxFromPPlabel(self, filePath):
        width, height = self.image.width(), self.image.height()
        img_idx = self.getImglabelidx(filePath)
        shapes = []
        for box in self.canvas.lockedShapes:
            key_cls = "None" if not self.kie_mode else box["key_cls"]
            extras = {"history": [], "instance_id": box.get("instance_id")}
            points = [[s[0] * width, s[1] * height] for s in box["ratio"]]
            label_text = (
                box["transcription"]
                if self.canvas.isInTheSameImage
                else "锁定框：待检验"
            )
            shapes.append(
                (
                    label_text,
                    points,
                    DEFAULT_LOCK_COLOR,
                    key_cls,
                    box["difficult"],
                    extras,
                )
            )
        if img_idx in self.PPlabel.keys():
            for box in self.PPlabel[img_idx]:
                key_cls = "None" if not self.kie_mode else box.get("key_cls", "None")
                extras = {
                    "history": copy.deepcopy(box.get("history") or []),
                    "instance_id": box.get("instance_id"),
                }
                shapes.append(
                    (
                        box["transcription"],
                        box["points"],
                        None,
                        key_cls,
                        box.get("difficult", False),
                        extras,
                    )
                )

        if shapes:
            self.loadLabels(shapes)
            self.canvas.verified = False
    def validFilestate(self, filePath):
        if filePath in self.fileStatedict.keys() and self.fileStatedict[filePath] == 1:
            return True
        elif (
            self.getImglabelidx(filePath) in self.fileStatedict.keys()
            and self.fileStatedict[self.getImglabelidx(filePath)] == 1
        ):
            return True
        else:
            return False

    def resizeEvent(self, event):
        if (
            self.canvas
            and not self.image.isNull()
            and self.zoomMode != self.MANUAL_ZOOM
        ):
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))
        self.imageSlider.setValue(self.zoomWidget.value())  # set zoom slider value

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e - 110
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        else:
            settings = self.settings
            # If it loads images from dir, don't load it at the beginning
            if self.dirname is None:
                settings[SETTING_FILENAME] = self.filePath if self.filePath else ""
            else:
                settings[SETTING_FILENAME] = ""

            settings[SETTING_WIN_SIZE] = self.size()
            settings[SETTING_WIN_POSE] = self.pos()
            settings[SETTING_WIN_STATE] = self.saveState()
            settings[SETTING_LINE_COLOR] = self.lineColor
            settings[SETTING_FILL_COLOR] = self.fillColor
            settings[SETTING_RECENT_FILES] = self.recentFiles
            settings[SETTING_ADVANCE_MODE] = not self._beginner
            if self.defaultSaveDir and os.path.exists(self.defaultSaveDir):
                settings[SETTING_SAVE_DIR] = self.defaultSaveDir
            else:
                settings[SETTING_SAVE_DIR] = ""

            if self.lastOpenDir and os.path.exists(self.lastOpenDir):
                settings[SETTING_LAST_OPEN_DIR] = self.lastOpenDir
            else:
                settings[SETTING_LAST_OPEN_DIR] = ""

            settings[SETTING_PAINT_LABEL] = self.displayLabelOption.isChecked()
            settings[SETTING_PAINT_INDEX] = self.displayIndexOption.isChecked()
            settings[SETTING_DRAW_SQUARE] = self.drawSquaresOption.isChecked()
            settings.save()
            try:
                self.saveLabelFile()
            except Exception:
                pass

    def loadRecent(self, filename):
        if self.mayContinue():
            logger.info("Loading recent file: %s", filename)
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = [
            ".%s" % fmt.data().decode("ascii").lower()
            for fmt in QImageReader.supportedImageFormats()
        ]
        images = []

        for file in os.listdir(folderPath):
            if file.lower().endswith(tuple(extensions)):
                relativePath = os.path.join(folderPath, file)
                path = os.path.abspath(relativePath)
                images.append(path)
        if self.img_list_natural_sort:
            natural_sort(images, key=lambda x: x.lower())
        else:
            images.sort()
        return images

    def openDirDialog(self, _value=False, dirpath=None, silent=False):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else "."
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = (
                os.path.dirname(self.filePath) if self.filePath else "."
            )
        if not silent:
            targetDirPath = QFileDialog.getExistingDirectory(
                self,
                "%s - Open Directory" % __appname__,
                defaultOpenDirPath,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
            )
        else:
            targetDirPath = defaultOpenDirPath
        self.lastOpenDir = targetDirPath
        self.importDirImages(targetDirPath)

    def openDatasetDirDialog(self):
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            if platform.system() == "Windows":
                os.startfile(self.lastOpenDir)
            else:
                os.system("open " + os.path.normpath(self.lastOpenDir))
            defaultOpenDirPath = self.lastOpenDir

        else:
            if self.lang == "ch":
                self.msgBox.warning(self, "提示", "\n 原文件夹已不存在,请从新选择数据集路径!")
            else:
                self.msgBox.warning(
                    self,
                    "Warn",
                    "\n The original folder no longer exists, please choose the data set path again!",
                )

            self.actions.open_dataset_dir.setEnabled(False)
            defaultOpenDirPath = (
                os.path.dirname(self.filePath) if self.filePath else "."
            )

    def importPdfDialog(self):
        if not self.mayContinue():
            return

        start_dir = (
            self.lastOpenDir
            if self.lastOpenDir and os.path.exists(self.lastOpenDir)
            else "."
        )
        pdf_paths, _ = QFileDialog.getOpenFileNames(
            self, self.get_str("selectPdf"), start_dir, "PDF Files (*.pdf)"
        )
        if not pdf_paths:
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            self.get_str("selectPdfOutputDir"),
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not output_dir:
            return

        total_pages = self._count_pdf_pages(pdf_paths)
        progress = QProgressDialog(
            self.get_str("pdfImportProgress").format(0, total_pages),
            self.get_str("cancel"),
            0,
            total_pages,
            self,
        )
        progress.setWindowTitle(self.get_str("importPdf"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            converted = self._convert_pdfs_to_images(
                pdf_paths, output_dir, progress=progress, total_pages=total_pages
            )
        except RuntimeError as e:
            if "canceled" in str(e).lower():
                QMessageBox.information(
                    self, self.get_str("info"), self.get_str("pdfImportCancelled")
                )
                converted = []
            else:
                QMessageBox.warning(
                    self, "Warning", self.get_str("pdfImportFailed").format(str(e))
                )
                converted = []
        except Exception as e:
            QMessageBox.warning(
                self, "Warning", self.get_str("pdfImportFailed").format(str(e))
            )
            converted = []
        finally:
            progress.close()
            QApplication.restoreOverrideCursor()

        if converted:
            self.lastOpenDir = output_dir
            self.importDirImages(output_dir)
            QMessageBox.information(
                self,
                self.get_str("info"),
                self.get_str("pdfImportSuccess").format(len(converted), output_dir),
            )

    def _count_pdf_pages(self, pdf_paths):
        try:
            import fitz  # PyMuPDF
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(f"PyMuPDF import failed: {exc}") from exc

        total = 0
        for pdf_path in pdf_paths:
            doc = fitz.open(pdf_path)
            total += doc.page_count
            doc.close()
        return total

    def _convert_pdfs_to_images(self, pdf_paths, output_dir, progress=None, total_pages=None):
        try:
            import fitz  # PyMuPDF
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(f"PyMuPDF import failed: {exc}") from exc

        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        converted_files = []
        completed = 0
        if progress and total_pages is not None:
            progress.setMaximum(total_pages)

        for pdf_path in pdf_paths:
            doc = fitz.open(pdf_path)
            try:
                base_name = Path(pdf_path).stem
                for page_index in range(doc.page_count):
                    if progress and progress.wasCanceled():
                        raise RuntimeError("canceled")
                    page = doc.load_page(page_index)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    file_name = f"{base_name}_p{page_index + 1:03d}.png"
                    img_path = output_root / file_name
                    if img_path.exists():
                        img_path = output_root / f"{base_name}_p{page_index + 1:03d}_{uuid.uuid4().hex[:6]}.png"
                    pix.save(str(img_path))
                    converted_files.append(str(img_path))
                    completed += 1
                    if progress and total_pages is not None:
                        progress.setValue(completed)
                        progress.setLabelText(
                            self.get_str("pdfImportProgress").format(
                                completed, total_pages
                            )
                        )
                        QApplication.processEvents()
            finally:
                doc.close()

        return converted_files

    def init_key_list(self, label_dict):
        if not self.kie_mode:
            return
        # load key_cls
        for image, info in label_dict.items():
            for box in info:
                if "key_cls" not in box:
                    box.update({"key_cls": "None"})
                self.existed_key_cls_set.add(box["key_cls"])
        if len(self.existed_key_cls_set) > 0:
            for key_text in self.existed_key_cls_set:
                if not self.keyList.findItemsByLabel(key_text):
                    item = self.keyList.createItemFromLabel(key_text)
                    self.keyList.addItem(item)
                    rgb = self._get_rgb_by_label(key_text, self.kie_mode)
                    self.keyList.setItemLabel(item, key_text, rgb)

        if self.keyDialog is None:
            # key list dialog
            self.keyDialog = KeyDialog(
                text=self.key_dialog_tip,
                parent=self,
                labels=self.existed_key_cls_set,
                sort_labels=True,
                show_text_field=True,
                completion="startswith",
                fit_to_content={"column": True, "row": False},
                flags=None,
            )

    def importDirImages(self, dirpath, isDelete=False):
        if not self.mayContinue() or not dirpath:
            return
        if self.defaultSaveDir and self.defaultSaveDir != dirpath:
            self.saveLabelFile()

        if not isDelete:
            self.loadFilestate(dirpath)
            self.PPlabelpath = dirpath + "/Label.txt"
            self.PPlabel = self.loadLabelFile(self.PPlabelpath)
            self.Cachelabelpath = dirpath + "/Cache.cach"
            self.Cachelabel = self.loadLabelFile(self.Cachelabelpath)
            if self.Cachelabel:
                self.PPlabel = dict(self.Cachelabel, **self.PPlabel)

            self.init_key_list(self.PPlabel)

        self.lastOpenDir = dirpath
        self.dirname = dirpath

        self.defaultSaveDir = dirpath
        self.statusBar().showMessage(
            "%s started. Annotation will be saved to %s"
            % (__appname__, self.defaultSaveDir)
        )
        self.statusBar().show()

        imgListCurrIndex = None
        if self.filePath:
            imgListCurrIndex = self.mImgList.index(self.filePath)

        self.filePath = None
        self.fileListWidget.clear()
        self.mImgList = self.scanAllImages(dirpath)
        self.mImgList5 = self.mImgList[:5]
        self.openNextImg(imgListCurrIndex=imgListCurrIndex)
        doneicon = newIcon("done")
        closeicon = newIcon("close")
        for imgPath in self.mImgList:
            filename = os.path.basename(imgPath)
            if self.validFilestate(imgPath) is True:
                item = QListWidgetItem(doneicon, filename)
            else:
                item = QListWidgetItem(closeicon, filename)
            self.fileListWidget.addItem(item)

        logger.info("DirPath in importDirImages is %s", dirpath)
        self.iconlist.clear()
        self.additems5(dirpath)
        self.changeFileFolder = True
        self.haveAutoReced = False
        self.auto_recognition_num = len(self.mImgList)
        self.AutoRecognitionNum.setRange(0, len(self.mImgList))
        self.AutoRecognitionNum.setValue(self.auto_recognition_num)
        self.AutoRecognition.setEnabled(True)
        self.reRecogButton.setEnabled(True)
        self.proofreadButton.setEnabled(True)
        self.addLexiconButton.setEnabled(True)
        self.tableRecButton.setEnabled(True)
        self.actions.AutoRec.setEnabled(True)
        self.actions.AutoRecCurrent.setEnabled(True)
        self.actions.reRec.setEnabled(True)
        self.actions.autoProofread.setEnabled(True)
        self.actions.addPageToLexicon.setEnabled(True)
        self.actions.addToLexicon.setEnabled(True)
        self.actions.tableRec.setEnabled(True)
        self.actions.open_dataset_dir.setEnabled(True)
        self.actions.rotateLeft.setEnabled(True)
        self.actions.rotateRight.setEnabled(True)

        fileListWidgetCurrentRow = 0
        if imgListCurrIndex is not None:
            fileListWidgetCurrentRow = imgListCurrIndex
            if fileListWidgetCurrentRow >= self.fileListWidget.count():
                fileListWidgetCurrentRow = fileListWidgetCurrentRow - 1

        self.fileListWidget.setCurrentRow(
            fileListWidgetCurrentRow
        )  # set list index to first
        self.fileDock.setWindowTitle(
            self.fileListName
            + f" ({fileListWidgetCurrentRow + 1}/{self.fileListWidget.count()})"
        )  # show image count

    def openPrevImg(self, _value=False):
        if len(self.mImgList) <= 0:
            return

        if self.filePath is None:
            return

        currIndex = self.mImgList.index(self.filePath)
        self.mImgList5 = self.mImgList[:5]
        if currIndex - 1 >= 0:
            filename = self.mImgList[currIndex - 1]
            self.mImgList5 = self.indexTo5Files(currIndex - 1)
            if filename:
                self.loadFile(filename)

    def openNextImg(self, _value=False, imgListCurrIndex=None):
        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return

        filename = None
        if self.filePath is None and imgListCurrIndex is None:
            filename = self.mImgList[0]
            self.mImgList5 = self.mImgList[:5]
        else:
            if imgListCurrIndex is None:
                currIndex = self.mImgList.index(self.filePath)
            else:
                currIndex = imgListCurrIndex - 1

            if currIndex + 1 < len(self.mImgList):
                filename = self.mImgList[currIndex + 1]
                self.mImgList5 = self.indexTo5Files(currIndex + 1)
            else:
                filename = self.mImgList[currIndex]
                self.mImgList5 = self.indexTo5Files(currIndex)
        if filename:
            logger.debug("file name in openNext is %s", filename)
            self.loadFile(filename)

    def updateFileListIcon(self, filename):
        pass

    def saveFile(self, _value=False, mode="Manual"):
        # Manual mode is used for users click "Save" manually,which will change the state of the image
        if self.filePath:
            img_idx = self.getImglabelidx(self.filePath)
            self._saveFile(img_idx, mode=mode)

    def saveLockedShapes(self):
        self.canvas.lockedShapes = []
        self.canvas.selectedShapes = []
        for s in self.canvas.shapes:
            if s.line_color == DEFAULT_LOCK_COLOR:
                self.canvas.selectedShapes.append(s)
        self.lockSelectedShape()
        for s in self.canvas.shapes:
            if s.line_color == DEFAULT_LOCK_COLOR:
                self.canvas.selectedShapes.remove(s)
                self.canvas.shapes.remove(s)

    def _saveFile(self, annotationFilePath, mode="Manual"):
        if len(self.canvas.lockedShapes) != 0:
            self.saveLockedShapes()

        if mode == "Manual":
            self.result_dic_locked = []
            img = cv2.imdecode(
                np.fromfile(self.filePath, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            width, height = self.image.width(), self.image.height()
            for shape in self.canvas.lockedShapes:
                box = [[int(p[0] * width), int(p[1] * height)] for p in shape["ratio"]]
                # assert len(box) == 4
                result = [(shape["transcription"], 1)]
                result.insert(0, box)
                self.result_dic_locked.append(result)
            self.result_dic += self.result_dic_locked
            self.result_dic_locked = []
            if annotationFilePath and self.saveLabels(annotationFilePath, mode=mode):
                self.setClean()
                self.statusBar().showMessage("Saved to  %s" % annotationFilePath)
                self.statusBar().show()
                currIndex = self.mImgList.index(self.filePath)
                item = self.fileListWidget.item(currIndex)
                item.setIcon(newIcon("done"))

                self.fileStatedict[self.getImglabelidx(self.filePath)] = 1
                if len(self.fileStatedict) % self.autoSaveNum == 0:
                    self.saveFilestate()
                    self.savePPlabel(mode="Auto")

                self.fileListWidget.insertItem(int(currIndex), item)
                if not self.canvas.isInTheSameImage:
                    self.openNextImg()
                self.actions.saveRec.setEnabled(True)
                self.actions.exportFullText.setEnabled(True)
                self.actions.saveLabel.setEnabled(True)
                self.actions.exportJSON.setEnabled(True)

        elif mode == "Auto":
            if annotationFilePath and self.saveLabels(annotationFilePath, mode=mode):
                self.setClean()
                self.statusBar().showMessage("Saved to  %s" % annotationFilePath)
                self.statusBar().show()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def deleteImg(self):
        deletePath = self.filePath
        if deletePath is not None:
            deleteInfo = self.deleteImgDialog()
            if deleteInfo == QMessageBox.Yes:
                if platform.system() == "Windows":
                    # from win32com import shell, shellcon
                    # shell.SHFileOperation((0, shellcon.FO_DELETE, deletePath, None,
                    #                        shellcon.FOF_SILENT | shellcon.FOF_ALLOWUNDO | shellcon.FOF_NOCONFIRMATION,
                    #                        None, None))
                    os.remove(deletePath)
                    # linux
                elif platform.system() == "Linux":
                    cmd = "trash " + deletePath
                    os.system(cmd)
                    # macOS
                elif platform.system() == "Darwin":
                    import subprocess

                    absPath = (
                        os.path.abspath(deletePath)
                        .replace("\\", "\\\\")
                        .replace('"', '\\"')
                    )
                    cmd = [
                        "osascript",
                        "-e",
                        'tell app "Finder" to move {the POSIX file "'
                        + absPath
                        + '"} to trash',
                    ]
                    logger.debug("Executing command: %s", " ".join(cmd))
                    subprocess.call(cmd, stdout=open(os.devnull, "w"))

                if self.filePath in self.fileStatedict.keys():
                    self.fileStatedict.pop(self.filePath)
                imgidx = self.getImglabelidx(self.filePath)
                if imgidx in self.PPlabel.keys():
                    self.PPlabel.pop(imgidx)

                self.importDirImages(self.lastOpenDir, isDelete=True)

    def deleteImgDialog(self):
        yes, cancel = QMessageBox.Yes, QMessageBox.Cancel
        msg = "The image will be deleted to the recycle bin"
        return QMessageBox.warning(self, "Attention", msg, yes | cancel)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(__file__))

    def mayContinue(self):  #
        if not self.dirty:
            return True
        else:
            if self.autoSaveUnsavedChangesOption.isChecked():
                self.canvas.isInTheSameImage = True
                self.saveFile()
                self.canvas.isInTheSameImage = False
                return True

            discardChanges = self.discardChangesDialog()
            if discardChanges == QMessageBox.No:
                return True
            elif discardChanges == QMessageBox.Yes:
                self.canvas.isInTheSameImage = True
                self.saveFile()
                self.canvas.isInTheSameImage = False
                return True
            else:
                return False

    def discardChangesDialog(self):
        yes, no, cancel = QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel
        if self.lang == "ch":
            msg = '您有未保存的变更, 您想保存再继续吗?\n点击 "No" 丢弃所有未保存的变更.'
        else:
            msg = 'You have unsaved changes, would you like to save them and proceed?\nClick "No" to undo all changes.'
        return QMessageBox.warning(self, "Attention", msg, yes | no | cancel)

    def errorMessage(self, title, message):
        return QMessageBox.critical(
            self, title, "<p><b>%s</b></p>%s" % (title, message)
        )

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else "."

    def chooseColor(self):
        color = self.colorDialog.getColor(
            self.lineColor, "Choose line color", default=DEFAULT_LINE_COLOR
        )
        if color:
            self.lineColor = color
            Shape.line_color = color
            self.canvas.setDrawingColor(color)
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        self.remLabels(self.canvas.deleteSelected())
        self.actions.undo.setEnabled(True)
        self.setDirty()
        if self.noShapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)
        self.BoxListDock.setWindowTitle(
            self.BoxListDockName + f" ({self.BoxList.count()})"
        )
        self.labelListDock.setWindowTitle(
            self.labelListDockName + f" ({self.labelList.count()})"
        )

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(
            self.lineColor, "Choose line color", default=DEFAULT_LINE_COLOR
        )
        if color:
            for shape in self.canvas.selectedShapes:
                shape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(
            self.fillColor, "Choose fill color", default=DEFAULT_FILL_COLOR
        )
        if color:
            for shape in self.canvas.selectedShapes:
                shape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        if os.path.exists(predefClassesFile) is True:
            with codecs.open(predefClassesFile, "r", "utf8") as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.labelHist = [line]
                    else:
                        self.labelHist.append(line)

    def togglePaintLabelsOption(self):
        self.displayIndexOption.setChecked(False)
        for shape in self.canvas.shapes:
            shape.paintLabel = self.displayLabelOption.isChecked()
            shape.paintIdx = self.displayIndexOption.isChecked()
        self.canvas.repaint()

    def togglePaintIndexOption(self):
        self.displayLabelOption.setChecked(False)
        for shape in self.canvas.shapes:
            shape.paintLabel = self.displayLabelOption.isChecked()
            shape.paintIdx = self.displayIndexOption.isChecked()
        self.canvas.repaint()

    def toogleDrawSquare(self):
        self.canvas.setDrawingShapeToSquare(self.drawSquaresOption.isChecked())

    def additems(self, dirpath):
        for file in self.mImgList:
            pix = QPixmap(file)
            _, filename = os.path.split(file)
            filename, _ = os.path.splitext(filename)
            item = QListWidgetItem(
                QIcon(
                    pix.scaled(100, 100, Qt.IgnoreAspectRatio, Qt.FastTransformation)
                ),
                filename[:10],
            )
            item.setToolTip(file)
            self.iconlist.addItem(item)

    def additems5(self, dirpath):
        for file in self.mImgList5:
            pix = QPixmap(file)
            _, filename = os.path.split(file)
            filename, _ = os.path.splitext(filename)
            pfilename = filename[:10]
            if len(pfilename) < 10:
                lentoken = 12 - len(pfilename)
                prelen = lentoken // 2
                bfilename = prelen * " " + pfilename + (lentoken - prelen) * " "
            # item = QListWidgetItem(QIcon(pix.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)),filename[:10])
            item = QListWidgetItem(
                QIcon(
                    pix.scaled(100, 100, Qt.IgnoreAspectRatio, Qt.FastTransformation)
                ),
                pfilename,
            )
            # item.setForeground(QBrush(Qt.white))
            item.setToolTip(file)
            self.iconlist.addItem(item)
        owidth = 0
        for index in range(len(self.mImgList5)):
            item = self.iconlist.item(index)
            itemwidget = self.iconlist.visualItemRect(item)
            owidth += itemwidget.width()
        self.iconlist.setMinimumWidth(owidth + 50)

    def gen_quad_from_poly(self, poly):
        """
        Generate min area quad from poly.
        """
        point_num = poly.shape[0]
        min_area_quad = np.zeros((4, 2), dtype=np.float32)
        rect = cv2.minAreaRect(
            poly.astype(np.int32)
        )  # (center (x,y), (width, height), angle of rotation)
        box = np.array(cv2.boxPoints(rect))

        first_point_idx = 0
        min_dist = 1e4
        for i in range(4):
            dist = (
                np.linalg.norm(box[(i + 0) % 4] - poly[0])
                + np.linalg.norm(box[(i + 1) % 4] - poly[point_num // 2 - 1])
                + np.linalg.norm(box[(i + 2) % 4] - poly[point_num // 2])
                + np.linalg.norm(box[(i + 3) % 4] - poly[-1])
            )
            if dist < min_dist:
                min_dist = dist
                first_point_idx = i
        for i in range(4):
            min_area_quad[i] = box[(first_point_idx + i) % 4]

        bbox_new = min_area_quad.tolist()
        bbox = []

        for box in bbox_new:
            box = list(map(int, box))
            bbox.append(box)

        return bbox

    def getImglabelidx(self, filePath):
        if platform.system() == "Windows":
            spliter = "\\"
        else:
            spliter = "/"
        file_path_split = filePath.split(spliter)[-2:]
        if len(file_path_split) == 1:
            return filePath
        return file_path_split[0] + "/" + file_path_split[1]

    def _get_labels_for_image(self, filePath):
        """Return labels for an image, tolerant to key formats and cache."""
        idx = self.getImglabelidx(filePath)
        fallback = os.path.basename(filePath)
        for source in (getattr(self, "Cachelabel", {}), getattr(self, "PPlabel", {})):
            if idx in source:
                return source.get(idx)
            if fallback in source:
                return source.get(fallback)
        return None

    def autoRecognitionNum(self, value):
        remain_num = len(self.mImgList) - self.currIndex
        if value == 0:
            self.auto_recognition_num = remain_num
        else:
            self.auto_recognition_num = min(value, remain_num)
        self.AutoRecognitionNum.setValue(self.auto_recognition_num)

    def autoRecognition(self):
        assert self.mImgList is not None
        logger.info("Using model from %s", self.model)

        start_index = self.currIndex
        end_index = min(self.currIndex + self.auto_recognition_num, len(self.mImgList))
        images_to_check = self.mImgList[start_index:end_index]

        self._start_auto_recognition(images_to_check)

    def autoRecognitionCurrent(self):
        assert self.mImgList is not None
        if not self.mImgList:
            return
        logger.info("Auto recognition limited to current page")
        current_image = [self.mImgList[self.currIndex]]
        self._start_auto_recognition(
            current_image, ignore_processed=True, force_images=current_image
        )

    def _start_auto_recognition(
        self, images_to_check, ignore_processed=True, force_images=None
    ):
        if not images_to_check:
            QMessageBox.information(
                self,
                "Information",
                self.stringBundle.getString("autoRecognitionNoPending"),
            )
            return

        force_set = set(force_images) if force_images else set()
        recorded_basenames = {
            os.path.basename(path)
            for path in self.fileStatedict.keys()
            if self.fileStatedict[path] == 1
        } if ignore_processed else set()

        uncheckedList = []
        for image_path in images_to_check:
            image_basename = os.path.basename(image_path)
            if (
                not ignore_processed
                or image_basename not in recorded_basenames
                or image_path in force_set
            ):
                uncheckedList.append(image_path)

        if not uncheckedList:
            QMessageBox.information(
                self,
                "Information",
                self.stringBundle.getString("autoRecognitionNoPending"),
            )
            return

        self.autoDialog = AutoDialog(
            parent=self,
            ocr=self.ocr,
            image_list=uncheckedList,
            len_bar=len(uncheckedList),
        )
        self.autoDialog.popUp()
        self.haveAutoReced = True
        self.filePath = self.mImgList[self.currIndex]
        self.loadFile(self.filePath, isAdjustScale=False)
        self.saveCacheLabel()

        self.init_key_list(self.Cachelabel)

    def launchPaddleTraining(self):
        if self.trainingProcess and self.trainingProcess.state() != QProcess.NotRunning:
            QMessageBox.information(
                self, "Information", self.get_str("trainingAlreadyRunning")
            )
            if self.trainingDialog:
                self.trainingDialog.show()
                self.trainingDialog.raise_()
            return

        repo_dir_default = self.settings.get(SETTING_TRAIN_REPO_DIR, "")
        repo_dir = QFileDialog.getExistingDirectory(
            self, self.get_str("selectPaddleRepo"), repo_dir_default or "."
        )
        if not repo_dir:
            return
        self.settings[SETTING_TRAIN_REPO_DIR] = repo_dir

        config_default = self.settings.get(SETTING_TRAIN_CONFIG_PATH, "")
        start_dir = config_default or os.path.join(repo_dir, "configs")
        config_path, _ = QFileDialog.getOpenFileName(
            self,
            self.get_str("selectTrainConfig"),
            start_dir,
            "YAML Files (*.yml *.yaml)",
        )
        if not config_path:
            return
        self.settings[SETTING_TRAIN_CONFIG_PATH] = config_path

        dataset_dir = None
        auto_split_root = None
        current_dir = self.lastOpenDir
        label_exists = current_dir and os.path.isfile(os.path.join(current_dir, "Label.txt"))
        if label_exists:
            reply = QMessageBox.question(
                self,
                self.get_str("trainingDialogTitle"),
                self.get_str("autoSplitPrompt"),
            )
            if reply == QMessageBox.Yes:
                QApplication.setOverrideCursor(Qt.WaitCursor)
                try:
                    dataset_dir, auto_split_root = self._prepare_dataset_from_current(
                        current_dir
                    )
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Warning",
                        self.get_str("autoSplitFailed").format(str(e)),
                    )
                    dataset_dir = None
                    auto_split_root = None
                finally:
                    QApplication.restoreOverrideCursor()
        if not dataset_dir:
            dataset_default = self.settings.get(
                SETTING_TRAIN_DATASET_DIR, current_dir or ""
            )
            dataset_dir = QFileDialog.getExistingDirectory(
                self, self.get_str("selectTrainDataset"), dataset_default or "."
            )
            if not dataset_dir:
                return
        train_txt = os.path.join(dataset_dir, "train.txt")
        val_txt = os.path.join(dataset_dir, "val.txt")
        if not (os.path.exists(train_txt) and os.path.exists(val_txt)):
            QMessageBox.warning(
                self, "Warning", self.get_str("trainingMissingSplits")
            )
            if auto_split_root:
                shutil.rmtree(auto_split_root, ignore_errors=True)
            return
        self.settings[SETTING_TRAIN_DATASET_DIR] = dataset_dir

        output_default = self.settings.get(SETTING_TRAIN_OUTPUT_DIR, dataset_dir)
        output_dir = QFileDialog.getExistingDirectory(
            self, self.get_str("selectTrainOutput"), output_default or "."
        )
        if not output_dir:
            if auto_split_root:
                shutil.rmtree(auto_split_root, ignore_errors=True)
            return
        self.settings[SETTING_TRAIN_OUTPUT_DIR] = output_dir

        batch_default = self.settings.get(SETTING_TRAIN_BATCH_SIZE, 2)
        batch_size, ok = QInputDialog.getInt(
            self,
            self.get_str("trainingDialogTitle"),
            self.get_str("trainingBatchPrompt"),
            int(batch_default),
            1,
            1024,
        )
        if not ok:
            return
        self.settings[SETTING_TRAIN_BATCH_SIZE] = batch_size

        epoch_default = self.settings.get(SETTING_TRAIN_EPOCHS, 100)
        epochs, ok = QInputDialog.getInt(
            self,
            self.get_str("trainingDialogTitle"),
            self.get_str("trainingEpochPrompt"),
            int(epoch_default),
            1,
            5000,
        )
        if not ok:
            return
        self.settings[SETTING_TRAIN_EPOCHS] = epochs

        self.settings.save()

        self._start_training_process(
            repo_dir,
            config_path,
            dataset_dir,
            output_dir,
            batch_size,
            epochs,
            auto_split_root,
        )

    def _start_training_process(
        self,
        repo_dir,
        config_path,
        dataset_dir,
        output_dir,
        batch_size,
        epochs,
        auto_split_root,
    ):
        script_path = os.path.join(repo_dir, "tools", "train.py")
        if not os.path.exists(script_path):
            QMessageBox.warning(
                self, "Warning", self.get_str("trainingStartFailed")
            )
            return

        train_txt = os.path.normpath(os.path.join(dataset_dir, "train.txt"))
        val_txt = os.path.normpath(os.path.join(dataset_dir, "val.txt"))

        if not (os.path.exists(train_txt) and os.path.exists(val_txt)):
            QMessageBox.warning(
                self, "Warning", self.get_str("trainingMissingSplits")
            )
            return

        norm = lambda p: os.path.normpath(p).replace("\\", "/")
        args = [
            script_path,
            "-c",
            config_path,
            "-o",
            f"Global.use_gpu={'true' if self.gpu == 'gpu' else 'false'}",
            f"Global.save_model_dir={norm(output_dir)}",
            f"Train.loader.batch_size_per_card={batch_size}",
            f"Global.epoch_num={epochs}",
            f"Train.dataset.data_dir={norm(dataset_dir)}",
            f'Train.dataset.label_file_list=["{norm(train_txt)}"]',
            f"Eval.dataset.data_dir={norm(dataset_dir)}",
            f'Eval.dataset.label_file_list=["{norm(val_txt)}"]',
        ]
        self._pendingTrainJob = {
            "repo_dir": repo_dir,
            "config_path": config_path,
            "output_dir": output_dir,
        }

        self.trainingProcess = QProcess(self)
        self.trainingProcess.setProcessChannelMode(QProcess.MergedChannels)
        self.trainingProcess.setWorkingDirectory(repo_dir)
        self.trainingProcess.readyReadStandardOutput.connect(
            self._handle_training_output
        )
        self.trainingProcess.finished.connect(self._training_finished)
        self._currentAutoSplitDir = auto_split_root

        self.trainingDialog = TrainingLogDialog(
            self,
            title=self.get_str("trainingDialogTitle"),
            stop_label=self.get_str("trainingStop"),
            close_label=self.get_str("trainingClose"),
        )
        self.trainingDialog.stopRequested.connect(self._stop_training_process)
        self.trainingDialog.finished.connect(self._training_dialog_closed)
        self.trainingDialog.show()
        self.trainingDialog.set_running(True)

        self.trainingProcess.start(sys.executable, args)
        if not self.trainingProcess.waitForStarted(5000):
            self.trainingDialog.append_text(self.get_str("trainingStartFailed") + "\n")
            self.trainingDialog.set_running(False)
            QMessageBox.warning(self, "Warning", self.get_str("trainingStartFailed"))
            self.trainingProcess = None
            self._pendingTrainJob = None
            if self._currentAutoSplitDir:
                shutil.rmtree(self._currentAutoSplitDir, ignore_errors=True)
                self._currentAutoSplitDir = None
            self.trainingDialog = None
            return
        command_preview = f"{sys.executable} " + " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
        self.trainingDialog.append_text(command_preview + "\n\n")

    def _handle_training_output(self):
        if not self.trainingProcess:
            return
        data = bytes(self.trainingProcess.readAllStandardOutput()).decode(
            errors="ignore"
        )
        if self.trainingDialog:
            self.trainingDialog.append_text(data)

    def _training_finished(self, exitCode, _exitStatus):
        if self.trainingDialog:
            message = self.get_str("trainingCompleted").format(exitCode)
            self.trainingDialog.append_text("\n" + message + "\n")
            self.trainingDialog.set_running(False)
        if self.trainingProcess:
            self.trainingProcess = None
        if self._currentAutoSplitDir:
            shutil.rmtree(self._currentAutoSplitDir, ignore_errors=True)
            self._currentAutoSplitDir = None
        job = self._pendingTrainJob
        self._pendingTrainJob = None
        if exitCode == 0 and job and self.auto_export_trained_model:
            self._maybe_start_auto_export(job)

    def _stop_training_process(self):
        if self.trainingProcess and self.trainingProcess.state() != QProcess.NotRunning:
            self.trainingProcess.terminate()
            proc = self.trainingProcess

            def kill_later():
                if proc.state() != QProcess.NotRunning:
                    proc.kill()

            QTimer.singleShot(5000, kill_later)
        if self.trainingDialog:
            self.trainingDialog.append_text("\n" + self.get_str("trainingStopped") + "\n")
            self.trainingDialog.set_running(False)

    def _training_dialog_closed(self, _result):
        self.trainingDialog = None

    def _maybe_start_auto_export(self, job):
        if self._exportProcess:
            logger.warning("Auto export already running, skip new request.")
            return
        repo_dir = job.get("repo_dir")
        config_path = job.get("config_path")
        output_dir = job.get("output_dir")
        if not (repo_dir and config_path and output_dir):
            return
        script_path = os.path.join(repo_dir, "tools", "export_model.py")
        if not os.path.exists(script_path):
            self._show_export_failure(
                f"tools/export_model.py not found under: {repo_dir}"
            )
            return
        checkpoint_prefix = self._find_latest_checkpoint(output_dir)
        if not checkpoint_prefix:
            self._show_export_failure(
                f"No checkpoint (.pdparams) found in: {output_dir}"
            )
            return
        inference_dir = self._next_inference_dir(output_dir)
        norm = lambda p: os.path.normpath(p).replace("\\", "/")
        args = [
            script_path,
            "-c",
            config_path,
            "-o",
            f"Global.checkpoints={norm(checkpoint_prefix)}",
            f"Global.save_inference_dir={norm(inference_dir)}",
        ]
        self._exportProcess = QProcess(self)
        self._exportProcess.setProcessChannelMode(QProcess.MergedChannels)
        self._exportProcess.setWorkingDirectory(repo_dir)
        self._exportProcess.readyReadStandardOutput.connect(
            self._handle_export_output
        )
        self._exportProcess.finished.connect(self._export_finished)
        self._pendingExportInfo = {
            "inference_dir": inference_dir,
            "output_dir": output_dir,
            "checkpoint": checkpoint_prefix,
        }
        self._exportLogBuffer = ""
        self._exportProcess.start(sys.executable, args)
        if not self._exportProcess.waitForStarted(5000):
            self._exportProcess = None
            self._pendingExportInfo = None
            self._show_export_failure("Unable to start export_model.py process.")
            return
        message = self.get_str("trainExporting")
        if self.trainingDialog:
            self.trainingDialog.append_text("\n" + message + "\n")
        self.statusBar().showMessage(message, 5000)

    def _handle_export_output(self):
        if not self._exportProcess:
            return
        data = bytes(self._exportProcess.readAllStandardOutput()).decode(
            errors="ignore"
        )
        self._exportLogBuffer += data
        if self.trainingDialog:
            self.trainingDialog.append_text(data)

    def _export_finished(self, exitCode, _status):
        info = self._pendingExportInfo
        self._exportProcess = None
        self._pendingExportInfo = None
        log_tail = (self._exportLogBuffer or "").strip()
        self._exportLogBuffer = ""
        if exitCode != 0:
            reason = log_tail or f"exit code {exitCode}"
            self._show_export_failure(reason)
            return
        if not info:
            return
        inference_dir = info.get("inference_dir")
        self._apply_exported_detection_model(inference_dir)

    def _show_export_failure(self, reason):
        logger.error("Auto export failed: %s", reason)
        message = self.get_str("trainExportFailed")
        if "{0}" in message:
            text = message.format(reason)
        else:
            text = "{}\n{}".format(message, reason)
        if self.trainingDialog:
            self.trainingDialog.append_text("\n" + text + "\n")
        QMessageBox.warning(self, "Warning", text)

    def _show_export_success(self, directory):
        message = self.get_str("trainExportSuccess")
        if "{0}" in message:
            text = message.format(directory)
        else:
            text = "{}\n{}".format(message, directory)
        if self.trainingDialog:
            self.trainingDialog.append_text("\n" + text + "\n")
        QMessageBox.information(self, "Information", text)

    def _apply_exported_detection_model(self, inference_dir):
        if not inference_dir or not os.path.isdir(inference_dir):
            self._show_export_failure(f"Inference directory not found: {inference_dir}")
            return
        valid, model_type = validate_model_dir(inference_dir)
        if not valid or (model_type and model_type != "det"):
            self._show_export_failure(
                f"Exported directory does not look like a detection model: {inference_dir}"
            )
            return
        prev_det = self.det_model_dir
        try:
            self.det_model_dir = inference_dir
            self.settings[SETTING_DET_MODEL_PATH] = inference_dir
            extra_dir = self.settings.get(SETTING_MODEL_SEARCH_DIR)
            parent_dir = os.path.dirname(inference_dir)
            if not extra_dir:
                self.settings[SETTING_MODEL_SEARCH_DIR] = parent_dir
            self.settings.save()
            self._reload_ocr_backends()
            self._show_export_success(inference_dir)
        except Exception as exc:
            logger.exception("Failed to apply exported detection model: %s", exc)
            self.det_model_dir = prev_det
            self._show_export_failure(str(exc))

    def _find_latest_checkpoint(self, output_dir):
        if not output_dir or not os.path.isdir(output_dir):
            return None
        preferred = ["best_accuracy", "best_model", "latest"]
        for name in preferred:
            candidate = os.path.join(output_dir, f"{name}.pdparams")
            if os.path.exists(candidate):
                return os.path.join(output_dir, name)
        mtimes = {}
        try:
            entries = os.listdir(output_dir)
        except OSError:
            return None
        for entry in entries:
            lower = entry.lower()
            if lower.endswith(".pdparams") or lower.endswith(".pdiparams"):
                prefix, _ = os.path.splitext(entry)
                full_path = os.path.join(output_dir, entry)
                try:
                    mtime = os.path.getmtime(full_path)
                except OSError:
                    continue
                mtimes[prefix] = max(mtimes.get(prefix, 0), mtime)
        if not mtimes:
            return None
        latest_prefix = max(mtimes.items(), key=lambda item: item[1])[0]
        return os.path.join(output_dir, latest_prefix)

    def _next_inference_dir(self, output_dir):
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = os.path.join(output_dir, f"inference_{timestamp}")
        candidate = base
        suffix = 1
        while os.path.exists(candidate):
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _prepare_dataset_from_current(self, source_dir, ratio="8:2:0"):
        split_root = tempfile.mkdtemp(prefix="ppocrlabel_split_")
        det_root = os.path.join(split_root, "det")
        rec_root = os.path.join(split_root, "rec")
        script_path = os.path.join(os.path.dirname(__file__), "gen_ocr_train_val_test.py")
        cmd = [
            sys.executable,
            script_path,
            "--datasetRootPath",
            source_dir,
            "--detRootPath",
            det_root,
            "--recRootPath",
            rec_root,
            "--trainValTestRatio",
            ratio,
        ]
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            shutil.rmtree(split_root, ignore_errors=True)
            raise RuntimeError(result.stderr or result.stdout or "split failed")
        return det_root, split_root

    def changeTextLayoutMode(self, mode):
        if mode == self.text_layout_mode:
            return
        if mode not in ["horizontal", "vertical"]:
            logger.warning("Unsupported text layout mode: %s", mode)
            return
        self.text_layout_mode = mode
        self.use_vertical_text = self.text_layout_mode == "vertical"
        self.settings[SETTING_TEXT_LAYOUT_MODE] = self.text_layout_mode
        self.settings.save()
        self._reload_ocr_backends()
        layout_label = (
            self.stringBundle.getString("textLayoutVertical")
            if self.use_vertical_text
            else self.stringBundle.getString("textLayoutHorizontal")
        )
        self.statusBar().showMessage(
            "{}: {}".format(
                self.stringBundle.getString("textLayoutMenu"), layout_label
            ),
            3000,
        )

    def changeReadingOrder(self, mode):
        if mode not in ("horizontal", "vertical"):
            return
        if mode == self.reading_mode:
            return
        self.reading_mode = mode
        self.settings[SETTING_READING_ORDER] = self.reading_mode
        self.settings.save()
        if hasattr(self, "readingModeActions"):
            action = self.readingModeActions.get(mode)
            if action:
                action.setChecked(True)
        label = (
            self.get_str("readingOrderVertical")
            if mode == "vertical"
            else self.get_str("readingOrderHorizontal")
        )
        self.statusBar().showMessage(
            self.get_str("readingOrderChanged").format(label), 3000
        )

    def chooseCustomModels(self):
        official_dir = self._get_official_model_dir()
        extra_dir = self.settings.get(SETTING_MODEL_SEARCH_DIR, official_dir)
        entries = discover_model_entries(official_dir, extra_dir)
        dialog = ModelSelectDialog(
            self,
            self.get_str,
            official_dir,
            extra_dir,
            entries,
            self.det_model_dir,
            self.rec_model_dir,
        )
        if not dialog.exec_():
            return
        det_path, rec_path, new_extra_dir = dialog.selected_paths()
        changed = False
        if (new_extra_dir or "") != (extra_dir or ""):
            self.settings[SETTING_MODEL_SEARCH_DIR] = new_extra_dir or ""
            changed = True
        new_det = det_path or None
        new_rec = rec_path or None
        if new_det != self.det_model_dir or new_rec != self.rec_model_dir:
            old_det = self.det_model_dir
            old_rec = self.rec_model_dir
            try:
                self.det_model_dir = new_det
                self.rec_model_dir = new_rec
                self._reload_ocr_backends()
                self.settings[SETTING_DET_MODEL_PATH] = new_det or ""
                self.settings[SETTING_REC_MODEL_PATH] = new_rec or ""
                changed = True
            except Exception as exc:
                logger.error("Failed to load custom model: %s", exc)
                self.det_model_dir = old_det
                self.rec_model_dir = old_rec
                QMessageBox.warning(
                    self, "Warning", self.get_str("customModelInvalid")
                )
                self._reload_ocr_backends()
                changed = False
        if changed:
            self.settings.save()
            QMessageBox.information(
                self, "Information", self.get_str("customModelApplied")
            )

    def _get_official_model_dir(self):
        home = Path.home()
        return os.path.join(str(home), ".paddlex", "official_models")

    def _read_inference_meta(self, directory):
        return read_inference_meta(directory)

    def _infer_model_name(self, directory, default_name):
        if not directory:
            return default_name
        info = self._read_inference_meta(directory) or {}
        name = info.get("model_name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return default_name

    def _build_proofread_payload(self):
        if not self.canvas.shapes:
            raise ValueError("no shapes to proofread")
        items = []
        context_segments = []
        for idx, shape in enumerate(self.canvas.shapes):
            bbox = [[int(p.x()), int(p.y())] for p in shape.points]
            text = shape.label or ""
            score = getattr(shape, "rec_score", 0.0) or 0.0
            entry = {
                "index": idx,
                "text": text,
                "score": float(score),
                "bbox": bbox,
            }
            if getattr(shape, "key_cls", None) and shape.key_cls != "None":
                entry["key_cls"] = shape.key_cls
            items.append(entry)
            if text:
                context_segments.append(text)
        payload = {
            "image_path": self.filePath,
            "language": self.lang,
            "context": "\n".join(context_segments),
            "items": items,
            "page_index": self.currIndex,
        }
        return payload

    def _request_json_proofreader(self, payload):
        response = requests.post(
            self.proofreader_endpoint,
            json=payload,
            timeout=self.proofreader_timeout,
        )
        response.raise_for_status()
        return response.json()

    def _compose_openai_prompt(self, payload):
        header = [
            "请充当OCR校对助手。根据下面的识别结果和上下文，找出缺失或错误的文字，并输出 JSON：",
            '{ "replacements": [ {"index": 0, "text": "替换后的文本", "score": 0.9} ] }',
            "index 对应识别结果的序号，从 0 开始，仅在需要修改时返回该条。",
            "不要编造坐标，若不确定请返回空数组。",
        ]
        context = payload.get("context") or ""
        if not context.strip():
            context = "(无上下文)"
        lines = []
        for item in payload.get("items", []):
            idx = item.get("index")
            text = item.get("text", "")
            score = item.get("score", 0)
            bbox = item.get("bbox", [])
            lines.append(f"{idx}: '{text}' (score={score}, bbox={bbox})")
        detail = "\n".join(lines)
        prompt = "\n".join(header)
        prompt += "\n上下文:\n" + context
        prompt += "\n识别结果:\n" + detail
        prompt += "\n请只返回 JSON。"
        return prompt

    def _extract_message_content(self, response_json):
        content = None
        if isinstance(response_json, dict):
            choices = response_json.get("choices")
            if choices:
                first_choice = choices[0] or {}
                message = first_choice.get("message") or {}
                content = message.get("content")
                if isinstance(content, list):
                    fragments = []
                    for chunk in content:
                        if isinstance(chunk, dict):
                            fragments.append(chunk.get("text", ""))
                        else:
                            fragments.append(str(chunk))
                    content = "".join(fragments)
            if content is None:
                output = response_json.get("output") or response_json.get("response")
                if isinstance(output, list) and output:
                    first = output[0]
                    if isinstance(first, dict):
                        segment = first.get("content") or first.get("text")
                        if isinstance(segment, list):
                            fragments = []
                            for chunk in segment:
                                if isinstance(chunk, dict):
                                    fragments.append(chunk.get("text", ""))
                                else:
                                    fragments.append(str(chunk))
                            content = "".join(fragments)
                        elif isinstance(segment, str):
                            content = segment
        if isinstance(content, str):
            return content.strip()
        return None

    def _extract_json_from_text(self, text):
        if not text:
            return None
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except Exception:
            pass
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = stripped[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                return None
        return None

    def _request_openai_proofreader(self, payload):
        prompt = self._compose_openai_prompt(payload)
        model_name = self.proofreader_model or "gpt-3.5-turbo"
        body = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an OCR proofreader. Return JSON replacements only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        headers = {"Content-Type": "application/json"}
        if self.proofreader_api_key:
            headers["Authorization"] = f"Bearer {self.proofreader_api_key}"
        response = requests.post(
            self.proofreader_endpoint,
            json=body,
            headers=headers,
            timeout=self.proofreader_timeout,
        )
        response.raise_for_status()
        response_json = response.json()
        content = self._extract_message_content(response_json)
        parsed = self._extract_json_from_text(content)
        if parsed is None:
            raise ValueError("Proofread response is not valid JSON.")
        return parsed

    def _normalize_proofread_changes(self, response_payload):
        if response_payload is None:
            return []
        if isinstance(response_payload, list):
            raw_entries = response_payload
        elif isinstance(response_payload, dict):
            raw_entries = response_payload.get("replacements")
            if raw_entries is None:
                raw_entries = response_payload.get("items")
            if raw_entries is None:
                suggestion = response_payload.get("text") or response_payload.get(
                    "suggested_text"
                )
                if (
                    isinstance(suggestion, str)
                    and len(suggestion) == len(self.canvas.shapes)
                ):
                    raw_entries = [
                        {"index": idx, "text": ch} for idx, ch in enumerate(suggestion)
                    ]
        else:
            raw_entries = []

        normalized = []
        if not isinstance(raw_entries, list):
            return normalized
        expected_len = len(self.canvas.shapes)
        for idx, entry in enumerate(raw_entries):
            target_idx = None
            text = None
            score = None
            if isinstance(entry, dict):
                target_idx = entry.get("index")
                text = entry.get("text")
                score = entry.get("score")
            else:
                text = str(entry) if entry is not None else None
            if target_idx is None and expected_len and len(raw_entries) == expected_len:
                target_idx = idx
            if text is None or target_idx is None:
                continue
            try:
                target_idx = int(target_idx)
            except (TypeError, ValueError):
                continue
            normalized.append(
                {"index": target_idx, "text": str(text), "score": score}
            )
        return normalized

    def _apply_proofread_suggestions(self, replacements):
        updated = []
        for change in replacements:
            index = change.get("index")
            new_text = change.get("text")
            if index is None or new_text is None:
                continue
            try:
                index = int(index)
            except (TypeError, ValueError):
                continue
            if index < 0 or index >= len(self.canvas.shapes):
                continue
            shape = self.canvas.shapes[index]
            old_text = shape.label or ""
            if old_text == new_text:
                continue
            shape.is_ai_corrected = True
            shape.label = new_text
            score = change.get("score")
            if score is not None:
                try:
                    shape.rec_score = float(score)
                except (TypeError, ValueError):
                    pass
            self._record_shape_history(
                shape,
                new_text,
                source="auto-proofread",
                previous_text=old_text,
                extra={"score": score},
            )
            self.singleLabel(shape)
            self._record_shape_history(
                shape,
                new_text,
                source="auto-proofread",
                previous_text=old_text,
                extra={"score": score} if score is not None else None,
            )
            updated.append({"index": index, "old": old_text, "new": new_text})
        if updated:
            self.setDirty()
            self.canvas.update()
        return updated

    def openManualProofreadDialog(self):
        if not self.canvas.shapes:
            QMessageBox.information(
                self, "Information", self.get_str("manualProofreadNoBoxes")
            )
            return
        shape = self._get_single_active_shape()
        if shape is None:
            shape = self._first_manual_proofread_shape()
        if shape is None:
            QMessageBox.information(
                self, "Information", self.get_str("manualProofreadNeedSelection")
            )
            return
        self._focus_shape_selection(shape)
        running = True
        current = shape
        while running and current is not None:
            proceed, direction = self._run_manual_proofread_session(current)
            if not proceed:
                break
            if direction == 0:
                break
            neighbor = self._get_neighbor_shape_for_manual(current, direction)
            if neighbor is None:
                break
            current = neighbor
            self._focus_shape_selection(current)

    def _build_shape_preview_pixmap(self, shape):
        if not self.filePath or not os.path.exists(self.filePath):
            return None
        img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None
        box = np.array([[int(p.x()), int(p.y())] for p in shape.points], dtype=np.int32)
        if box.size == 0:
            return None
        padded = boxPad(box, img.shape, pad=2)
        try:
            crop = get_rotate_crop_image(img, padded.astype(np.float32))
        except Exception:
            crop = None
        if crop is None:
            return None
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        height, width, channel = crop.shape
        bytes_per_line = channel * width
        qimg = QImage(crop.data, width, height, bytes_per_line, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg.copy())

    def _latest_history_stage(self, history):
        if not history:
            return ""
        for entry in reversed(history):
            stage = entry.get("stage")
            if stage:
                return stage
        return ""

    def _gather_stage_options(self, *extra):
        options = list(self._review_stage_options)
        for stage in extra:
            if stage and stage not in options:
                options.append(stage)
        return options

    def _remember_stage(self, stage):
        if not stage:
            return
        if stage not in self._review_stage_options:
            self._review_stage_options.append(stage)

    def _ensure_shape_history(self, shape):
        if not hasattr(shape, "history") or getattr(shape, "history") is None:
            shape.history = []
        return shape.history

    def _ingest_lexicon_text(self, text):
        if not text:
            return
        if getattr(self, "lexicon_manager", None):
            try:
                self.lexicon_manager.ingest_text(text)
            except Exception as exc:
                logger.warning("Failed to update lexicon: %s", exc)

    def _record_shape_history(
        self,
        shape,
        text,
        source="manual",
        previous_text="",
        stage=None,
        extra=None,
    ):
        history = self._ensure_shape_history(shape)
        entry = {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "type": source,
            "text": text,
            "previous_text": previous_text,
            "stage": stage,
        }
        if extra:
            entry.update(extra)
        history.append(entry)
        shape.history = history
    def _first_manual_proofread_shape(self):
        for shape in self.canvas.shapes:
            if shape.line_color != DEFAULT_LOCK_COLOR:
                return shape
        return self.canvas.shapes[0] if self.canvas.shapes else None

    def _focus_shape_selection(self, shape):
        if not shape:
            return
        try:
            self.canvas.selectShapes([shape])
        except Exception:
            pass
        item = self.shapesToItems.get(shape)
        if item:
            self.labelList.setCurrentItem(item)
            self.labelList.scrollToItem(item)
            index = self.labelList.indexFromItem(item).row()
            if 0 <= index < self.indexList.count():
                self.indexList.setCurrentRow(index)
        box_item = self.shapesToItemsbox.get(shape)
        if box_item:
            self.BoxList.setCurrentItem(box_item)
            self.BoxList.scrollToItem(box_item)

    def _run_manual_proofread_session(self, shape):
        pixmap = self._build_shape_preview_pixmap(shape)
        if pixmap is None:
            QMessageBox.warning(
                self, "Warning", self.get_str("manualProofreadNoImage")
            )
        history = copy.deepcopy(getattr(shape, "history", []))
        last_stage = self._latest_history_stage(history)
        stage_options = self._gather_stage_options(last_stage)
        self.lineProofDialog.prepare_for_shape()
        self.lineProofDialog.set_history(history)
        self.lineProofDialog.set_pixmap(pixmap)
        self.lineProofDialog.set_text(shape.label or "")
        self.lineProofDialog.set_stage_options(stage_options, last_stage or "")
        accepted = self.lineProofDialog.exec_()
        direction = self.lineProofDialog.take_navigation_direction()
        if not accepted and direction == 0:
            return False, 0
        self._apply_manual_proofread_result(shape)
        return True, direction

    def _apply_manual_proofread_result(self, shape):
        new_text, stage = self.lineProofDialog.get_result()
        prev_text = shape.label or ""
        text_changed = new_text != prev_text
        if text_changed:
            shape.label = new_text
            shape.is_ai_corrected = False
            self.singleLabel(shape)
        if stage:
            self._remember_stage(stage)
        if text_changed or stage:
            self._record_shape_history(
                shape,
                new_text if new_text is not None else "",
                source="manual",
                previous_text=prev_text,
                stage=stage or None,
            )
            self.setDirty()
            self.canvas.update()

    def _get_neighbor_shape_for_manual(self, current_shape, direction):
        if not self.canvas.shapes:
            return None
        try:
            index = self.canvas.shapes.index(current_shape)
        except ValueError:
            return None
        step = -1 if direction < 0 else 1
        idx = index + step
        while 0 <= idx < len(self.canvas.shapes):
            candidate = self.canvas.shapes[idx]
            if candidate.line_color != DEFAULT_LOCK_COLOR or candidate == current_shape:
                return candidate
            idx += step
        return None

    def addSelectedToLexicon(self):
        if not getattr(self, "lexicon_manager", None):
            QMessageBox.warning(self, "Warning", self.get_str("lexiconNotReady"))
            return
        if not self.canvas.shapes:
            QMessageBox.information(self, "Information", self.get_str("autoProofreadNoBoxes"))
            return
        targets = list(self.canvas.selectedShapes)
        if not targets:
            QMessageBox.information(self, "Information", self.get_str("lexiconNeedSelection"))
            return
        texts = []
        for shape in targets:
            text = (shape.label or "").strip()
            if text:
                texts.append(text)
        if not texts:
            QMessageBox.information(self, "Information", self.get_str("lexiconNoText"))
            return
        before_words = len(self.lexicon_manager.word_set)
        before_corpus = len(self.lexicon_manager.corpus_lines)
        for text in texts:
            self._ingest_lexicon_text(text)
        added_words = len(self.lexicon_manager.word_set) - before_words
        added_corpus = len(self.lexicon_manager.corpus_lines) - before_corpus
        if self.lang == "ch":
            msg = f"已加入词典 {max(added_words,0)} 条，语料 {max(added_corpus,0)} 条。"
        else:
            msg = f"Added {max(added_words,0)} lexicon entries, {max(added_corpus,0)} sentences."
        QMessageBox.information(self, "Information", msg)

    def addPageToLexicon(self):
        if not getattr(self, "lexicon_manager", None):
            QMessageBox.warning(self, "Warning", self.get_str("lexiconNotReady"))
            return
        if not self.canvas.shapes:
            QMessageBox.information(self, "Information", self.get_str("autoProofreadNoBoxes"))
            return
        texts = []
        for shape in self.canvas.shapes:
            text = (shape.label or "").strip()
            if text:
                texts.append(text)
        if not texts:
            QMessageBox.information(self, "Information", self.get_str("lexiconNoText"))
            return
        before_words = len(self.lexicon_manager.word_set)
        before_corpus = len(self.lexicon_manager.corpus_lines)
        for text in texts:
            self._ingest_lexicon_text(text)
        added_words = len(self.lexicon_manager.word_set) - before_words
        added_corpus = len(self.lexicon_manager.corpus_lines) - before_corpus
        if self.lang == "ch":
            msg = f"已加入词典 {max(added_words,0)} 条，语料 {max(added_corpus,0)} 条。"
        else:
            msg = f"Added {max(added_words,0)} lexicon entries, {max(added_corpus,0)} sentences."
        QMessageBox.information(self, "Information", msg)

    def autoProofread(self):
        if not self.canvas.shapes:
            QMessageBox.information(self, "Information", self.get_str("autoProofreadNoBoxes"))
            return
        if not self.proofreader_endpoint:
            QMessageBox.warning(self, "Warning", self.get_str("autoProofreadNoEndpoint"))
            return
        try:
            payload = self._build_proofread_payload()
        except ValueError:
            QMessageBox.information(self, "Information", self.get_str("autoProofreadNoBoxes"))
            return
        logger.info("Sending proofread request to %s", self.proofreader_endpoint)
        self.statusBar().showMessage(self.get_str("autoProofreadRunning"))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if self.proofreader_style == "openai":
                data = self._request_openai_proofreader(payload)
            else:
                data = self._request_json_proofreader(payload)
        except requests.RequestException as exc:
            logger.warning("Proofread request failed: %s", exc)
            QMessageBox.warning(
                self,
                "Warning",
                self.get_str("autoProofreadFailed").format(error=str(exc)),
            )
            return
        except ValueError as exc:
            logger.warning("Proofread response parse failed: %s", exc)
            QMessageBox.warning(
                self,
                "Warning",
                self.get_str("autoProofreadFailed").format(error=str(exc)),
            )
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
        replacements = self._normalize_proofread_changes(data)
        update_infos = self._apply_proofread_suggestions(replacements)
        if update_infos:
            change_lines = [
                self.get_str("autoProofreadChangeLine").format(
                    index=info["index"],
                    old=info["old"],
                    new=info["new"],
                )
                for info in update_infos
            ]
            max_lines = 10
            preview = "\n".join(change_lines[:max_lines])
            suffix = ""
            if len(change_lines) > max_lines:
                suffix = "\n" + self.get_str("autoProofreadAppliedMore").format(
                    remaining=len(change_lines) - max_lines
                )
            QMessageBox.information(
                self,
                "Information",
                self.get_str("autoProofreadApplied").format(
                    count=len(update_infos)
                )
                + ("\n" + preview if preview else "")
                + suffix,
            )
        else:
            QMessageBox.information(
                self, "Information", self.get_str("autoProofreadNoChange")
            )

    def reRecognition(self):
        img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), cv2.IMREAD_COLOR)
        if self.canvas.shapes:
            self.result_dic = []
            self.result_dic_locked = (
                []
            )  # result_dic_locked stores the ocr result of self.canvas.lockedShapes
            rec_flag = 0
            for shape in self.canvas.shapes:
                shape.is_ai_corrected = False
                old_text = shape.label or ""
                box = [[int(p.x()), int(p.y())] for p in shape.points]
                kie_cls = shape.key_cls

                if len(box) > 4:
                    box = self.gen_quad_from_poly(np.array(box))
                assert len(box) == 4

                img_crop = get_rotate_crop_image(img, np.array(box, np.float32))
                if img_crop is None:
                    msg = (
                        "Can not recognise the detection box in "
                        + self.filePath
                        + ". Please change manually"
                    )
                    QMessageBox.information(self, "Information", msg)
                    return
                result = self._decode_with_lexicon(self.text_recognizer.predict(img_crop)[0])
                shape.char_candidates = result.get("char_candidates", []) or []
                self._store_shape_candidates(shape, box, shape.char_candidates)
                storage = [(result["rec_text"], result["rec_score"])]
                if result["rec_text"] != "":
                    shape.rec_score = float(result.get("rec_score") or 0.0)
                    if shape.line_color == DEFAULT_LOCK_COLOR:
                        shape.label = result["rec_text"]
                        storage.insert(0, box)
                        if self.kie_mode:
                            storage.append(kie_cls)
                        self.result_dic_locked.append(storage)
                    else:
                        storage.insert(0, box)
                        if self.kie_mode:
                            storage.append(kie_cls)
                        self.result_dic.append(storage)
                else:
                    logger.warning("Can not recognise the box")
                    shape.rec_score = 0.0
                    if shape.line_color == DEFAULT_LOCK_COLOR:
                        shape.label = result["rec_text"]
                        if self.kie_mode:
                            self.result_dic_locked.append(
                                [box, (self.noLabelText, 0), kie_cls]
                            )
                        else:
                            self.result_dic_locked.append([box, (self.noLabelText, 0)])
                    else:
                        if self.kie_mode:
                            self.result_dic.append(
                                [box, (self.noLabelText, 0), kie_cls]
                            )
                        else:
                            self.result_dic.append([box, (self.noLabelText, 0)])
            if not shape.char_candidates:
                shape.char_candidates = []
            self._store_shape_confidence(shape, box)
            if (shape.label or "") != old_text:
                self._record_shape_history(
                    shape,
                    shape.label or "",
                    source="recognition",
                    previous_text=old_text,
                )
            try:
                if (
                    self.noLabelText == shape.label
                    or result["rec_text"] == shape.label
                ):
                    logger.debug("label no change")
                else:
                    rec_flag += 1
            except IndexError as e:
                logger.warning("Can not recognise the box")
            if (len(self.result_dic) > 0 and rec_flag > 0) or self.canvas.lockedShapes:
                self.canvas.isInTheSameImage = True
                self.saveFile(mode="Auto")
                self.loadFile(self.filePath, isAdjustScale=False)
                self.canvas.isInTheSameImage = False
                self.setDirty()
            elif len(self.result_dic) == len(self.canvas.shapes) and rec_flag == 0:
                if self.lang == "ch":
                    QMessageBox.information(self, "Information", "识别结果保持一致！")
                else:
                    QMessageBox.information(
                        self, "Information", "The recognition result remains unchanged!"
                    )
            else:
                logger.warning("Can not recognise in %s", self.filePath)
        else:
            QMessageBox.information(self, "Information", "Draw a box!")

    def singleRerecognition(self):
        img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), cv2.IMREAD_COLOR)
        for shape in self.canvas.selectedShapes:
            shape.is_ai_corrected = False
            old_text = shape.label or ""
            box = [[int(p.x()), int(p.y())] for p in shape.points]
            if len(box) > 4:
                box = self.gen_quad_from_poly(np.array(box))
            assert len(box) == 4
            img_crop = get_rotate_crop_image(img, np.array(box, np.float32))
            if img_crop is None:
                msg = (
                    "Can not recognise the detection box in "
                    + self.filePath
                    + ". Please change manually"
                )
                QMessageBox.information(self, "Information", msg)
                return
                result = self._decode_with_lexicon(self.text_recognizer.predict(img_crop)[0])
                score = float(result.get("rec_score") or 0.0)
                shape.char_candidates = result.get("char_candidates", []) or []
            self._store_shape_candidates(shape, box, shape.char_candidates)
            storage = [(result["rec_text"], result["rec_score"])]
            if result["rec_text"] != "":
                shape.rec_score = score
                storage.insert(0, box)
                storage.append(result["rec_text"])
                if self.kie_mode:
                    storage.append(shape.key_cls)
                logger.debug("result in reRec is %s", result)
                if result["rec_text"] == shape.label:
                    logger.debug("label no change")
                else:
                    shape.label = result["rec_text"]
            else:
                logger.warning("Can not recognise the box")
                if self.noLabelText == shape.label:
                    logger.debug("label no change")
                else:
                    shape.label = self.noLabelText
                shape.rec_score = 0.0
            if not shape.char_candidates:
                shape.char_candidates = []
            self._store_shape_confidence(shape, box)
            self.singleLabel(shape)
            self.setDirty()
            if (shape.label or "") != old_text:
                self._record_shape_history(
                    shape,
                    shape.label or "",
                    source="single-recognition",
                    previous_text=old_text,
                )

    def TableRecognition(self):
        """
        Table Recognition
        """
        from tablepyxl import tablepyxl

        import time

        start = time.time()
        img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), cv2.IMREAD_COLOR)
        res = self.table_ocr.predict(img)[0]

        table_rec_excel_dir = self.lastOpenDir + "/tableRec_excel_output/"
        os.makedirs(table_rec_excel_dir, exist_ok=True)
        filename, _ = os.path.splitext(os.path.basename(self.filePath))

        excel_path = table_rec_excel_dir + "{}.xlsx".format(filename)

        if res is None:
            msg = (
                "Can not recognise the table in "
                + self.filePath
                + ". Please change manually"
            )
            QMessageBox.information(self, "Information", msg)
            # create an empty excel
            tablepyxl.document_to_xl("", excel_path)
            return

        # save res
        # ONLY SUPPORT ONE TABLE in one image
        has_table_flag = False
        for region in res["table_res_list"]:
            if region["table_ocr_pred"]["rec_boxes"] is None:
                msg = (
                    "Can not recognise the detection box in "
                    + self.filePath
                    + ". Please change manually"
                )
                QMessageBox.information(self, "Information", msg)
                # create an empty excel
                tablepyxl.document_to_xl("", excel_path)
                return
            has_table_flag = True
            # save table ocr result on PPOCRLabel
            # clear all old annotations before saving result
            self.itemsToShapes.clear()
            self.shapesToItems.clear()
            self.itemsToShapesbox.clear()
            self.shapesToItemsbox.clear()
            self.labelList.clear()
            self.indexList.clear()
            self.BoxList.clear()
            self.result_dic = []
            self.result_dic_locked = []

            shapes = []
            result_len = len(region["table_ocr_pred"]["rec_boxes"])
            order_index = 0
            for i in range(result_len):
                bbox = region["table_ocr_pred"]["rec_boxes"][i]
                rec_text = region["table_ocr_pred"]["rec_texts"][i]

                rext_bbox = [
                    [bbox[0], bbox[1]],
                    [bbox[2], bbox[1]],
                    [bbox[2], bbox[3]],
                    [bbox[0], bbox[3]],
                ]

                # save bbox to shape
                shape = Shape(
                    label=rec_text, line_color=DEFAULT_LINE_COLOR, key_cls=None
                )
                for point in rext_bbox:
                    x, y = point
                    # Ensure the labels are within the bounds of the image.
                    # If not, fix them.
                    x, y, _ = self.canvas.snapPointToCanvas(x, y)
                    shape.addPoint(QPointF(x, y))
                shape.difficult = False
                shape.idx = order_index
                order_index += 1
                # shape.locked = False
                shape.close()
                self.addLabel(shape)
                shapes.append(shape)
            self.setDirty()
            self.canvas.loadShapes(shapes)

            # save HTML result to excel
            try:
                tablepyxl.document_to_xl(region["pred_html"], excel_path)
            except Exception as e:
                logger.error(
                    "Can not save excel file. \nError: %s",
                    e,
                )
            break

        if not has_table_flag:
            msg = (
                "Can not recognise the table in "
                + self.filePath
                + ". Please change manually"
            )
            QMessageBox.information(self, "Information", msg)
            # create an empty excel
            try:
                tablepyxl.document_to_xl("", excel_path)
            except AttributeError:  # 如果 tablepyxl 报错，改用 openpyxl
                wb = openpyxl.Workbook()
                wb.save(excel_path)
            return

        # automatically open excel annotation file
        if platform.system() == "Windows":
            try:
                import win32com.client
            except Exception as e:
                logger.error(
                    "CANNOT OPEN .xlsx. It could be one of the following reasons: "
                    "Only support Windows | No python win32com. Error: %s",
                    e,
                )

            try:
                xl = win32com.client.Dispatch("Excel.Application")
                xl.Visible = True
                xl.Workbooks.Open(excel_path)
                # excelEx = "You need to show the excel executable at this point"
                # subprocess.Popen([excelEx, excel_path])

                # os.startfile(excel_path)
            except Exception as e:
                logger.error(
                    "CANNOT OPEN .xlsx. It could be the following reasons: "
                    ".xlsx is not existed. Error: %s",
                    e,
                )
        else:
            os.system("open " + os.path.normpath(excel_path))

        logger.info("Table recognition time cost: %s", time.time() - start)

    def cellreRecognition(self):
        """
        re-recognise text in a cell
        """
        img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), cv2.IMREAD_COLOR)
        for shape in self.canvas.selectedShapes:
            box = [[int(p.x()), int(p.y())] for p in shape.points]

            if len(box) > 4:
                box = self.gen_quad_from_poly(np.array(box))
            assert len(box) == 4

            # pad around bbox for better text recognition accuracy
            _box = boxPad(box, img.shape, 6)
            img_crop = get_rotate_crop_image(img, np.array(_box, np.float32))
            if img_crop is None:
                msg = (
                    "Can not recognise the detection box in "
                    + self.filePath
                    + ". Please change manually"
                )
                QMessageBox.information(self, "Information", msg)
                return

            # merge the text result in the cell
            texts = ""
            probs = 0.0  # the probability of the cell is average prob of every text box in the cell
            det_res = self.text_detector.predict(img_crop)[0]
            bboxes = det_res["dt_polys"].tolist()
            if len(bboxes) > 0:
                bboxes.reverse()  # top row text at first
                for _bbox in bboxes:
                    patch = get_rotate_crop_image(img_crop, np.array(_bbox, np.float32))
                    rec_res = self._decode_with_lexicon(self.text_recognizer.predict(patch)[0])
                    text = rec_res["rec_text"]
                    if text != "":
                        texts += text + (
                            "" if text[0].isalpha() else " "
                        )  # add space between english word
                        probs += rec_res["rec_score"]
                probs = probs / len(bboxes)
            result = [(texts.strip(), probs)]

            if result[0][0] != "":
                result.insert(0, box)
                logger.debug("result in reRec is %s", result)
                if result[1][0] == shape.label:
                    logger.debug("label no change")
                else:
                    shape.label = result[1][0]
                shape.rec_score = float(probs)
            else:
                logger.warning("Can not recognise the box")
                if self.noLabelText == shape.label:
                    logger.debug("label no change")
                else:
                    shape.label = self.noLabelText
                shape.rec_score = 0.0
            self._store_shape_confidence(shape, box)
            self.singleLabel(shape)
            self.setDirty()

    def exportJSON(self):
        """
        export PPLabel and CSV to JSON (PubTabNet)
        """

        # automatically save annotations
        self.saveFilestate()
        self.savePPlabel(mode="auto")

        # load box annotations
        labeldict = {}
        if not os.path.exists(self.PPlabelpath):
            msg = "ERROR, Can not find Label.txt"
            QMessageBox.information(self, "Information", msg)
            return
        else:
            with open(self.PPlabelpath, "r", encoding="utf-8") as f:
                data = f.readlines()
                for each in data:
                    file, label = each.split("\t")
                    if label:
                        label = label.replace("false", "False")
                        label = label.replace("true", "True")
                        label = label.replace("null", "None")
                        labeldict[file] = eval(label)
                    else:
                        labeldict[file] = []

        # read table recognition output
        TableRec_excel_dir = os.path.join(self.lastOpenDir, "tableRec_excel_output")

        # save txt
        fid = open("{}/gt.txt".format(self.lastOpenDir), "w", encoding="utf-8")
        for image_path in labeldict.keys():
            # load csv annotations
            filename, _ = os.path.splitext(os.path.basename(image_path))
            csv_path = os.path.join(TableRec_excel_dir, filename + ".xlsx")
            if not os.path.exists(csv_path):
                continue

            excel = openpyxl.load_workbook(csv_path, data_only=True)
            sheet0 = excel.worksheets[0]  # only sheet 0
            merged_cells = sheet0.merged_cells.ranges  # list of merged cell ranges

            html_list = [["td"] * sheet0.max_column for i in range(sheet0.max_row)]

            for merged in merged_cells:
                # Convert merged cell range to start row, end row, start col, end col
                sr = merged.min_row - 1
                er = merged.max_row - 1
                sc = merged.min_col - 1
                ec = merged.max_col - 1
                html_list = expand_list((sr, er, sc, ec), html_list)

            token_list = convert_token(html_list)

            # load box annotations
            cells = []
            for anno in labeldict[image_path]:
                tokens = list(anno["transcription"])
                cells.append({"tokens": tokens, "bbox": anno["points"]})

            # 构造标注信息
            html = {"structure": {"tokens": token_list}, "cells": cells}
            d = {"filename": os.path.basename(image_path), "html": html}
            # 重构HTML
            d["gt"] = rebuild_html_from_ppstructure_label(d)
            fid.write("{}\n".format(json.dumps(d, ensure_ascii=False)))

        # convert to PP-Structure label format
        fid.close()
        msg = "JSON successfully saved in {}/gt.txt".format(self.lastOpenDir)
        QMessageBox.information(self, "Information", msg)

    def autolcm(self):
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        self.panel = QLabel()
        self.panel.setText(self.stringBundle.getString("choseModelLg"))
        self.panel.setAlignment(Qt.AlignLeft)
        self.comboBox = QComboBox()
        self.comboBox.setObjectName("comboBox")
        self.comboBox.addItems(
            ["Chinese & English", "English", "French", "German", "Korean", "Japanese"]
        )
        vbox.addWidget(self.panel)
        vbox.addWidget(self.comboBox)
        self.dialog = QDialog()
        self.dialog.resize(300, 100)
        self.okBtn = QPushButton(self.stringBundle.getString("ok"))
        self.cancelBtn = QPushButton(self.stringBundle.getString("cancel"))

        self.okBtn.clicked.connect(self.modelChoose)
        self.cancelBtn.clicked.connect(self.cancel)
        self.dialog.setWindowTitle(self.stringBundle.getString("choseModelLg"))

        hbox.addWidget(self.okBtn)
        hbox.addWidget(self.cancelBtn)

        vbox.addWidget(self.panel)
        vbox.addLayout(hbox)
        self.dialog.setLayout(vbox)
        self.dialog.setWindowModality(Qt.ApplicationModal)
        self.dialog.exec_()
        if self.filePath:
            self.AutoRecognition.setEnabled(True)
            self.actions.AutoRec.setEnabled(True)
            self.actions.AutoRecCurrent.setEnabled(True)

    def modelChoose(self):
        current_text = self.comboBox.currentText()
        logger.debug("Model selected: %s", current_text)
        lg_idx = {
            "Chinese & English": "ch",
            "English": "en",
            "French": "french",
            "German": "german",
            "Korean": "korean",
            "Japanese": "japan",
        }
        if current_text in lg_idx:
            choose_lang = lg_idx[current_text]
            self._reload_ocr_backends(lang=choose_lang)
        else:
            logger.error("Invalid language selection")
        self.dialog.close()

    def cancel(self):
        self.dialog.close()

    def loadFilestate(self, saveDir):
        self.fileStatepath = saveDir + "/fileState.txt"
        self.fileStatedict = {}
        if not os.path.exists(self.fileStatepath):
            f = open(self.fileStatepath, "w", encoding="utf-8")
        else:
            with open(self.fileStatepath, "r", encoding="utf-8") as f:
                states = f.readlines()
                for each in states:
                    file, state = each.split("\t")
                    self.fileStatedict[self.getImglabelidx(file)] = 1
                self.actions.saveLabel.setEnabled(True)
                self.actions.saveRec.setEnabled(True)
                self.actions.exportFullText.setEnabled(True)
                self.actions.exportJSON.setEnabled(True)

    def saveFilestate(self):
        with open(self.fileStatepath, "w", encoding="utf-8") as f:
            for key in self.fileStatedict:
                f.write(key + "\t")
                f.write(str(self.fileStatedict[key]) + "\n")

    def loadLabelFile(self, labelpath):
        labeldict = {}
        if not os.path.exists(labelpath):
            f = open(labelpath, "w", encoding="utf-8")

        else:
            with open(labelpath, "r", encoding="utf-8") as f:
                data = f.readlines()
                for each in data:
                    file, label = each.split("\t")
                    if label:
                        label = label.replace("false", "False")
                        label = label.replace("true", "True")
                        label = label.replace("null", "None")
                        labeldict[file] = eval(label)
                    else:
                        labeldict[file] = []
        return labeldict

    def savePPlabel(self, mode="Manual"):
        savedfile = [self.getImglabelidx(i) for i in self.fileStatedict.keys()]
        with open(self.PPlabelpath, "w", encoding="utf-8") as f:
            for key in self.PPlabel:
                if key in savedfile and self.PPlabel[key] != []:
                    f.write(key + "\t")
                    f.write(json.dumps(self.PPlabel[key], ensure_ascii=False) + "\n")

        if mode == "Manual":
            if self.lang == "ch":
                msg = "已将检查过的图片标签保存在 " + self.PPlabelpath + " 文件中"
            else:
                msg = "Images that have been checked are saved in " + self.PPlabelpath
            QMessageBox.information(self, "Information", msg)

    def saveCacheLabel(self):
        with open(self.Cachelabelpath, "w", encoding="utf-8") as f:
            for key in self.Cachelabel:
                f.write(key + "\t")
                f.write(json.dumps(self.Cachelabel[key], ensure_ascii=False) + "\n")

    def saveLabelFile(self):
        self.saveFilestate()
        self.savePPlabel()

    def saveRecResult(self):
        if {} in [self.PPlabelpath, self.PPlabel, self.fileStatedict]:
            QMessageBox.information(self, "Information", "Check the image first")
            return

        base_dir = os.path.dirname(self.PPlabelpath)
        rec_gt_dir = base_dir + "/rec_gt.txt"
        crop_img_dir = base_dir + "/crop_img/"
        ques_img = []
        if not os.path.exists(crop_img_dir):
            os.mkdir(crop_img_dir)

        with open(rec_gt_dir, "w", encoding="utf-8") as f:
            for key in self.fileStatedict:
                labels = self._get_labels_for_image(key)
                if not labels:
                    continue
                try:
                    img_path = os.path.dirname(base_dir) + "/" + key
                    img = cv2.imdecode(
                        np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR
                    )
                    for i, label in enumerate(labels):
                        if label["difficult"]:
                            continue
                        img_crop = get_rotate_crop_image(
                            img, np.array(label["points"], np.float32)
                        )
                        img_name = (
                            os.path.splitext(os.path.basename(idx))[0]
                            + "_crop_"
                            + str(i)
                            + ".jpg"
                        )
                        cv2.imencode(".jpg", img_crop)[1].tofile(
                            crop_img_dir + img_name
                        )
                        f.write("crop_img/" + img_name + "\t")
                        f.write(label["transcription"] + "\n")
                except KeyError as e:
                    pass
                except Exception as e:
                    ques_img.append(key)
                    logger.exception("Error processing image %s: %s", key, e)
        if ques_img:
            QMessageBox.information(
                self,
                "Information",
                "The following images can not be saved, please check the image path and labels.\n"
                + "".join(str(i) + "\n" for i in ques_img),
            )
        QMessageBox.information(
            self,
            "Information",
            "Cropped images have been saved in " + str(crop_img_dir),
        )

    def exportFullText(self):
        if not self.PPlabel or not self.mImgList:
            QMessageBox.information(
                self, "Information", self.get_str("exportFullTextEmpty")
            )
            return

        base_dir = os.path.dirname(self.PPlabelpath)
        default_path = os.path.join(base_dir, "full_text.txt")
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.get_str("exportFullText"),
            default_path,
            "Text Files (*.txt)",
        )
        if not save_path:
            return

        lines = []
        for img_path in self.mImgList:
            labels = self._get_labels_for_image(img_path) or []
            if not labels:
                continue
            for label in labels:
                if label.get("difficult"):
                    continue
                text = label.get("transcription", "")
                if text:
                    lines.append(text)
            lines.append("")  # page separator

        while lines and lines[-1] == "":
            lines.pop()

        if not lines:
            QMessageBox.information(
                self, "Information", self.get_str("exportFullTextEmpty")
            )
            return

        with open(save_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        QMessageBox.information(
            self,
            "Information",
            self.get_str("exportFullTextSuccess").format(save_path),
        )

    def speedChoose(self):
        if self.labelDialogOption.isChecked():
            self.canvas.newShape.disconnect()
            self.canvas.newShape.connect(partial(self.newShape, True))

        else:
            self.canvas.newShape.disconnect()
            self.canvas.newShape.connect(partial(self.newShape, False))

    def autoSaveFunc(self):
        if self.autoSaveOption.isChecked():
            self.autoSaveNum = 1  # Real auto_Save
            try:
                self.saveLabelFile()
            except Exception:
                pass
            logger.info(
                "The program will automatically save once after confirming an image"
            )
        else:
            self.autoSaveNum = 5  # Used for backup
            logger.info(
                "The program will automatically save once after confirming 5 images (default)"
            )

    def change_box_key(self):
        if not self.kie_mode:
            return
        key_text, _ = self.keyDialog.popUp(self.key_previous_text)
        if key_text is None:
            return
        self.key_previous_text = key_text
        for shape in self.canvas.selectedShapes:
            shape.key_cls = key_text
            if not self.keyList.findItemsByLabel(key_text):
                item = self.keyList.createItemFromLabel(key_text)
                self.keyList.addItem(item)
                rgb = self._get_rgb_by_label(key_text, self.kie_mode)
                self.keyList.setItemLabel(item, key_text, rgb)

            self._update_shape_color(shape)
            self.keyDialog.addLabelHistory(key_text)

        # save changed shape
        self.setDirty()

    def undoShapeEdit(self):
        self.canvas.restoreShape()
        self.labelList.clear()
        self.indexList.clear()
        self.BoxList.clear()
        self.loadShapes(self.canvas.shapes)
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)

    def loadShapes(self, shapes, replace=True):
        self._noSelectionSlot = True
        for shape in shapes:
            self.addLabel(shape)
        self.labelList.clearSelection()
        self.indexList.clearSelection()
        self._noSelectionSlot = False
        self.canvas.loadShapes(shapes, replace=replace)
        logger.debug("loadShapes")

    def lockSelectedShape(self):
        """lock the selected shapes.

        Add self.selectedShapes to lock self.canvas.lockedShapes,
        which holds the ratio of the four coordinates of the locked shapes
        to the width and height of the image
        """
        width, height = self.image.width(), self.image.height()

        def format_shape(s):
            return dict(
                label=s.label,  # str
                line_color=s.line_color.getRgb(),
                fill_color=s.fill_color.getRgb(),
                ratio=[
                    [int(p.x()) / width, int(p.y()) / height] for p in s.points
                ],  # QPonitF
                difficult=s.difficult,  # bool
                key_cls=s.key_cls,  # bool
            )

        # lock
        if len(self.canvas.lockedShapes) == 0:
            for s in self.canvas.selectedShapes:
                s.line_color = DEFAULT_LOCK_COLOR
                s.locked = True
            shapes = [format_shape(shape) for shape in self.canvas.selectedShapes]
            trans_dic = []
            for box in shapes:
                trans_dict = {
                    "transcription": box["label"],
                    "ratio": box["ratio"],
                    "difficult": box["difficult"],
                }
                if self.kie_mode:
                    trans_dict.update({"key_cls": box["key_cls"]})
                trans_dic.append(trans_dict)
            self.canvas.lockedShapes = trans_dic
            self.actions.save.setEnabled(True)

        # unlock
        else:
            for s in self.canvas.shapes:
                s.line_color = DEFAULT_LINE_COLOR
            self.canvas.lockedShapes = []
            self.result_dic_locked = []
            self.setDirty()
            self.actions.save.setEnabled(True)

    def expandSelectedShape(self):
        img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), cv2.IMREAD_COLOR)
        for shape in self.canvas.selectedShapes:
            box = [[int(p.x()), int(p.y())] for p in shape.points]
            if len(box) > 4:
                box = self.gen_quad_from_poly(np.array(box))
            assert len(box) == 4
            box = boxPad(box, img.shape, 3)
            shape.points = [
                QPointF(box[0][0], box[0][1]),
                QPointF(box[1][0], box[1][1]),
                QPointF(box[2][0], box[2][1]),
                QPointF(box[3][0], box[3][1]),
            ]
            logger.debug("Shape points: %s", shape.points)
            self.updateBoxlist()
            self.setDirty()

    def sort_rectangles(self, rectangles, row_height_threshold=0.5):
        if not rectangles:
            return []
        rect_info = []
        for idx, rect in enumerate(rectangles):
            xs = [pt[0] for pt in rect]
            ys = [pt[1] for pt in rect]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            rect_info.append(
                {
                    "index": idx,
                    "center_x": (min_x + max_x) / 2.0,
                    "center_y": (min_y + max_y) / 2.0,
                    "width": max_x - min_x,
                    "height": max_y - min_y,
                }
            )
        if not rect_info:
            return rectangles
        mode = getattr(self, "reading_mode", "horizontal")
        if mode == "vertical":
            avg_width = (
                sum(info["width"] for info in rect_info) / len(rect_info)
                if rect_info
                else 1.0
            )
            threshold = avg_width * row_height_threshold if avg_width > 0 else 10.0
            sorted_by_x = sorted(
                rect_info, key=lambda info: info["center_x"], reverse=True
            )
            columns = []
            current_col = [sorted_by_x[0]]
            last_x = sorted_by_x[0]["center_x"]
            for info in sorted_by_x[1:]:
                if abs(info["center_x"] - last_x) <= threshold:
                    current_col.append(info)
                else:
                    columns.append(current_col)
                    current_col = [info]
                last_x = info["center_x"]
            if current_col:
                columns.append(current_col)
            ordered = []
            for col in columns:
                col.sort(key=lambda info: info["center_y"])
                ordered.extend(rectangles[info["index"]] for info in col)
            return ordered
        else:
            avg_height = (
                sum(info["height"] for info in rect_info) / len(rect_info)
                if rect_info
                else 1.0
            )
            threshold = avg_height * row_height_threshold if avg_height > 0 else 10.0
            sorted_by_y = sorted(rect_info, key=lambda info: info["center_y"])
            rows = []
            current_row = [sorted_by_y[0]]
            last_y = sorted_by_y[0]["center_y"]
            for info in sorted_by_y[1:]:
                if abs(info["center_y"] - last_y) <= threshold:
                    current_row.append(info)
                else:
                    rows.append(current_row)
                    current_row = [info]
                last_y = info["center_y"]
            if current_row:
                rows.append(current_row)
            ordered = []
            for row in rows:
                row.sort(key=lambda info: info["center_x"])
                ordered.extend(rectangles[info["index"]] for info in row)
            return ordered

    def resortBoxPosition(self):
        # get original elements
        items = []
        for i in range(self.BoxList.count()):
            item = self.BoxList.item(i)
            items.append({"text": item.text(), "object": item})
        # get coordinate points
        rectangles = []
        for item in items:
            text = item["text"]
            try:
                rect = ast.literal_eval(text)  # 转为列表
                rectangles.append(rect)
            except (ValueError, SyntaxError) as e:
                logger.error(f"Error parsing text: {text}")
                continue
        # start resort
        sorted_rectangles = self.sort_rectangles(rectangles, row_height_threshold=0.5)
        # old_idx <--> new_idx
        index_map = []
        for sorted_rect in sorted_rectangles:
            for old_idx, rect in enumerate(rectangles):
                if rect == sorted_rect:
                    index_map.append(old_idx)
                    break
        # resort BoxList labelList canvas.shapes
        items = [self.BoxList.takeItem(0) for _ in range(self.BoxList.count())]
        items_label = [
            self.labelList.takeItem(0) for _ in range(self.labelList.count())
        ]
        shapes = self.canvas.shapes
        self.canvas.shapes = []
        for new_idx in range(len(index_map)):
            old_idx = index_map[new_idx]
            self.BoxList.insertItem(new_idx, items[old_idx])
            self.labelList.insertItem(new_idx, items_label[old_idx])
            self.canvas.shapes.insert(new_idx, shapes[old_idx])
        QMessageBox.information(
            self,
            "Information",
            self.get_str("resortSuccess"),
        )


def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        with open(filename, "rb") as f:
            return f.read()
    except Exception:
        return default


def str2bool(v):
    return v.lower() in ("true", "t", "1")


def parse_rgb(value):
    r, g, b = value.split(",")
    r, g, b = int(r), int(g), int(b)
    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
        raise argparse.ArgumentTypeError("RGB values must be between 0 and 255.")
    return (r, g, b)


def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("app"))
    # Tzutalin 201705+: Accept extra arguments to change predefined class file
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--lang", type=str, default="ch", nargs="?")
    arg_parser.add_argument("--gpu", type=str2bool, default=True, nargs="?")
    arg_parser.add_argument(
        "--img_list_natural_sort", type=str2bool, default=True, nargs="?"
    )
    arg_parser.add_argument("--kie", type=str2bool, default=False, nargs="?")
    arg_parser.add_argument(
        "--predefined_classes_file",
        default=os.path.join(
            os.path.dirname(__file__), "data", "predefined_classes.txt"
        ),
        nargs="?",
    )
    arg_parser.add_argument("--det_model_dir", type=str, default=None, nargs="?")
    arg_parser.add_argument("--rec_model_dir", type=str, default=None, nargs="?")
    arg_parser.add_argument("--rec_char_dict_path", type=str, default=None, nargs="?")
    arg_parser.add_argument("--cls_model_dir", type=str, default=None, nargs="?")
    arg_parser.add_argument(
        "--bbox_auto_zoom_center", type=str2bool, default=False, nargs="?"
    )
    arg_parser.add_argument("--label_font_path", type=str, default=None, nargs="?")
    arg_parser.add_argument(
        "--selected_shape_color",
        type=parse_rgb,
        default="255,255,0",
        nargs="?",
        help='An RGB value as "R,G,B".',
    )
    arg_parser.add_argument(
        "--text_layout",
        type=str,
        choices=["horizontal", "vertical"],
        default=None,
        nargs="?",
        help="Preferred text layout direction for OCR inference.",
    )
    arg_parser.add_argument(
        "--proofread_url",
        type=str,
        default=None,
        nargs="?",
        help="Endpoint URL for the AI proofread button.",
    )
    arg_parser.add_argument(
        "--proofread_style",
        type=str,
        choices=["json", "openai"],
        default=None,
        nargs="?",
        help="Proofread API style: custom JSON endpoint or OpenAI-compatible chat completion.",
    )
    arg_parser.add_argument(
        "--proofread_model",
        type=str,
        default=None,
        nargs="?",
        help="Model name when using OpenAI-compatible proofread endpoints.",
    )
    arg_parser.add_argument(
        "--proofread_api_key",
        type=str,
        default=None,
        nargs="?",
        help="API key for OpenAI-compatible proofread endpoints.",
    )

    args = arg_parser.parse_args(argv[1:])

    win = MainWindow(
        lang=args.lang,
        gpu=args.gpu,
        img_list_natural_sort=args.img_list_natural_sort,
        kie_mode=args.kie,
        default_predefined_class_file=args.predefined_classes_file,
        det_model_dir=args.det_model_dir,
        rec_model_dir=args.rec_model_dir,
        cls_model_dir=args.cls_model_dir,
        bbox_auto_zoom_center=args.bbox_auto_zoom_center,
        label_font_path=args.label_font_path,
        selected_shape_color=args.selected_shape_color,
        text_layout_mode=args.text_layout,
        proofread_url=args.proofread_url,
        proofread_style=args.proofread_style,
        proofread_model=args.proofread_model,
        proofread_api_key=args.proofread_api_key,
    )
    win.show()
    return app, win


def main():
    """construct main app and run it"""
    app, _win = get_main_app(sys.argv)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
