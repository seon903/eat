"""설정창."""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTime, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from config import MOOD_LABELS, MOODS
from menu_parser import find_latest_excel
from widgets import placeholder_pixmap


class ImagePicker(QWidget):
    def __init__(self, mood: str, path: str):
        super().__init__()
        self.mood = mood
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.preview = QLabel()
        self.preview.setFixedSize(56, 56)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("border:1px solid #eee;border-radius:6px;background:#fafafa;")
        self.edit = QLineEdit(path)
        self.edit.setPlaceholderText("기본 밥공기 캐릭터 사용")
        self.edit.textChanged.connect(self._refresh)
        pick = QPushButton("찾기")
        pick.clicked.connect(self._pick)
        clear = QPushButton("지우기")
        clear.clicked.connect(lambda: self.edit.setText(""))
        h.addWidget(self.preview)
        h.addWidget(self.edit, 1)
        h.addWidget(pick)
        h.addWidget(clear)
        self._refresh()

    def _pick(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "이미지 선택", os.path.dirname(self.edit.text()),
            "이미지 (*.png *.gif *.jpg *.jpeg *.webp)",
        )
        if p:
            self.edit.setText(p)

    def _refresh(self):
        p = self.edit.text().strip()
        pm = QPixmap(p) if p and os.path.isfile(p) else QPixmap()
        if pm.isNull():
            pm = placeholder_pixmap(self.mood, 52)
        self.preview.setPixmap(pm.scaled(52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def value(self) -> str:
        return self.edit.text().strip()


class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("구내식당 알리미 설정")
        self.setMinimumWidth(680)
        root = QVBoxLayout(self)

        g1 = QGroupBox("캐릭터 이미지 (PNG 투명배경 / GIF 지원)")
        f1 = QFormLayout(g1)
        self.pickers = {}
        for m in MOODS:
            p = ImagePicker(m, cfg["images"].get(m, ""))
            self.pickers[m] = p
            f1.addRow(MOOD_LABELS[m], p)
        self.size = QSpinBox()
        self.size.setRange(60, 500)
        self.size.setSuffix(" px")
        self.size.setValue(cfg["char_size"])
        f1.addRow("캐릭터 크기", self.size)
        root.addWidget(g1)

        g2 = QGroupBox("식단 엑셀")
        f2 = QFormLayout(g2)
        row = QHBoxLayout()
        self.folder = QLineEdit(cfg["excel_folder"])
        self.folder.setPlaceholderText("식단표 엑셀을 넣어두는 폴더")
        self.folder.textChanged.connect(self._refresh_file)
        b = QPushButton("폴더 선택")
        b.clicked.connect(self._pick_folder)
        row.addWidget(self.folder, 1)
        row.addWidget(b)
        w = QWidget()
        w.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        f2.addRow("폴더", w)
        self.file_lbl = QLabel()
        self.file_lbl.setStyleSheet("color:#888;")
        f2.addRow("사용할 파일", self.file_lbl)
        self.corner = QComboBox()
        self.corner.addItems(["A", "B"])
        self.corner.setCurrentText(cfg["default_corner"])
        f2.addRow("기본 코너", self.corner)
        root.addWidget(g2)

        g3 = QGroupBox("알림 / 실행")
        f3 = QFormLayout(g3)
        arow = QHBoxLayout()
        self.alarm_on = QCheckBox("점심 알림 사용")
        self.alarm_on.setChecked(cfg["alarm_enabled"])
        self.alarm_time = QTimeEdit(QTime.fromString(cfg["alarm_time"], "HH:mm"))
        self.alarm_time.setDisplayFormat("HH:mm")
        arow.addWidget(self.alarm_on)
        arow.addWidget(self.alarm_time)
        arow.addStretch()
        aw = QWidget()
        aw.setLayout(arow)
        arow.setContentsMargins(0, 0, 0, 0)
        f3.addRow("알림", aw)
        self.autostart = QCheckBox("윈도우 시작 시 자동 실행")
        self.autostart.setChecked(cfg["autostart"])
        self.autostart.setEnabled(sys.platform == "win32")
        f3.addRow("", self.autostart)
        root.addWidget(g3)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("저장")
        bb.button(QDialogButtonBox.Cancel).setText("취소")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)
        self._refresh_file()

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "엑셀 폴더 선택", self.folder.text())
        if d:
            self.folder.setText(d)

    def _refresh_file(self):
        p = find_latest_excel(self.folder.text().strip())
        self.file_lbl.setText(os.path.basename(p) if p else "(폴더에 .xlsx 파일이 없어요)")

    def _save(self):
        c = self.cfg
        c["images"] = {m: p.value() for m, p in self.pickers.items()}
        c["char_size"] = self.size.value()
        c["excel_folder"] = self.folder.text().strip()
        c["default_corner"] = self.corner.currentText()
        c["alarm_enabled"] = self.alarm_on.isChecked()
        c["alarm_time"] = self.alarm_time.time().toString("HH:mm")
        c["autostart"] = self.autostart.isChecked()
        c.save()
        self.accept()
