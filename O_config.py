"""설정 / 하트 저장."""
from __future__ import annotations

import json
import os
import sys

APP_NAME = "EatNotifier"

MOODS = ("normal", "joy", "excited", "holiday")
MOOD_LABELS = {
    "normal": "기본",
    "joy": "기쁨 (하트 눌렀을 때)",
    "excited": "흥분 (점심 알림)",
    "holiday": "휴일 (비우면 기쁨 이미지)",
}

DEFAULTS = {
    "images": {m: "" for m in MOODS},
    "excel_folder": "",
    "default_corner": "A",
    "alarm_enabled": True,
    "alarm_time": "11:30",
    "char_size": 140,
    "autostart": False,
    "pos": None,
}


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _path(name: str) -> str:
    return os.path.join(config_dir(), name)


def _load_json(name: str, default):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save_json(name: str, data) -> None:
    tmp = _path(name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path(name))


class Config:
    def __init__(self):
        data = _load_json("config.json", {})
        self.first_run = not data
        self.data = json.loads(json.dumps(DEFAULTS))
        for k, v in data.items():
            if k == "images" and isinstance(v, dict):
                self.data["images"].update(v)
            elif k in self.data:
                self.data[k] = v

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v

    def save(self):
        _save_json("config.json", self.data)


class Hearts:
    """먹고 싶은 메뉴 표시. key = 'YYYY-MM-DD|A|메뉴명'"""

    def __init__(self):
        self.keys: set[str] = set(_load_json("hearts.json", []))

    @staticmethod
    def key(date, corner, item) -> str:
        return f"{date.isoformat()}|{corner}|{item}"

    def has(self, date, corner, item) -> bool:
        return self.key(date, corner, item) in self.keys

    def toggle(self, date, corner, item) -> bool:
        k = self.key(date, corner, item)
        if k in self.keys:
            self.keys.remove(k)
            on = False
        else:
            self.keys.add(k)
            on = True
        _save_json("hearts.json", sorted(self.keys))
        return on


def set_autostart(enabled: bool) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    if getattr(sys, "frozen", False):
        cmd = f'"{sys.executable}"'
    else:
        pyw = sys.executable.replace("python.exe", "pythonw.exe")
        cmd = f'"{pyw}" "{os.path.abspath(sys.argv[0])}"'
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    )
    try:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)
    return True
