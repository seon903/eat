"""구내식당 알리미 - 데스크톱 캐릭터 위젯."""
from __future__ import annotations

import datetime as dt
import math
import os
import sys
import time
import traceback

from PySide6.QtCore import QLockFile, QPoint, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCursor, QIcon, QImageReader, QMovie, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)

from config import Config, Hearts, config_dir, set_autostart
from menu_parser import find_latest_excel, parse_workbook
from settings_dialog import SettingsDialog
from widgets import Fireworks, MenuBubble, ShoutBubble, placeholder_pixmap

PAD = 16  # 흔들림 여유 공간


class Character(QWidget):
    def __init__(self, app_ctl):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint,
        )
        self.ctl = app_ctl
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.label = QLabel(self)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.movie: QMovie | None = None
        self.mood = None
        self._press = None
        self._dragging = False
        self._shake_t = 0
        self.shake_timer = QTimer(self, interval=30, timeout=self._shake_step)
        self.setCursor(Qt.PointingHandCursor)

    # -- 이미지
    def set_mood(self, mood: str):
        self.mood = mood
        imgs = self.ctl.cfg["images"]
        size = self.ctl.cfg["char_size"]
        path = imgs.get(mood, "")
        if mood == "holiday" and not path:
            path = imgs.get("joy", "")
        if self.movie:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        pm = None
        if path and os.path.isfile(path):
            reader = QImageReader(path)
            src = reader.size()
            if src.isValid() and src.height() > 0:
                w = max(1, round(src.width() * size / src.height()))
                target = QSize(w, size)
            else:
                target = QSize(size, size)
            if path.lower().endswith(".gif") and QMovie(path).frameCount() > 1:
                self.movie = QMovie(path)
                self.movie.setScaledSize(target)
                self.label.setMovie(self.movie)
                self.movie.start()
                self._resize_to(target)
                return
            pm = QPixmap(path)
            if not pm.isNull():
                pm = pm.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if pm is None or pm.isNull():
            pm = placeholder_pixmap(mood, size)
        self.label.setPixmap(pm)
        self._resize_to(pm.size())

    def _resize_to(self, s: QSize):
        self.label.resize(s)
        self.label.move(PAD, PAD)
        # 표정이 바뀌어도 발밑(아래쪽 가운데)이 고정되도록
        old = self.geometry() if self.isVisible() else None
        self.resize(s.width() + PAD * 2, s.height() + PAD * 2)
        if old is not None:
            self.move(old.center().x() - self.width() // 2, old.bottom() - self.height() + 1)

    def char_rect(self) -> QRectF:
        g = self.geometry()
        return QRectF(g.x() + PAD, g.y() + PAD, g.width() - 2 * PAD, g.height() - 2 * PAD)

    # -- 흔들기
    def start_shake(self):
        self._shake_t = 0
        self.shake_timer.start()

    def stop_shake(self):
        self.shake_timer.stop()
        self.label.move(PAD, PAD)

    def _shake_step(self):
        self._shake_t += 1
        t = self._shake_t
        dx = round(10 * math.sin(t * 0.9))
        dy = round(-abs(6 * math.sin(t * 0.45)))
        self.label.move(PAD + dx, PAD + dy)

    # -- 마우스
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = (e.globalPosition().toPoint(), self.pos())
            self._dragging = False
        elif e.button() == Qt.RightButton:
            self.ctl.tray_menu.popup(QCursor.pos())

    def mouseMoveEvent(self, e):
        if not self._press:
            return
        gp, wp = self._press
        delta = e.globalPosition().toPoint() - gp
        if not self._dragging and delta.manhattanLength() > 5:
            self._dragging = True
            self.ctl.hide_bubbles()
        if self._dragging:
            self.move(wp + delta)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self._press:
            return
        self._press = None
        if self._dragging:
            self._dragging = False
            self.ctl.cfg["pos"] = [self.x(), self.y()]
            self.ctl.cfg.save()
        else:
            self.ctl.on_click()


class Controller:
    def __init__(self, app: QApplication):
        self.app = app
        self.cfg = Config()
        self.hearts = Hearts()
        self.menus = {}
        self.excel_path = None
        self.excel_mtime = None
        self.error = None
        self.alarm_fired_on = None
        self.alarm_active = False
        self.today = dt.date.today()

        self.char = Character(self)
        self.menu_bubble = MenuBubble()
        self.menu_bubble.heart_toggled.connect(self.on_heart)
        self.shout = ShoutBubble()
        self.shout.clicked.connect(self.on_click)
        self.fireworks = Fireworks()
        self.mood_timer = QTimer(singleShot=True, timeout=self.restore_mood)
        self.shout_timer = QTimer(singleShot=True, timeout=self.shout.hide)
        self.alarm_end_timer = QTimer(singleShot=True, timeout=self.stop_alarm)

        self._build_tray()
        self.reload_excel(force=True)
        self.restore_mood()
        self._place_initial()
        self.char.show()

        self.tick = QTimer(interval=10_000, timeout=self.on_tick)
        self.tick.start()

        if self.cfg.first_run:
            QTimer.singleShot(400, self.open_settings)
        elif self.day_state() == "holiday":
            QTimer.singleShot(600, self.celebrate_holiday)

    # ---------------------------------------------------------- 초기화
    def _build_tray(self):
        self.tray_menu = QMenu()
        for text, fn in (
            ("오늘 메뉴 보기", lambda: self.show_menu(browse=True)),
            ("설정", self.open_settings),
            ("엑셀 다시 불러오기", lambda: self.reload_excel(force=True, notify=True)),
            ("알림 테스트", self.start_alarm),
            ("위치 초기화", self.reset_position),
        ):
            a = QAction(text, self.tray_menu)
            a.triggered.connect(fn)
            self.tray_menu.addAction(a)
        self.tray_menu.addSeparator()
        q = QAction("종료", self.tray_menu)
        q.triggered.connect(self.app.quit)
        self.tray_menu.addAction(q)

        self.tray = QSystemTrayIcon(QIcon(placeholder_pixmap("normal", 64)))
        self.tray.setToolTip("구내식당 알리미")
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(
            lambda r: self.show_menu() if r == QSystemTrayIcon.Trigger else None
        )
        self.tray.show()

    def _place_initial(self):
        pos = self.cfg["pos"]
        screens = [s.availableGeometry() for s in self.app.screens()]
        if pos and any(g.contains(QPoint(pos[0] + 20, pos[1] + 20)) for g in screens):
            self.char.move(pos[0], pos[1])
        else:
            self.reset_position()

    def reset_position(self):
        g = self.app.primaryScreen().availableGeometry()
        self.char.move(g.right() - self.char.width() - 30, g.bottom() - self.char.height() - 30)
        self.cfg["pos"] = [self.char.x(), self.char.y()]
        self.cfg.save()

    # ---------------------------------------------------------- 데이터
    def reload_excel(self, force=False, notify=False):
        path = find_latest_excel(self.cfg["excel_folder"])
        mtime = os.path.getmtime(path) if path else None
        if not force and path == self.excel_path and mtime == self.excel_mtime:
            return
        self.excel_path, self.excel_mtime = path, mtime
        self.error = None
        self.menus = {}
        if path:
            try:
                self.menus = parse_workbook(path, dt.date.today())
            except Exception as ex:  # noqa: BLE001
                self.error = f"{type(ex).__name__}: {ex}"
                traceback.print_exc()
        if notify:
            msg = (f"{os.path.basename(path)} 에서 {len(self.menus)}일치 식단을 읽었어요."
                   if path and not self.error else self.error or "엑셀 파일을 찾지 못했어요.")
            self.tray.showMessage("구내식당 알리미", msg, QSystemTrayIcon.Information, 3000)
        if self.char.mood is not None and not self.alarm_active:
            self.restore_mood()

    def day_state(self) -> str:
        """menu / holiday / stale / nofile"""
        today = dt.date.today()
        if not self.menus:
            return "nofile"
        if today in self.menus:
            return "menu"
        if today.weekday() >= 5:
            return "holiday"
        dates = sorted(self.menus)
        week_start = dates[0] - dt.timedelta(days=dates[0].weekday())
        week_end = dates[-1] + dt.timedelta(days=6 - dates[-1].weekday())
        if week_start <= today <= week_end:
            return "holiday"  # 식단표 주간에 포함되는데 오늘 칸이 없음 = 휴일
        return "stale"

    # ---------------------------------------------------------- 표정
    def restore_mood(self):
        self.char.set_mood("holiday" if self.day_state() == "holiday" else "normal")

    def flash_mood(self, mood, ms):
        self.char.set_mood(mood)
        self.mood_timer.start(ms)

    # ---------------------------------------------------------- 동작
    def hide_bubbles(self):
        self.menu_bubble.hide()
        self.shout.hide()

    def screen_rect(self):
        s = self.app.screenAt(self.char.geometry().center()) or self.app.primaryScreen()
        return s.availableGeometry()

    def on_click(self):
        if time.monotonic() - self.menu_bubble.hidden_at < 0.25:
            return  # 열린 말풍선을 닫으려고 누른 클릭
        if self.alarm_active:
            self.stop_alarm()
            self.show_menu()
            return
        if self.day_state() == "holiday" and not self.shout.isVisible():
            self.celebrate_holiday()  # 휴일: 첫 클릭은 폭죽, 한 번 더 누르면 다른 날 메뉴
            return
        self.show_menu(browse=True)

    def show_menu(self, browse=False):
        self.shout.hide()
        state = self.day_state()
        if state == "holiday" and not browse:
            self.celebrate_holiday()
            return
        b = self.menu_bubble
        today = dt.date.today()
        if state in ("menu", "holiday"):
            b.show_days(self.menus, today, self.hearts, self.cfg["default_corner"], today)
        elif state == "stale":
            b.show_message("📅 새 식단표가 필요해요",
                           "엑셀에 오늘 날짜가 없어요.\n이번 주 식단표를 폴더에 넣어주세요!")
        elif self.error:
            b.show_message("😵 엑셀을 읽지 못했어요", self.error)
        else:
            b.show_message("📂 식단표를 찾을 수 없어요",
                           "설정에서 식단 엑셀이 들어있는 폴더를 지정해 주세요.")
        b.place_near(self.char.char_rect(), self.screen_rect())
        b.show()
        b.raise_()

    def shout_text(self, text, size, color, ms):
        self.shout.set_text(text, size, color)
        self.shout.place_near(self.char.char_rect(), self.screen_rect())
        self.shout.show()
        self.shout.raise_()
        if ms:
            self.shout_timer.start(ms)
        else:
            self.shout_timer.stop()

    def celebrate_holiday(self):
        self.menu_bubble.hide()
        self.char.set_mood("holiday")
        self.shout_text("오늘은 휴일!! 🎉", 18, "#e2557f", 5000)
        self.fireworks.play(self.char.geometry().center())
        self.char.raise_()

    def on_heart(self, corner, item, on):
        if on:
            self.flash_mood("joy", 2500)

    # ---------------------------------------------------------- 알림
    def on_tick(self):
        today = dt.date.today()
        if today != self.today:
            self.today = today
            self.reload_excel(force=True)
            self.restore_mood()
        else:
            self.reload_excel()
        if not self.cfg["alarm_enabled"] or self.alarm_fired_on == today:
            return
        try:
            hh, mm = map(int, self.cfg["alarm_time"].split(":"))
        except ValueError:
            return
        now = dt.datetime.now()
        at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if at <= now < at + dt.timedelta(minutes=30):
            self.alarm_fired_on = today
            if self.day_state() == "menu":
                self.start_alarm()

    def start_alarm(self):
        self.alarm_active = True
        self.menu_bubble.hide()
        self.mood_timer.stop()
        self.char.set_mood("excited")
        self.char.start_shake()
        self.shout_text("밥!!!", 26, "#ff6a3d", 0)
        QApplication.beep()
        self.alarm_end_timer.start(60_000)

    def stop_alarm(self):
        if not self.alarm_active:
            return
        self.alarm_active = False
        self.alarm_end_timer.stop()
        self.char.stop_shake()
        self.shout.hide()
        self.restore_mood()

    # ---------------------------------------------------------- 설정
    def open_settings(self):
        self.hide_bubbles()
        dlg = SettingsDialog(self.cfg)
        dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        if dlg.exec():
            try:
                set_autostart(self.cfg["autostart"])
            except OSError as ex:
                QMessageBox.warning(None, "자동 실행", f"자동 실행 설정에 실패했어요.\n{ex}")
            self.reload_excel(force=True)
            if self.alarm_active:
                self.char.set_mood("excited")
            else:
                self.restore_mood()


def main():
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:  # noqa: BLE001
            pass
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("구내식당 알리미")

    lock = QLockFile(os.path.join(config_dir(), "app.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "구내식당 알리미", "이미 실행 중이에요! 작업표시줄 트레이를 확인해 주세요.")
        return 0

    ctl = Controller(app)  # noqa: F841
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
