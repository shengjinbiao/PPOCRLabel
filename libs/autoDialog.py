import datetime
import json
import logging
import time
import threading

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSize
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox as BB,
    QProgressBar,
    QVBoxLayout,
    QListWidget,
    QApplication,
)

from libs.utils import newIcon
from libs.hunyuan_ocr import HunyuanLayout

logger = logging.getLogger("PPOCRLabel")


class Worker(QThread):
    progressBarValue = pyqtSignal(int)
    listValue = pyqtSignal(str)
    end_signal = pyqtSignal(int, str)
    pageReady = pyqtSignal(str, object)
    handle = 0

    def __init__(self, ocr, img_list, main_thread, model):
        super(Worker, self).__init__()
        self.result_dic = None
        self.ocr = ocr
        self.img_list = img_list
        self.mainThread = main_thread
        self.model = model
        self.pageSaved = threading.Event()
        self.save_error = None
        self.setStackSize(1024 * 1024)

    def run(self):
        try:
            findex = 0
            total = len(self.img_list)
            saved_count = 0
            failed_paths = []
            logger.info("Auto recognition started: model=%s pages=%d", self.model, total)
            for img_path in self.img_list:
                if self.handle == 0:
                    logger.info(
                        "Auto recognition page %d/%d: %s",
                        findex + 1,
                        total,
                        img_path,
                    )
                    self.listValue.emit(img_path)
                    if self.model == "paddle":
                        img = cv2.imdecode(
                            np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR
                        )
                        if img is None:
                            logger.warning("Can not read image file %s", img_path)
                            self.result_dic = None
                            findex += 1
                            self.progressBarValue.emit(findex)
                            failed_paths.append(img_path)
                            continue
                        h, w, _ = img.shape
                        if h > 32 and w > 32:
                            column_result = None
                            if getattr(self.mainThread, "two_column_lr", False):
                                try:
                                    column_result = (
                                        self.mainThread.predict_ocr_by_two_column_crops(
                                            self.ocr, img
                                        )
                                    )
                                except Exception as exc:
                                    logger.warning(
                                        "Two-column crop OCR failed; falling back to full page: %s",
                                        exc,
                                    )
                            self.result_dic = []
                            if column_result is not None:
                                rec_polys, rec_texts, rec_scores = column_result
                            else:
                                result = self.ocr.predict(img)[0]
                                rec_polys = result["rec_polys"]
                                rec_texts = result["rec_texts"]
                                rec_scores = result["rec_scores"]
                            if getattr(
                                self.mainThread, "layout_first", False
                            ) or getattr(self.mainThread, "two_column_lr", False):
                                (
                                    rec_polys,
                                    rec_texts,
                                    rec_scores,
                                ) = self.mainThread.reorder_ocr_result_by_layout(
                                    rec_polys,
                                    rec_texts,
                                    rec_scores,
                                    w,
                                )
                            for poly, text, score in zip(
                                rec_polys,
                                rec_texts,
                                rec_scores,
                            ):
                                # Convert numpy array to list for JSON serialization
                                poly_list = (
                                    poly.tolist() if hasattr(poly, "tolist") else poly
                                )
                                self.result_dic.append([poly_list, (text, score)])
                        else:
                            logger.warning(
                                "The size of %s is too small to be recognised", img_path
                            )
                            self.result_dic = None
                    elif self.model == "ppstructure":
                        img = cv2.imdecode(
                            np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR
                        )
                        if img is None:
                            logger.warning("Can not read image file %s", img_path)
                            self.result_dic = None
                            findex += 1
                            self.progressBarValue.emit(findex)
                            failed_paths.append(img_path)
                            continue
                        self.result_dic = self.mainThread._ppstructure_recognize(
                            img_path
                        )

                    elif self.model in ("hunyuan", "qwen"):
                        engine = (
                            self.mainThread.hunyuan_engine
                            if self.model == "hunyuan"
                            else self.mainThread.qwen_engine
                        )
                        engine_name = "HunyuanOCR" if self.model == "hunyuan" else "Qwen OCR"
                        self.listValue.emit(f"{engine_name}：启动本地模型并识别，首次加载可能需要一些时间…")
                        layout_mode = getattr(self.mainThread, "hunyuan_layout_mode", "page")
                        self.listValue.emit(
                            f"{engine_name} 版式：{HunyuanLayout.LABELS.get(layout_mode, layout_mode)}"
                        )
                        self.listValue.emit(HunyuanLayout.detail(layout_mode))
                        if getattr(self.mainThread, "hunyuan_line_mode", False):
                            self.listValue.emit("逐行裁条识别：每条印刷行单独送模型，框与文严格对应（较慢）。")
                        if getattr(self.mainThread, "hunyuan_ipa_mode", False):
                            self.listValue.emit("音标页模式：用国际音标专用提示词（五度调符 + 音标字符表，禁止注音/拼音代替）。")
                        try:
                            self.result_dic = engine.recognize(
                                img_path,
                                layout_mode=layout_mode,
                                reading_mode=getattr(self.mainThread, "reading_mode", "horizontal"),
                                cancelled=lambda: self.handle != 0,
                                line_mode=getattr(self.mainThread, "hunyuan_line_mode", False),
                                ipa_mode=getattr(self.mainThread, "hunyuan_ipa_mode", False),
                            )
                        except Exception as exc:
                            logger.exception("%s failed for %s", engine_name, img_path)
                            self.listValue.emit("跳过本页：" + str(exc))
                            self.result_dic = None
                            findex += 1
                            self.progressBarValue.emit(findex)
                            failed_paths.append(img_path)
                            continue

                    # 结果保存
                    if self.result_dic is None or len(self.result_dic) == 0:
                        logger.warning("Can not recognise file %s", img_path)
                        failed_paths.append(img_path)
                        pass
                    else:
                        if self.model not in ("hunyuan", "qwen"):
                            self.result_dic = (
                                self.mainThread.refine_ocr_result_entries_by_crops(
                                    img, self.result_dic
                                )
                            )
                        if self.model not in ("hunyuan", "qwen"):
                            self.result_dic = self.mainThread.sort_ocr_result_entries(
                                self.result_dic
                            )
                        strs = ""
                        for res in self.result_dic:
                            chars = res[1][0]
                            cond = res[1][1]
                            posi = res[0]
                            strs += (
                                "Transcription: "
                                + chars
                                + " Probability: "
                                + str(cond)
                                + " Location: "
                                + json.dumps(posi)
                                + "\n"
                            )
                        # Sending large amounts of data repeatedly through pyqtSignal may affect the program efficiency
                        self.listValue.emit(strs)
                        if self.model in ("hunyuan", "qwen"):
                            # All Qt-backed sorting and saving stays on the GUI thread.
                            self.pageSaved.clear()
                            self.save_error = None
                            self.pageReady.emit(img_path, self.result_dic)
                            while not self.pageSaved.wait(0.05):
                                if self.handle != 0:
                                    raise RuntimeError("本地 OCR 已取消")
                            if self.save_error:
                                raise RuntimeError(self.save_error)
                        else:
                            self.mainThread.result_order_from_model = False
                            self.mainThread.result_dic = self.result_dic
                            self.mainThread.filePath = img_path
                            self.mainThread.saveFile(mode="Auto")
                        saved_count += 1
                        logger.info(
                            "Auto recognition saved page %d/%d: boxes=%d file=%s",
                            findex + 1,
                            total,
                            len(self.result_dic),
                            img_path,
                        )
                    findex += 1
                    self.progressBarValue.emit(findex)
                else:
                    logger.warning(
                        "Auto recognition canceled after %d/%d pages", findex, total
                    )
                    break
            if failed_paths:
                logger.warning(
                    "Auto recognition finished with missing pages: saved=%d failed=%d total=%d",
                    saved_count,
                    len(failed_paths),
                    total,
                )
                for path in failed_paths:
                    logger.warning("Auto recognition failed page: %s", path)
                    self.listValue.emit("未完成：" + path)
            else:
                logger.info(
                    "Auto recognition finished successfully: saved=%d total=%d",
                    saved_count,
                    total,
                )
            self.end_signal.emit(0, "readAll")
        except Exception as e:
            logger.exception("Error in worker thread: %s", e)
            self.end_signal.emit(1, str(e))
        finally:
            if self.model == "hunyuan" and self.mainThread.hunyuan_engine is not None:
                self.mainThread.hunyuan_engine.stop()
            elif self.model == "qwen" and self.mainThread.qwen_engine is not None:
                self.mainThread.qwen_engine.stop()


class AutoDialog(QDialog):
    def __init__(
        self,
        text="Enter object label",
        parent=None,
        ocr=None,
        image_list=None,
        len_bar=0,
        model="paddle",
    ):
        super(AutoDialog, self).__init__(parent)
        self.setFixedWidth(1000)
        self.parent = parent
        self.ocr = ocr
        self.img_list = image_list
        self.len_bar = len_bar
        self.pb = QProgressBar(parent)
        self.pb.setRange(0, self.len_bar)
        self.pb.setValue(0)

        layout = QVBoxLayout()
        layout.addWidget(self.pb)
        self.model = model
        self.listWidget = QListWidget(self)
        self.listWidget.setWordWrap(True)
        layout.addWidget(self.listWidget)

        self.buttonBox = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon("done"))
        bb.button(BB.Cancel).setIcon(newIcon("undo"))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)
        bb.button(BB.Ok).setEnabled(False)

        self.setLayout(layout)
        # self.setWindowTitle("自动标注中")
        self.setWindowModality(Qt.ApplicationModal)

        # self.setWindowFlags(Qt.WindowCloseButtonHint)

        self.thread_1 = Worker(self.ocr, self.img_list, self.parent, model)
        self.thread_1.progressBarValue.connect(self.handleProgressBarSingal)
        self.thread_1.listValue.connect(self.handleListWidgetSingal)
        self.thread_1.end_signal.connect(self.handleEndsignalSignal)
        self.thread_1.pageReady.connect(self.saveHunyuanPage)
        self.time_start = time.time()  # save start time

    def handleProgressBarSingal(self, i):
        self.pb.setValue(i)

        # calculate time left of auto labeling
        # Use average time to prevent time fluctuations
        avg_time = (time.time() - self.time_start) / max(i, 1)
        time_left = str(
            datetime.timedelta(seconds=avg_time * (self.len_bar - i))
        ).split(".")[
            0
        ]  # Remove microseconds
        # show
        self.setWindowTitle("PPOCRLabel  --  " + f"Time Left: {time_left}")

    def saveHunyuanPage(self, path, results):
        try:
            if self.thread_1.handle != 0:
                return
            # 视觉模型的阅读顺序由模型自己（或按指定栏序合并）给出，
            # 保存前不再按坐标几何重排，否则会把段落顺序打乱。
            self.parent.result_order_from_model = True
            self.parent.result_dic = results
            self.parent.filePath = path
            self.parent.saveFile(mode="Auto")
        except Exception as exc:
            logger.exception("Unable to save HunyuanOCR page")
            self.thread_1.save_error = str(exc)
        finally:
            self.thread_1.pageSaved.set()

    def handleListWidgetSingal(self, i):
        self.listWidget.addItem(i)
        titem = self.listWidget.item(self.listWidget.count() - 1)
        titem.setToolTip(i)
        # 长文本（例如两行并成一行的识别结果）要让行高跟着换行长，否则尾部被遮住。
        try:
            metrics = self.listWidget.fontMetrics()
            width = max(60, self.listWidget.viewport().width() - 16)
            rect = metrics.boundingRect(
                0, 0, width, 100000, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, i
            )
            titem.setSizeHint(QSize(width, rect.height() + 6))
        except Exception:
            pass
        self.listWidget.scrollToItem(titem)

    def handleEndsignalSignal(self, code, message):
        self.buttonBox.button(BB.Ok).setEnabled(True)
        self.buttonBox.button(BB.Cancel).setEnabled(False)
        if code:
            self.handleListWidgetSingal("识别未完成：" + message)
        self.thread_1.quit()

    def reject(self):
        logger.debug("Auto recognition dialog rejected")
        self.thread_1.handle = -1
        if self.model == "hunyuan" and self.parent.hunyuan_engine is not None:
            self.parent.hunyuan_engine.stop()
        elif self.model == "qwen" and self.parent.qwen_engine is not None:
            self.parent.qwen_engine.stop()
        self.thread_1.quit()
        self.buttonBox.setEnabled(False)
        while not self.thread_1.wait(50):
            QApplication.processEvents()
        self.accept()

    def validate(self):
        while not self.thread_1.wait(50):
            QApplication.processEvents()
        self.accept()

    def postProcess(self):
        try:
            self.edit.setText(self.edit.text().trimmed())
        except AttributeError:
            self.edit.setText(self.edit.text())
            logger.debug("Auto dialog text: %s", self.edit.text())

    def popUp(self):
        self.thread_1.start()
        return 1 if self.exec_() else None

    def closeEvent(self, event, **kwargs):
        self.reject()
