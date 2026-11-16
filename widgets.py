"""말풍선, 폭죽, 기본 캐릭터 그림."""
from __future__ import annotations

import datetime as dt
import math
import random

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

FONT = "Malgun Gothic"
PINK = QColor("#ff8fb1")
BORDER = QColor("#f3b6c8")
CREAM = QColor("#fffaf3")
TEXT = "#5a4a42"

WEEK = "월화수목금토일"


def font(size: int, bold: bool = False) -> QFont:
    f = QFont(FONT)
    f.setPointSize(size)
    f.setBold(bold)
    return f


# ---------------------------------------------------------------- 기본 캐릭터
def placeholder_pixmap(mood: str, size: int) -> QPixmap:
    """이미지를 지정하지 않았을 때 쓰는 밥공기 캐릭터."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 100.0
    p.scale(s, s)

    # 밥
    p.setPen(QPen(QColor("#d9cfc2"), 2))
    p.setBrush(QColor("#ffffff"))
    p.drawEllipse(QRectF(18, 22, 64, 46))
    # 그릇
    bowl = QPainterPath()
    bowl.moveTo(12, 50)
    bowl.lineTo(88, 50)
    bowl.cubicTo(86, 80, 70, 92, 50, 92)
    bowl.cubicTo(30, 92, 14, 80, 12, 50)
    color = {"normal": "#8fc7ff", "joy": "#ff9fbf", "excited": "#ffb347", "holiday": "#b39dff"}[mood]
    p.setBrush(QColor(color))
    p.setPen(QPen(QColor(color).darker(130), 2))
    p.drawPath(bowl)

    # 얼굴
    p.setPen(QPen(QColor("#4a3a34"), 3, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    if mood == "normal":
        p.setBrush(QColor("#4a3a34"))
        p.drawEllipse(QPointF(38, 64), 3, 3.5)
        p.drawEllipse(QPointF(62, 64), 3, 3.5)
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(44, 66, 12, 8), 200 * 16, 140 * 16)
    elif mood in ("joy", "holiday"):
        p.drawArc(QRectF(32, 60, 12, 10), 20 * 16, 140 * 16)
        p.drawArc(QRectF(56, 60, 12, 10), 20 * 16, 140 * 16)
        p.setBrush(QColor("#e8576f"))
        p.drawChord(QRectF(42, 66, 16, 14), 180 * 16, 180 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 120, 150, 120))
        p.drawEllipse(QPointF(28, 72), 6, 4)
        p.drawEllipse(QPointF(72, 72), 6, 4)
    else:  # excited
        p.drawLine(QPointF(32, 58), QPointF(42, 64))
        p.drawLine(QPointF(42, 64), QPointF(32, 68))
        p.drawLine(QPointF(68, 58), QPointF(58, 64))
        p.drawLine(QPointF(58, 64), QPointF(68, 68))
        p.setBrush(QColor("#e8576f"))
        p.drawEllipse(QRectF(43, 68, 14, 14))
    if mood == "holiday":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffd54f"))
        for cx, cy, r in ((14, 18, 7), (86, 14, 6), (50, 8, 5)):
            _star(p, cx, cy, r)
    p.end()
    return pm


def _star(p: QPainter, cx, cy, r):
    path = QPainterPath()
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pt = QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    path.closeSubpath()
    p.drawPath(path)


# ---------------------------------------------------------------- 말풍선
class BubbleBase(QWidget):
    TAIL = 14
    RADIUS = 18

    def __init__(self, popup: bool):
        flags = Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        flags |= Qt.Popup if popup else (Qt.Tool | Qt.WindowStaysOnTopHint)
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.tail_side = "bottom"
        self.tail_x = 60
        self.inner = QWidget(self)
        self._outer = QVBoxLayout(self)
        self._apply_margins()
        self._outer.addWidget(self.inner)

    def _apply_margins(self):
        t = self.TAIL
        if self.tail_side == "bottom":
            self._outer.setContentsMargins(14, 12, 14, 12 + t)
        else:
            self._outer.setContentsMargins(14, 12 + t, 14, 12)

    _anchor = None

    def place_near(self, target: QRectF, screen_rect):
        self._anchor = (target, screen_rect)
        self.adjustSize()
        w, h = self.width(), self.height()
        cx = target.center().x()
        x = int(min(max(cx - w / 2, screen_rect.left() + 4), screen_rect.right() - w - 4))
        y_above = int(target.top() - h + 8)
        if y_above >= screen_rect.top():
            self.tail_side, y = "bottom", y_above
        else:
            self.tail_side, y = "top", int(target.bottom() - 8)
        self._apply_margins()
        self.adjustSize()
        self.tail_x = min(max(cx - x, self.RADIUS + 12), self.width() - self.RADIUS - 12)
        self.move(x, y)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t, r = self.TAIL, self.RADIUS
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self.tail_side == "bottom":
            body = rect.adjusted(0, 0, 0, -t)
            tip_y, base_y = rect.bottom(), body.bottom() - 1
        else:
            body = rect.adjusted(0, t, 0, 0)
            tip_y, base_y = rect.top(), body.top() + 1
        path = QPainterPath()
        path.addRoundedRect(body, r, r)
        tail = QPainterPath()
        tx = self.tail_x
        tail.moveTo(tx - 10, base_y)
        tail.lineTo(tx + 2, tip_y)
        tail.lineTo(tx + 10, base_y)
        tail.closeSubpath()
        path = path.united(tail)
        p.setPen(QPen(BORDER, 2.5))
        p.setBrush(CREAM)
        p.drawPath(path)


class ShoutBubble(BubbleBase):
    """'밥!!!', '오늘은 휴일!!' 같은 짧은 말풍선."""

    clicked = Signal()

    def __init__(self):
        super().__init__(popup=False)
        lay = QVBoxLayout(self.inner)
        lay.setContentsMargins(6, 2, 6, 2)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"color:{TEXT};")
        lay.addWidget(self.label)

    def set_text(self, text: str, size: int = 20, color: str = TEXT):
        self.label.setFont(font(size, True))
        self.label.setStyleSheet(f"color:{color};")
        self.label.setText(text)

    def mousePressEvent(self, e):
        self.clicked.emit()
        self.hide()


class MenuBubble(BubbleBase):
    heart_toggled = Signal(str, str, bool)  # corner, item, on
    corner_changed = Signal(str)
    holiday_shown = Signal()
    day_rendered = Signal(bool)  # True = 휴일인 날을 보는 중
    closed = Signal()

    def __init__(self):
        super().__init__(popup=True)
        self.menus = {}
        self.setMinimumWidth(250)
        self.setMaximumWidth(340)
        self.hidden_at = 0.0
        self.day = None
        self.hearts = None
        self.corner = "A"
        lay = QVBoxLayout(self.inner)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)

        self.days = []  # 날짜순 DayMenu 목록
        self.idx = 0
        self.today = None

        head = QHBoxLayout()
        head.setSpacing(2)
        self.nav = {}
        for key, txt, delta in (("prev", "◀", -1), ("next", "▶", 1)):
            b = QPushButton(txt)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(QSize(26, 26))
            b.setFont(font(10))
            b.setStyleSheet(
                "QPushButton{border:none;border-radius:13px;background:#ffe3ec;color:#c76b8a;}"
                "QPushButton:hover{background:#ffcadb;}"
                "QPushButton:disabled{background:transparent;color:#eedde3;}"
            )
            b.clicked.connect(lambda _=False, d=delta: self.go(d))
            self.nav[key] = b
        self.title = QLabel()
        self.title.setFont(font(12, True))
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet(f"color:{TEXT};")
        head.addWidget(self.nav["prev"])
        head.addWidget(self.title, 1)
        head.addWidget(self.nav["next"])
        lay.addLayout(head)

        tabs = QHBoxLayout()
        tabs.setSpacing(6)
        self.tab_btns = {}
        for c in ("A", "B"):
            b = QPushButton(f"{c}코너")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFont(font(10, True))
            b.setStyleSheet(
                "QPushButton{background:#fff;border:2px solid #f3b6c8;border-radius:12px;"
                "padding:4px 14px;color:#c76b8a;}"
                "QPushButton:checked{background:#ff8fb1;color:white;border-color:#ff8fb1;}"
            )
            b.clicked.connect(lambda _=False, c=c: self.select_corner(c, user=True))
            tabs.addWidget(b)
            self.tab_btns[c] = b
        tabs.addStretch()
        lay.addLayout(tabs)

        self.tags = QLabel()
        self.tags.setFont(font(9))
        lay.addWidget(self.tags)

        self.list_box = QWidget()
        self.list_lay = QVBoxLayout(self.list_box)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(1)
        lay.addWidget(self.list_box)

        self.message = QLabel()
        self.message.setFont(font(11))
        self.message.setWordWrap(True)
        self.message.setStyleSheet(f"color:{TEXT};")
        lay.addWidget(self.message)

    # -- 데이터
    def show_days(self, menus: dict, date, hearts, corner, today):
        """하루씩 ◀ ▶로 이동. 식단표 앞뒤 하루(주말 포함)와 오늘까지 볼 수 있고,
        엑셀에 메뉴가 없는 날은 '회사 안 나오는 날'."""
        self.menus, self.hearts, self.today = menus, hearts, today
        keys = sorted(menus)
        lo = min(keys[0] - dt.timedelta(days=1), today)
        hi = max(keys[-1] + dt.timedelta(days=2), today)
        self.days = [lo + dt.timedelta(days=i) for i in range((hi - lo).days + 1)]
        self.idx = self.days.index(date) if date in self.days else 0
        self.corner = corner
        self._render()

    def go(self, delta):
        if not self.days:
            return
        self.idx = max(0, min(len(self.days) - 1, self.idx + delta))
        self._render()

    def _render(self):
        d = self.days[self.idx]
        rel = {0: "오늘", -1: "어제", 1: "내일"}.get((d - self.today).days)
        label = f"{d.month}월 {d.day}일 ({WEEK[d.weekday()]})"
        self.title.setText(f"{label} · {rel}" if rel else label)
        self.nav["prev"].show()
        self.nav["next"].show()
        self.nav["prev"].setEnabled(self.idx > 0)
        self.nav["next"].setEnabled(self.idx < len(self.days) - 1)
        day = self.menus.get(d)
        if day is None:  # 메뉴 없는 날 = 휴일
            self.day = None
            for b in self.tab_btns.values():
                b.hide()
            self.tags.hide()
            self._clear_list()
            self.message.setFont(font(15, True))
            self.message.setAlignment(Qt.AlignCenter)
            self.message.setStyleSheet("color:#e2557f;padding:10px 0;")
            self.message.setText("회사 안 나오는 날! 🎉")
            self.message.show()
            self._relayout()
            self.day_rendered.emit(True)
            self.holiday_shown.emit()
            return
        self.day = day
        self.message.hide()
        for b in self.tab_btns.values():
            b.show()
        corner = self.corner if self.corner in day.corners else next(iter(day.corners))
        self.select_corner(corner)
        self.day_rendered.emit(False)

    def _relayout(self):
        self.inner.adjustSize()
        if self.isVisible() and self._anchor:
            self.place_near(*self._anchor)
        else:
            self.adjustSize()

    def show_message(self, title: str, text: str):
        self.day = None
        self.title.setText(title)
        self.nav["prev"].hide()
        self.nav["next"].hide()
        for b in self.tab_btns.values():
            b.hide()
        self.tags.hide()
        self._clear_list()
        self.message.setFont(font(11))
        self.message.setAlignment(Qt.AlignLeft)
        self.message.setStyleSheet(f"color:{TEXT};")
        self.message.setText(text)
        self.message.show()

    def select_corner(self, corner, user=False):
        if not self.day:
            return
        self.corner = corner
        for c, b in self.tab_btns.items():
            b.setChecked(c == corner)
            b.setEnabled(c in self.day.corners)
        info = self.day.corners.get(corner)
        self._clear_list()
        if info and info.tags:
            chips = " ".join(
                f"<span style='background:#ffe3ec;color:#c76b8a;'>&nbsp;#{t}&nbsp;</span>"
                for t in info.tags
            )
            self.tags.setText(chips)
            self.tags.show()
        else:
            self.tags.hide()
        for item in (info.items if info else []):
            row = self._row(corner, item)
            self.list_lay.addWidget(row)
            row.show()
        if user:
            self.corner_changed.emit(corner)
        self.list_box.adjustSize()
        self.inner.adjustSize()
        if self.isVisible() and self._anchor:
            self.place_near(*self._anchor)
        else:
            self.adjustSize()

    def _clear_list(self):
        while self.list_lay.count():
            w = self.list_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _row(self, corner, item):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(2, 0, 0, 0)
        lbl = QLabel(item)
        lbl.setFont(font(11))
        lbl.setStyleSheet(f"color:{TEXT};")
        btn = QPushButton()
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFlat(True)
        btn.setFixedSize(QSize(28, 24))
        btn.setFont(font(13))

        def paint(on):
            btn.setText("♥" if on else "♡")
            btn.setStyleSheet(
                "QPushButton{border:none;background:transparent;color:%s;}"
                % ("#ff4f7f" if on else "#d8a8b8")
            )

        paint(self.hearts.has(self.day.date, corner, item))

        def toggled():
            on = self.hearts.toggle(self.day.date, corner, item)
            paint(on)
            self.heart_toggled.emit(corner, item, on)

        btn.clicked.connect(toggled)
        h.addWidget(lbl, 1)
        h.addWidget(btn)
        return row

    def hideEvent(self, e):
        import time

        self.hidden_at = time.monotonic()
        super().hideEvent(e)
        self.closed.emit()


# ---------------------------------------------------------------- 폭죽
class Fireworks(QWidget):
    COLORS = ["#ff5c8a", "#ffd54f", "#7cd4ff", "#a98bff", "#7be495", "#ff9f43"]

    def __init__(self):
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(460, 460)
        self.particles = []
        self.remaining = 0
        self.timer = QTimer(self, interval=16, timeout=self._tick)

    def play(self, center, duration_ms=4500):
        self.move(int(center.x() - self.width() / 2), int(center.y() - self.height() / 2))
        self.remaining = duration_ms
        self.particles.clear()
        self.show()
        self.timer.start()

    def _burst(self):
        cx = random.uniform(70, self.width() - 70)
        cy = random.uniform(50, self.height() * 0.55)
        color = QColor(random.choice(self.COLORS))
        n = random.randint(26, 40)
        for i in range(n):
            a = 2 * math.pi * i / n + random.uniform(-0.1, 0.1)
            sp = random.uniform(2.0, 4.5)
            self.particles.append([cx, cy, math.cos(a) * sp, math.sin(a) * sp, 1.0, color])

    def _tick(self):
        self.remaining -= 16
        if self.remaining > 600 and random.random() < 0.09:
            self._burst()
        alive = []
        for pt in self.particles:
            pt[0] += pt[2]
            pt[1] += pt[3]
            pt[2] *= 0.97
            pt[3] = pt[3] * 0.97 + 0.07
            pt[4] -= 0.016
            if pt[4] > 0:
                alive.append(pt)
        self.particles = alive
        if self.remaining <= 0 and not self.particles:
            self.timer.stop()
            self.hide()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for x, y, _, _, life, c in self.particles:
            col = QColor(c)
            col.setAlphaF(max(0.0, min(1.0, life)))
            p.setBrush(QBrush(col))
            r = 2 + 2.5 * life
            p.drawEllipse(QPointF(x, y), r, r)
