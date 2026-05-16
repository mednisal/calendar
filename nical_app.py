#!/usr/bin/env python3
#!/usr/bin/env python3
"""
Native Desktop Calendar Application - PyQt6
Sunday-First, 12-Hour, Dark Default, Scrollable Hours, Dynamic Columns
"""

import sys
import json
import os
import shutil
from datetime import datetime, timedelta, date, time
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QMenu, QColorDialog,
    QDialog, QLineEdit, QDialogButtonBox, QMessageBox
)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QBrush, QPen, QMouseEvent


# ============================================================================
# CONFIGURATION
# ============================================================================
CONFIG_DIR = os.path.expanduser("~/.calendar_app")
EVENTS_FILE = os.path.join(CONFIG_DIR, "events.json")
DEFAULT_COLOR = "blue"

# UI Theme Colors
UI_LIGHT = {
    "bg": QColor("#ffffff"), "grid": QColor("#e5e7eb"),
    "text": QColor("#6b7280"), "header_text": QColor("#1f2937"),
    "highlight": QColor("#3b82f6"), "weekend": QColor("#ef4444"),
}
UI_DARK = {
    "bg": QColor("#1f2937"), "grid": QColor("#374151"),
    "text": QColor("#9ca3af"), "header_text": QColor("#f3f4f6"),
    "highlight": QColor("#60a5fa"), "weekend": QColor("#f87171"),
}

# Event Bar Colors
EVT_LIGHT = {
    "blue": QColor("#3b82f6"), "red": QColor("#ef4444"),
    "green": QColor("#22c55e"), "yellow": QColor("#eab308"),
    "purple": QColor("#a855f7"), "pink": QColor("#ec4899"),
    "orange": QColor("#f97316"), "gray": QColor("#6b7280")
}
EVT_DARK = {
    "blue": QColor("#60a5fa"), "red": QColor("#f87171"),
    "green": QColor("#4ade80"), "yellow": QColor("#facc15"),
    "purple": QColor("#c084fc"), "pink": QColor("#f472b6"),
    "orange": QColor("#fb923c"), "gray": QColor("#9ca3af")
}


# ============================================================================
# EVENT MODEL
# ============================================================================
class Event:
    def __init__(self, title: str, start: datetime, end: datetime, color: str = DEFAULT_COLOR):
        self.title = title.strip() or "Untitled"
        self.start = start
        self.end = end
        self.color = color

    def __eq__(self, other):
        return (isinstance(other, Event) and 
                self.start == other.start and 
                self.end == other.end and 
                self.title == other.title)

    def __hash__(self):
        return hash((self.title, self.start, self.end))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "color": self.color
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        def parse_dt(val: Any) -> datetime:
            if isinstance(val, str):
                return datetime.fromisoformat(val)
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val)
            return datetime.now()
        start = parse_dt(data.get("start"))
        end = parse_dt(data.get("end"))
        if end <= start:
            end = start + timedelta(minutes=15)
        title = str(data.get("title", "Untitled")).strip() or "Untitled"
        color = str(data.get("color", DEFAULT_COLOR))
        return cls(title, start, end, color)


# ============================================================================
# EVENT STORAGE
# ============================================================================
class EventStore:
    def __init__(self):
        self.events: List[Event] = []
        self._load()

    def _load(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if not os.path.exists(EVENTS_FILE):
            return
        try:
            with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            if not isinstance(raw, list):
                raise ValueError("Root must be a JSON array")
            self.events = []
            for i, item in enumerate(raw):
                if not isinstance(item, dict):
                    continue
                try:
                    self.events.append(Event.from_dict(item))
                except Exception as e:
                    print(f"Warning: Skipping event {i}: {e}")
        except json.JSONDecodeError as e:
            self._handle_corruption(f"JSON parse error: {e}")
        except Exception as e:
            self._handle_corruption(str(e))

    def _handle_corruption(self, reason: str):
        QMessageBox.critical(
            None, "Data Error",
            f"Failed to load events: {reason}\n\n"
            f"File backed up to:\n{EVENTS_FILE}.bak\n\n"
            f"Starting with empty event list."
        )
        if os.path.exists(EVENTS_FILE):
            shutil.copy2(EVENTS_FILE, EVENTS_FILE + ".bak")
            try:
                os.remove(EVENTS_FILE)
            except OSError:
                pass
        self.events = []

    def save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump([e.to_dict() for e in self.events], f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(None, "Save Error", f"Failed to save events: {e}")

    def add(self, ev: Event):
        self.events.append(ev)
        self.save()

    def remove(self, ev: Event):
        if ev in self.events:
            self.events.remove(ev)
            self.save()

    def update(self, ev: Event, title: str, color: str):
        if ev in self.events:
            ev.title = title.strip() or "Untitled"
            ev.color = color
            self.save()

    def get_for_day(self, d: date) -> List[Event]:
        return [e for e in self.events if e.start.date() == d]


# ============================================================================
# EVENT EDIT DIALOG
# ============================================================================
class EventEditDialog(QDialog):
    def __init__(self, event: Optional[Event], store: EventStore, new_event: bool,
                 start: Optional[datetime] = None, end: Optional[datetime] = None, 
                 dark_mode: bool = False):
        super().__init__()
        self.store = store
        self.event = event
        self.new_event = new_event
        self.dark_mode = dark_mode
        self.evt_colors = EVT_DARK if dark_mode else EVT_LIGHT
        
        if event:
            self.start_dt = start if start is not None else event.start
            self.end_dt = end if end is not None else event.end
        else:
            self.start_dt = start or datetime.now()
            self.end_dt = end or (self.start_dt + timedelta(hours=1))
        
        self.selected_color = event.color if event else DEFAULT_COLOR
        self.setWindowTitle("Edit Event" if not new_event else "New Event")
        self.setModal(True)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Title:"))
        self.title_inp = QLineEdit()
        self.title_inp.setPlaceholderText("Enter event title")
        if event:
            self.title_inp.setText(event.title)
        layout.addWidget(self.title_inp)

        time_text = f"Time: {self.start_dt.strftime('%I:%M %p').lstrip('0')} – {self.end_dt.strftime('%I:%M %p').lstrip('0')}"
        layout.addWidget(QLabel(time_text))

        layout.addWidget(QLabel("Color:"))
        self.color_btn = QPushButton("Select Color")
        self.color_btn.clicked.connect(self._pick_color)
        layout.addWidget(self.color_btn)
        self._update_color_btn()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.title_inp.setFocus()

    def _update_color_btn(self):
        color_val = self.evt_colors.get(self.selected_color, QColor(self.selected_color))
        fg = "#ffffff" if color_val.lightness() < 128 else "#000000"
        self.color_btn.setStyleSheet(
            f"background-color: {color_val.name()}; color: {fg}; font-weight: bold; border-radius: 4px;"
        )

    def _pick_color(self):
        current = self.evt_colors.get(self.selected_color, QColor(self.selected_color))
        chosen = QColorDialog.getColor(current, self, "Select Event Color")
        if chosen.isValid():
            matched = next((n for n, c in self.evt_colors.items() if c.rgb() == chosen.rgb()), None)
            self.selected_color = matched or chosen.name()
            self._update_color_btn()

    def accept(self):
        title = self.title_inp.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation Error", "Event title cannot be empty.")
            self.title_inp.setFocus()
            return
        if self.new_event:
            new_ev = Event(title, self.start_dt, self.end_dt, self.selected_color)
            self.store.add(new_ev)
        else:
            self.store.update(self.event, title, self.selected_color)
        super().accept()


# ============================================================================
# WEEK GRID WIDGET
# ============================================================================
class WeekGridWidget(QWidget):
    START_HOUR = 18  # 6 PM
    TIME_W_RATIO = 0.08
    HEAD_H = 30
    HOUR_H = 60

    def __init__(self, week_start: date, store: EventStore, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self.week_start = week_start
        self.store = store
        self.dark_mode = dark_mode
        self.ui_colors = UI_DARK if dark_mode else UI_LIGHT
        self.evt_colors = EVT_DARK if dark_mode else EVT_LIGHT
        
        self._drag_start: Optional[QPoint] = None
        self._drag_curr: Optional[QPoint] = None
        self._drag_col = -1
        self._dragging = False
        
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def sizeHint(self) -> QSize:
        # Height is fixed (24 hours), Width is handled by parent
        return QSize(1000, self.HEAD_H + self.HOUR_H * 24)

    def _get_dims(self):
        # Safety guards to prevent crashes during init/resize
        w = max(100, self.width())
        h = max(100, self.height())
        time_w = max(40, int(w * self.TIME_W_RATIO))
        day_w = max(20, (w - time_w) / 7.0)
        return w, h, time_w, day_w

    @staticmethod
    def _format_12h(hour_24: int) -> str:
        if hour_24 == 0: return "12 AM"
        if hour_24 < 12: return f"{hour_24} AM"
        if hour_24 == 12: return "12 PM"
        return f"{hour_24 - 12} PM"

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        _, _, time_w, day_w = self._get_dims()

        painter.fillRect(self.rect(), self.ui_colors["bg"])

        pen = QPen(self.ui_colors["grid"])
        painter.setPen(pen)
        
        # Vertical grid lines
        for i in range(8):
            x = time_w + i * day_w
            painter.drawLine(int(x), int(self.HEAD_H), int(x), int(self.height()))
        
        # Horizontal grid lines (24 hours starting from 6 PM)
        for h in range(24):
            y = self.HEAD_H + h * self.HOUR_H
            painter.drawLine(int(time_w), int(y), int(self.width()), int(y))

        # Time labels (12-hour format)
        painter.setPen(self.ui_colors["text"])
        painter.setFont(QFont("Arial", 8))
        for h in range(24):
            actual_hour = (self.START_HOUR + h) % 24
            y = self.HEAD_H + h * self.HOUR_H + 12
            painter.drawText(5, int(y), self._format_12h(actual_hour))

        # Day headers
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        for col in range(7):
            day = self.week_start + timedelta(days=col)
            x = time_w + col * day_w + 5
            label = day.strftime("%a %d")
            
            if day == date.today():
                painter.setPen(self.ui_colors["highlight"])
            elif day.weekday() in (4, 5):  # Friday & Saturday blue
                painter.setPen(self.ui_colors["highlight"])
            else:
                painter.setPen(self.ui_colors["header_text"])
            painter.drawText(int(x), int(self.HEAD_H - 10), label)

        # Events
        grid_start_min = self.START_HOUR * 60
        for col in range(7):
            day = self.week_start + timedelta(days=col)
            events = sorted(self.store.get_for_day(day), key=lambda e: e.start)
            for ev in events:
                start_min = ev.start.hour * 60 + ev.start.minute
                end_min = ev.end.hour * 60 + ev.end.minute
                
                start_offset = (start_min - grid_start_min) % 1440
                end_offset = (end_min - grid_start_min) % 1440
                if end_offset <= start_offset:
                    end_offset += 1440
                    
                height_px = max(5, (end_offset - start_offset) / 60 * self.HOUR_H)
                top_px = self.HEAD_H + start_offset / 60 * self.HOUR_H
                x = time_w + col * day_w + 2
                width = day_w - 4
                
                color = self.evt_colors.get(ev.color, QColor(ev.color))
                painter.setBrush(QBrush(color.lighter(110)))
                painter.setPen(QPen(color.darker(110)))
                rect = QRect(int(x), int(top_px), int(width), int(height_px))
                painter.drawRoundedRect(rect, 4, 4)
                
                text_color = QColor("#f3f4f6") if self.dark_mode else QColor("#000000")
                painter.setPen(text_color)
                painter.setFont(QFont("Arial", 9))
                text = ev.title if len(ev.title) <= 15 else ev.title[:13] + ".."
                painter.drawText(rect.adjusted(4, 4, -4, -4),
                               Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, text)

        if self._dragging and self._drag_start and self._drag_curr:
            self._draw_drag_preview(painter, time_w, day_w, grid_start_min)

    def _draw_drag_preview(self, painter: QPainter, time_w: float, day_w: float, grid_start_min: int):
        y1, y2 = self._drag_start.y(), self._drag_curr.y()
        if y1 < self.HEAD_H or y2 < self.HEAD_H:
            return
            
        rel_start = min(y1, y2) - self.HEAD_H
        rel_end = max(y1, y2) - self.HEAD_H
        
        start_off = int((rel_start / self.HOUR_H * 60) + grid_start_min) % 1440
        end_off = int((rel_end / self.HOUR_H * 60) + grid_start_min) % 1440
        if end_off <= start_off: end_off += 1440
        
        top = self.HEAD_H + start_off / 60 * self.HOUR_H
        height = (end_off - start_off) / 60 * self.HOUR_H
        x = time_w + self._drag_col * day_w + 2
        width = day_w - 4
        
        preview = QColor("#3b82f6")
        preview.setAlpha(100)
        painter.setBrush(QBrush(preview))
        painter.setPen(QPen(preview.darker(120)))
        painter.drawRoundedRect(int(x), int(top), int(width), int(height), 4, 4)

    def _y_to_minutes(self, y: int) -> int:
        return int(((y - self.HEAD_H) / self.HOUR_H * 60 + self.START_HOUR * 60) % 1440)

    def _get_event_at(self, pos: QPoint) -> Optional[Event]:
        if pos.y() < self.HEAD_H:
            return None
        _, _, time_w, day_w = self._get_dims()
        col = int((pos.x() - time_w) // day_w)
        if not (0 <= col <= 6):
            return None
            
        day = self.week_start + timedelta(days=col)
        click_min = self._y_to_minutes(pos.y())
        
        for ev in self.store.get_for_day(day):
            ev_start = ev.start.hour * 60 + ev.start.minute
            ev_end = ev.end.hour * 60 + ev.end.minute
            check_click = click_min + 1440 if (ev_end <= ev_start and click_min < ev_start) else click_min
            if ev_start <= check_click < ev_end:
                return ev
        return None

    def _notify_parent(self):
        parent = self.parent()
        if parent and hasattr(parent, 'refresh_view'):
            parent.refresh_view()

    def mousePressEvent(self, event: QMouseEvent):
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.RightButton:
            ev = self._get_event_at(pos)
            if ev:
                self._show_context_menu(ev, event.globalPosition().toPoint())
            return
        if event.button() == Qt.MouseButton.LeftButton and pos.y() >= self.HEAD_H:
            _, _, time_w, day_w = self._get_dims()
            col = int((pos.x() - time_w) // day_w)
            if 0 <= col <= 6:
                self._drag_start = pos
                self._drag_curr = pos
                self._drag_col = col
                self._dragging = True

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging and self._drag_start:
            self._drag_curr = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if not self._dragging or event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = False
        if self._drag_start and self._drag_curr and self._drag_col >= 0:
            y1, y2 = self._drag_start.y(), self._drag_curr.y()
            if y1 >= self.HEAD_H and y2 >= self.HEAD_H:
                start_min = self._y_to_minutes(min(y1, y2))
                end_min = self._y_to_minutes(max(y1, y2))
                
                start_min = max(0, (start_min // 15) * 15)
                end_min = max(start_min + 15, ((end_min + 14) // 15) * 15)
                if end_min >= 1440: end_min = 1439
                
                day = self.week_start + timedelta(days=self._drag_col)
                base = datetime.combine(day, time(0, 0))
                start_dt = base + timedelta(minutes=start_min)
                end_dt = base + timedelta(minutes=end_min)
                
                dlg = EventEditDialog(
                    None, self.store, new_event=True,
                    start=start_dt, end=end_dt,
                    dark_mode=self.dark_mode
                )
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self._notify_parent()
        self._drag_start = None
        self._drag_curr = None
        self._drag_col = -1
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if pos.y() < self.HEAD_H:
            return
        _, _, time_w, day_w = self._get_dims()
        col = int((pos.x() - time_w) // day_w)
        if not (0 <= col <= 6):
            return
            
        day = self.week_start + timedelta(days=col)
        hour_24 = self._y_to_minutes(pos.y()) // 60
        start_dt = datetime.combine(day, time(hour_24, 0))
        end_dt = start_dt + timedelta(hours=1)
        
        dlg = EventEditDialog(
            None, self.store, new_event=True,
            start=start_dt, end=end_dt,
            dark_mode=self.dark_mode
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._notify_parent()

    def _show_context_menu(self, event: Event, global_pos: QPoint):
        menu = QMenu(self)
        if self.dark_mode:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #1f2937;
                    color: #f3f4f6;
                    border: 1px solid #374151;
                }
                QMenu::item:selected {
                    background-color: #374151;
                }
            """)
        def do_rename():
            dlg = EventEditDialog(
                event, self.store, new_event=False,
                dark_mode=self.dark_mode
            )
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.update()
                self._notify_parent()
        def do_color():
            current = self.evt_colors.get(event.color, QColor(event.color))
            chosen = QColorDialog.getColor(current, self, "Select Color")
            if chosen.isValid():
                name = next(
                    (n for n, c in self.evt_colors.items() if c.rgb() == chosen.rgb()),
                    chosen.name()
                )
                self.store.update(event, event.title, name)
                self.update()
                self._notify_parent()
        def do_delete():
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Delete event \"{event.title}\"?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.store.remove(event)
                self.update()
                self._notify_parent()
        menu.addAction("Rename", do_rename)
        menu.addAction("Change Color", do_color)
        menu.addSeparator()
        menu.addAction("Delete", do_delete)
        menu.exec(global_pos)


# ============================================================================
# WEEK VIEW CONTAINER
# ============================================================================
class WeekView(QWidget):
    def __init__(self, week_start: date, store: EventStore, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self.store = store
        self.dark_mode = dark_mode
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        if dark_mode:
            self.setStyleSheet("background-color: #1f2937;")
        
        self.scroll = QScrollArea()
        # Keep this False to enable vertical scrolling of the 24-hour grid
        self.scroll.setWidgetResizable(False) 
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        viewport = self.scroll.viewport()
        viewport.setStyleSheet(f"background-color: {UI_DARK['bg'].name() if dark_mode else UI_LIGHT['bg'].name()};")
        viewport.setAutoFillBackground(True)
        
        self.grid = WeekGridWidget(week_start, store, self, dark_mode)
        self.scroll.setWidget(self.grid)
        layout.addWidget(self.scroll)

        # FIX: Use QTimer to sync width after the layout is fully initialized
        # This prevents the "squashed" look when switching weeks/themes
        QTimer.singleShot(100, self._sync_width)

    def resizeEvent(self, event):
    	super().resizeEvent(event)
    # Delay the sync slightly to ensure proper sizing
    	QTimer.singleShot(50, self._sync_width)

    def _sync_width(self):
    	"""Force grid to fill the horizontal space of the viewport"""
    	if hasattr(self, 'scroll') and hasattr(self, 'grid'):
        	vp = self.scroll.viewport()
        	if vp.width() > 0:
            # Ensure the grid fills the viewport width
            		new_width = max(vp.width(), self.grid.sizeHint().width())
            		self.grid.resize(new_width, self.grid.sizeHint().height())
            # Force a repaint
            		self.grid.update()

    def refresh_view(self):
        self.grid.update()


# ============================================================================
# MAIN APPLICATION
# ============================================================================
class CalendarApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = EventStore()
        self.current_date = date.today()
        self.dark_mode = True  # Default to dark
        
        self.setWindowTitle("My Calendar")
        self.resize(1100, 750)
        
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        toolbar = QHBoxLayout()
        for label_text, callback in [("<", lambda: self._shift_week(-1)), 
                                      (">", lambda: self._shift_week(1))]:
            btn = QPushButton(label_text)
            btn.setFixedWidth(40)
            btn.clicked.connect(callback)
            toolbar.addWidget(btn)
        
        today_btn = QPushButton("Today")
        today_btn.clicked.connect(self._go_to_today)
        toolbar.addWidget(today_btn)
        
        self.week_label = QLabel()
        self.week_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        toolbar.addWidget(self.week_label)
        
        toolbar.addStretch()
        
        # FIX: Ensure the icon is visible. 
        # Since dark_mode is True, we show the Sun icon (to switch to light)
        self.theme_btn = QPushButton("☀️")
        self.theme_btn.setFixedWidth(40)
        self.theme_btn.setToolTip("Toggle Dark Mode")
        self.theme_btn.clicked.connect(self._toggle_theme)
        toolbar.addWidget(self.theme_btn)
        
        main_layout.addLayout(toolbar)
        
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout(self.view_container)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.view_container, 1)
        
        self._apply_theme()
        self._render_week_view()

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        # Update icon: If dark, show Sun. If light, show Moon.
        self.theme_btn.setText("☀️" if self.dark_mode else "🌙")
        self._apply_theme()
        self._render_week_view()

    def _apply_theme(self):
        app = QApplication.instance()
        if not app:
            return
        if self.dark_mode:
            app.setStyleSheet("""
                QMainWindow { background-color: #1f2937; }
                QWidget { background-color: #1f2937; color: #f3f4f6; }
                QPushButton {
                    background-color: #374151;
                    color: #f3f4f6;
                    border: 1px solid #4b5563;
                    border-radius: 4px;
                    padding: 4px;
                }
                QPushButton:hover { background-color: #4b5563; }
                QPushButton:pressed { background-color: #6b7280; }
                QLabel { color: #f3f4f6; }
                QScrollArea { background-color: #1f2937; border: none; }
                QScrollBar:vertical {
                    background-color: #374151;
                    width: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background-color: #6b7280;
                    border-radius: 6px;
                    min-height: 20px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
                QScrollBar:horizontal {
                    background-color: #374151;
                    height: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #6b7280;
                    border-radius: 6px;
                    min-width: 20px;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
            """)
        else:
            app.setStyleSheet("")

    def _render_week_view(self):
        while self.view_layout.count():
            child = self.view_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        days_since_sunday = (self.current_date.weekday() + 1) % 7
        week_start = self.current_date - timedelta(days=days_since_sunday)
        week_end = week_start + timedelta(days=6)
        
        self.week_view = WeekView(week_start, self.store, self, dark_mode=self.dark_mode)
        self.view_layout.addWidget(self.week_view)
        self.week_label.setText(
            f"Week: {week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
        )

    def refresh_view(self):
        self._render_week_view()

    def _shift_week(self, offset: int):
        self.current_date += timedelta(weeks=offset)
        self._render_week_view()

    def _go_to_today(self):
        self.current_date = date.today()
        self._render_week_view()


# ============================================================================
# ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("My Calendar")
    
    window = CalendarApp()
    window.show()
    
    sys.exit(app.exec())
