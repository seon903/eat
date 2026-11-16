"""구내식당 주간 식단 엑셀 파서.

엑셀 구조 (예시):
  A1 : '11.16(월)~'              -> 주 시작일
  6행: '16월', '17화', ...        -> 요일 헤더 (열 = 날짜)
  각 열을 위에서 아래로 읽으며
    <A코너> ... <B코너> ... <공통> ...
  <공통> 이하(칼로리, 샐러드도시락 등)는 무시한다.
  "한그릇" 처럼 따옴표로 감싼 항목은 태그.
  '&'로 시작하는 줄은 바로 윗줄 메뉴에 붙인다.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field

import openpyxl

WEEKDAYS = "월화수목금토일"
HEADER_RE = re.compile(r"^\s*(\d{1,2})\s*\(?\s*([월화수목금토일])\s*\)?\s*$")
START_RE = re.compile(r"(\d{1,2})\s*[./-]\s*(\d{1,2})")
MARKER_RE = re.compile(r"^\s*<\s*(.+?)\s*>\s*$")
QUOTE_RE = re.compile(r'^\s*["“”\'‘’](.+?)["“”\'‘’]\s*$')
STOP_WORDS = ("공통", "칼로리")
STOP_ROW_LABELS = ("샐러드", "도시락")


@dataclass
class Corner:
    tags: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)


@dataclass
class DayMenu:
    date: dt.date
    corners: dict[str, Corner] = field(default_factory=dict)  # 'A', 'B'


def _text(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _find_header_row(ws) -> tuple[int, dict[int, tuple[int, str]]] | None:
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 40)):
        found = {}
        for c in row:
            m = HEADER_RE.match(_text(c.value))
            if m:
                found[c.column] = (int(m.group(1)), m.group(2))
        if len(found) >= 2:
            return row[0].row, found
    return None


def _find_start_date(ws, today: dt.date) -> dt.date | None:
    for row in ws.iter_rows(min_row=1, max_row=5, max_col=3):
        for c in row:
            v = c.value
            if isinstance(v, dt.datetime):
                return v.date()
            if isinstance(v, dt.date):
                return v
            m = START_RE.search(_text(v))
            if m:
                mon, day = int(m.group(1)), int(m.group(2))
                year = today.year
                # 연말/연초 보정
                if mon == 12 and today.month == 1:
                    year -= 1
                elif mon == 1 and today.month == 12:
                    year += 1
                try:
                    return dt.date(year, mon, day)
                except ValueError:
                    return None
    return None


def _resolve_date(day: int, wd: str, start: dt.date | None, today: dt.date) -> dt.date | None:
    """헤더의 '16월' 같은 값을 실제 날짜로 변환."""
    want_wd = WEEKDAYS.index(wd)
    base = start or (today - dt.timedelta(days=today.weekday()))
    for off in range(-7, 15):
        d = base + dt.timedelta(days=off)
        if d.day == day and d.weekday() == want_wd:
            return d
    for off in range(0, 15):  # 요일이 어긋나도 날짜만 맞으면 허용
        d = base + dt.timedelta(days=off)
        if d.day == day:
            return d
    return None


def _corner_key(marker: str) -> str | None:
    m = marker.upper()
    if any(w in marker for w in STOP_WORDS):
        return "STOP"
    if "A" in m:
        return "A"
    if "B" in m:
        return "B"
    if "C" in m:
        return "C"
    return None


def parse_workbook(path: str, today: dt.date | None = None) -> dict[dt.date, DayMenu]:
    today = today or dt.date.today()
    # 엑셀에서 열려 있어도 읽을 수 있도록 임시 복사본 사용
    tmpdir = tempfile.mkdtemp(prefix="eatmenu_")
    tmp = os.path.join(tmpdir, "menu.xlsx")
    try:
        shutil.copy2(path, tmp)
        wb = openpyxl.load_workbook(tmp, data_only=True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    result: dict[dt.date, DayMenu] = {}
    for ws in wb.worksheets:
        hdr = _find_header_row(ws)
        if not hdr:
            continue
        header_row, cols = hdr
        start = _find_start_date(ws, today)
        for col, (day, wd) in cols.items():
            date = _resolve_date(day, wd, start, today)
            if not date:
                continue
            dm = DayMenu(date=date)
            current: Corner | None = None
            for r in range(header_row + 1, ws.max_row + 1):
                label = _text(ws.cell(r, 1).value)
                if any(w in label for w in STOP_ROW_LABELS):
                    break
                val = _text(ws.cell(r, col).value)
                if not val:
                    continue
                mk = MARKER_RE.match(val)
                if mk:
                    key = _corner_key(mk.group(1))
                    if key == "STOP":
                        break
                    if key:
                        current = dm.corners.setdefault(key, Corner())
                    else:
                        current = None
                    continue
                if current is None:
                    continue
                q = QUOTE_RE.match(val)
                if q:
                    current.tags.append(q.group(1).strip())
                elif val.startswith("&") and current.items:
                    current.items[-1] = f"{current.items[-1]} & {val[1:].strip()}"
                else:
                    current.items.append(val)
            if dm.corners:
                result[date] = dm
    return result


def find_latest_excel(folder: str) -> str | None:
    if not folder or not os.path.isdir(folder):
        return None
    best, best_m = None, -1.0
    for name in os.listdir(folder):
        if name.startswith("~$") or not name.lower().endswith((".xlsx", ".xlsm")):
            continue
        p = os.path.join(folder, name)
        try:
            m = os.path.getmtime(p)
        except OSError:
            continue
        if m > best_m:
            best, best_m = p, m
    return best


if __name__ == "__main__":
    import sys

    data = parse_workbook(sys.argv[1], dt.date(2026, 11, 16))
    for d, dm in sorted(data.items()):
        print("==", d, WEEKDAYS[d.weekday()])
        for k, c in dm.corners.items():
            print(f"  [{k}] tags={c.tags}")
            for it in c.items:
                print("     -", it)
