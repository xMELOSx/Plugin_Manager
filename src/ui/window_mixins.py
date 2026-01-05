""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import ctypes
from ctypes.wintypes import HWND, MSG, POINT, RECT
from PyQt6.QtCore import Qt, QPoint, QEvent, QEasingCurve, QPropertyAnimation, QRect
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QCursor
import os
import json
from src.core.file_handler import FileHandler

# Win32 Constants
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

import logging
import ctypes
from ctypes import wintypes

class Win32Mixin:
    """Handles Windows specific API calls."""
    
    def set_always_on_top(self, on_top: bool):
        """Use Win32 API to set always on top without flicker."""
        try:
            logger = logging.getLogger(self.__class__.__name__)
            hwnd = int(self.winId())
            
            # HWND_TOPMOST = -1, HWND_NOTOPMOST = -2
            # Must cast to pointer-sized integer for 64-bit compatibility
            HWND_TOPMOST = ctypes.c_void_p(-1)
            HWND_NOTOPMOST = ctypes.c_void_p(-2)
            order = HWND_TOPMOST if on_top else HWND_NOTOPMOST
            
            # Flags
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            
            ret = ctypes.windll.user32.SetWindowPos(
                hwnd, 
                order, 
                0, 0, 0, 0, 
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )
            
            if ret == 0:
                error_code = ctypes.windll.kernel32.GetLastError()
                logger.error(f"SetWindowPos failed with error code: {error_code}")
            else:
                logger.info(f"SetWindowPos success: HWND={hwnd}, TopMost={on_top}")
                
        except Exception as e:
            msg = f"Win32 API Error in set_always_on_top: {e}"
            print(msg)
            if hasattr(self, 'logger'):
                self.logger.error(msg)



class DraggableMixin:
    """Handles dragging logic. Requires 'title_bar' attribute in usage."""
    
    def init_drag(self):
        self.draggable = False
        self._drag_pos = QPoint()

    def handle_drag_press(self, event):
        # Allow dragging if specific conditions met (handled in MouseHandlerMixin usually)
        # But here we just set the flag/pos
        self._drag_pos = event.globalPosition().toPoint() - self.pos()
        self.draggable = True
        
    def handle_drag_move(self, event):
        if self.draggable and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            
    def handle_drag_release(self, event):
        self.draggable = False

class ResizableMixin:
    """Handles 8-way resizing logic."""
    
    def init_resize(self):
        self.resizable = True
        self._resizing = False
        self._resize_edges = ""
        self.setMouseTracking(True)
        
    def _get_resize_edges(self, pos: QPoint):
        w, h = self.width(), self.height()
        m = 10 # Margin increased for better grab area (especially diagonal handles)
        edges = ""
        
        # Check edges
        if pos.y() < m: edges += "Top"
        elif pos.y() > h - m: edges += "Bottom"
        
        if pos.x() < m: edges += "Left"
        elif pos.x() > w - m: edges += "Right"
        
        return edges

    def _update_cursor(self, edges):
        resize_shapes = [
            Qt.CursorShape.SizeVerCursor,
            Qt.CursorShape.SizeHorCursor,
            Qt.CursorShape.SizeFDiagCursor,
            Qt.CursorShape.SizeBDiagCursor
        ]
        
        current = self.cursor().shape()
        
        if not edges:
            # Only reset to Arrow if we were previously showing a resize cursor.
            # This avoids overriding custom cursors (like PointingHand) of child widgets.
            if current in resize_shapes:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return
            
        target = Qt.CursorShape.ArrowCursor
        if edges == "Top" or edges == "Bottom":
            target = Qt.CursorShape.SizeVerCursor
        elif edges == "Left" or edges == "Right":
            target = Qt.CursorShape.SizeHorCursor
        elif edges in ["TopLeft", "BottomRight"]:
            target = Qt.CursorShape.SizeFDiagCursor
        elif edges in ["TopRight", "BottomLeft"]:
            target = Qt.CursorShape.SizeBDiagCursor
            
        if current != target:
            self.setCursor(target)

    def handle_resize_press(self, event):
        if self.resizable:
            edges = self._get_resize_edges(event.pos())
            if edges:
                self._resizing = True
                self._resize_edges = edges
                return True
        return False

    def handle_resize_move(self, event):
        # Cursor update is handled in eventFilter or MouseMove
        if self.resizable and not self._resizing:
            # We are just hovering
            pass # handled by caller

        if self.resizable and self._resizing:
            global_pos = event.globalPosition().toPoint()
            rect = self.geometry()
            
            if "Left" in self._resize_edges:
                new_w = rect.right() - global_pos.x()
                if new_w > self.minimumWidth():
                    rect.setLeft(global_pos.x())
            elif "Right" in self._resize_edges:
                new_w = global_pos.x() - rect.left()
                if new_w > self.minimumWidth():
                    rect.setRight(global_pos.x())
            
            if "Top" in self._resize_edges:
                new_h = rect.bottom() - global_pos.y()
                if new_h > self.minimumHeight():
                    rect.setTop(global_pos.y())
            elif "Bottom" in self._resize_edges:
                new_h = global_pos.y() - rect.top()
                if new_h > self.minimumHeight():
                    rect.setBottom(global_pos.y())
                    
            self.setGeometry(rect)

    def handle_resize_release(self, event):
        self._resizing = False
        self.setCursor(Qt.CursorShape.ArrowCursor)


class OptionsMixin:
    """Handles saving and restoring window options (position, size, visibility)."""
    
    def _get_config_path(self):
        project_root = FileHandler().project_root
        return os.path.join(project_root, "config", "window.json")

    def _read_window_config(self):
        path = self._get_config_path()
        if not os.path.exists(path):
            return {}
        try:
            content = FileHandler().read_text_file(path)
            return json.loads(content)
        except:
            return {}

    def _write_window_config(self, data):
        path = self._get_config_path()
        try:
            FileHandler().write_text_file(path, json.dumps(data, indent=4))
        except Exception as e:
            print(f"Failed to write window config: {e}")

    def save_options(self, key_prefix: str, extra_data: dict = None):
        """Saves current geometry and state to JSON file.
        
        Only saves if 'save_window_state' flag in extra_data is True (or not present).
        """
        # Check if saving is enabled (default: True)
        save_enabled = True
        if extra_data and 'save_window_state' in extra_data:
            save_enabled = extra_data.get('save_window_state', True)
        
        config = self._read_window_config()
        
        rect = self.geometry()
        options = {
            'geometry': [rect.x(), rect.y(), rect.width(), rect.height()],
            'is_maximized': self.isMaximized(),
            'opacity': 1.0, # Force save opaque, we handle transparency internally via paintEvent
            'always_on_top': getattr(self, '_always_on_top', False)
        }
        
        # Also save search if available
        if hasattr(self, 'search_bar'):
             options['search_text'] = self.search_bar.text()
        
        # Merge extra data (e.g. display overrides)
        if extra_data:
            options.update(extra_data)
        
        # Only update geometry if saving is enabled
        if save_enabled:
            config[key_prefix] = options
        else:
            # Preserve existing geometry, update only non-geometry fields
            existing = config.get(key_prefix, {})
            for k, v in options.items():
                if k not in ['geometry', 'is_maximized']:
                    existing[k] = v
            config[key_prefix] = existing
             
        self._write_window_config(config)

    def load_options(self, key_prefix: str):
        """Restores geometry and state from JSON file."""
        config = self._read_window_config()
        data = config.get(key_prefix)
        
        if not data:
            return None # Allow caller to know no data was found
            
        try:
            # Only restore geometry if save_window_state was enabled
            if data.get('save_window_state', True):
                geo = data.get('geometry')
                if geo and len(geo) == 4:
                    self.setGeometry(geo[0], geo[1], geo[2], geo[3])
                
                if data.get('is_maximized'):
                    self.showMaximized()
            
            # Restore opacity
            # Restore opacity - DISABLED to prevent artifacting with paintEvent transparency
            # Opacity is now handled via _bg_opacity and paintEvent
            if hasattr(self, 'setWindowOpacity'):
                 self.setWindowOpacity(1.0) # Force opaque to ensure visibility
            # if 'opacity' in data and hasattr(self, 'setWindowOpacity'):
            #     self.setWindowOpacity(data['opacity'])
            
            # Restore always_on_top
            if 'always_on_top' in data and hasattr(self, 'set_always_on_top'):
                is_pinned = data['always_on_top']
                self._always_on_top = is_pinned
                self.set_always_on_top(is_pinned)
            
            # Restore search
            if hasattr(self, 'search_bar') and data.get('search_text'):
                self.search_bar.setText(data['search_text'])
                
            return data # Return full data to allow caller to extract extra fields
        except Exception as e:
            print(f"Error loading options for {key_prefix}: {e}")
            return None
