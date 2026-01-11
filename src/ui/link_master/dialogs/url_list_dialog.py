""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import json
import webbrowser
import urllib.request
import urllib.error
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox, QMenu,
    QAbstractItemView, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from src.core.lang_manager import _
from src.ui.common_widgets import StyledLineEdit, ProtectedLineEdit
from src.ui.slide_button import SlideButton
from src.ui.styles import TooltipStyles


class URLItemWidget(QWidget):
    """Custom widget for each URL item in the list."""
    removed = pyqtSignal(object)
    changed = pyqtSignal()
    
    def __init__(self, data: dict, is_marked: bool = False, parent_dialog=None):
        super().__init__()
        self.url = data.get('url', '')
        self.is_active = data.get('active', True)
        self.is_marked = is_marked
        self.parent_dialog = parent_dialog
        self._init_ui()
    
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(5)
        
        # Drag Handle (☰)
        drag_label = QLabel("☰")
        drag_label.setFixedWidth(24)
        drag_label.setStyleSheet("color: #888; font-size: 14px;")
        drag_label.setCursor(Qt.CursorShape.SizeAllCursor)
        layout.addWidget(drag_label)
        
        # Active Toggle (👁/🌑)
        self.active_btn = QPushButton("👁" if self.is_active else "🌑")
        self.active_btn.setFixedWidth(36)
        self.active_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.active_btn.setToolTip(_("Toggle URL Active/Inactive"))
        self.active_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 16px; } QPushButton:hover { background-color: #444; border-radius: 4px; }")
        self.active_btn.clicked.connect(self._toggle_active)
        layout.addWidget(self.active_btn)

        # Mark indicator (🔗 for last working URL)
        self.mark_btn = QPushButton("🔗" if self.is_marked else "  ")
        self.mark_btn.setFixedWidth(36)
        self.mark_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mark_btn.setToolTip(_("Mark as Preferred (Fast Access)"))
        mark_color = "#2ecc71" if self.is_marked else "#888"
        self.mark_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; font-size: 16px; color: {mark_color}; }} QPushButton:hover {{ background-color: #444; border-radius: 4px; }}")
        self.mark_btn.clicked.connect(self._mark_as_preferred)
        layout.addWidget(self.mark_btn)
        
        # URL Label
        self.url_label = QLabel(self.url)
        self.url_label.setToolTip(self.url)
        self.url_label.setStyleSheet("color: #e0e0e0;" if self.is_active else "color: #666; text-decoration: line-through;")
        self.url_label.mousePressEvent = self._start_edit
        
        self.url_edit = ProtectedLineEdit(self.url)
        self.url_edit.setStyleSheet("background-color: #3b3b3b; color: #fff; border: 1px solid #555; padding: 2px;")
        self.url_edit.returnPressed.connect(self._finish_edit)
        self.url_edit.editingFinished.connect(self._finish_edit)
        self.url_edit.hide()
        
        layout.addWidget(self.url_label, 1)
        layout.addWidget(self.url_edit, 1)
        
        btn_style = """
            QPushButton { padding: 2px; background: transparent; border: none; font-size: 14px; } 
            QPushButton:hover { background-color: #5d5d5d; border-radius: 4px; }
        """
        
        # Test connectivity (🔍)
        test_btn = QPushButton("🔍")
        test_btn.setToolTip(_("Test connectivity"))
        test_btn.setFixedWidth(36)
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.setStyleSheet(btn_style)
        test_btn.clicked.connect(self._test_url)
        layout.addWidget(test_btn)
        
        # Open in browser (🌐)
        open_btn = QPushButton("🌐")
        open_btn.setToolTip(_("Open in browser"))
        open_btn.setFixedWidth(36)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(btn_style)
        open_btn.clicked.connect(self._open_url)
        layout.addWidget(open_btn)
        
        # Delete (❌)
        del_btn = QPushButton("❌")
        del_btn.setFixedWidth(36)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(btn_style)
        del_btn.clicked.connect(self._remove)
        layout.addWidget(del_btn)
    
    def _toggle_active(self):
        self.is_active = not self.is_active
        self.active_btn.setText("👁" if self.is_active else "🌑")
        self.url_label.setStyleSheet("color: #e0e0e0;" if self.is_active else "color: #666; text-decoration: line-through;")
        self.changed.emit()

    def _start_edit(self, event):
        self.url_label.hide()
        self.url_edit.setText(self.url)
        self.url_edit.show()
        self.url_edit.setFocus()
    
    def _finish_edit(self):
        if self.url_edit.isHidden(): return
        new_url = self.url_edit.text().strip()
        if new_url and new_url != self.url:
            self.url = new_url
            self.url_label.setText(new_url)
            self.changed.emit()
        self.url_edit.hide()
        self.url_label.show()
    
    def _mark_as_preferred(self):
        if self.parent_dialog:
            self.parent_dialog.set_marked_url(self.url)

    def set_marked(self, is_marked: bool):
        self.is_marked = is_marked
        self.mark_btn.setText("🔗" if is_marked else "  ")
        self.mark_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 16px; color: #2ecc71; }" if is_marked else "QPushButton { background: transparent; border: none; font-size: 16px; color: #888; }")

    def _test_url(self):
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        try:
            req = urllib.request.Request(self.url, method='HEAD')
            req.add_header('User-Agent', user_agent)
            urllib.request.urlopen(req, timeout=5)
            QMessageBox.information(self, _("Success"), _("✅ Reachable"))
        except Exception as e:
            QMessageBox.warning(self, _("Failed"), _("❌ Failed: {error}").format(error=e))

    def _open_url(self):
        webbrowser.open(self.url)
        if self.parent_dialog:
            self.parent_dialog._on_url_opened(self.url)
    
    def _remove(self):
        self.removed.emit(self)


class URLListDialog(QDialog):
    """Dialog to manage multiple URLs with connectivity testing."""
    changed = pyqtSignal()  # Emitted when URLs change
    
    def __init__(self, parent=None, url_list_json: str = '[]', marked_url: str = None):
        super().__init__(parent)
        self.setWindowTitle(_("Manage URLs"))
        self.resize(700, 400)
        self.setStyleSheet(f"""
            QDialog {{ background-color: #1e1e1e; color: #e0e0e0; }}
            QListWidget {{ background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d; }}
            QListWidget::item {{ padding: 2px; }}
            QListWidget::item:selected {{ background-color: #3d5a80; }}
            QPushButton {{ background-color: #3d3d3d; color: #e0e0e0; padding: 5px 10px; }}
            QPushButton:hover {{ background-color: #5d5d5d; }}
            QLabel {{ color: #e0e0e0; }}
            QCheckBox {{ color: #e0e0e0; }}
            {TooltipStyles.DARK}
        """)
        
        self.url_data = []
        self.marked_url = marked_url
        self.auto_mark = False
        
        try:
            raw_data = json.loads(url_list_json) if url_list_json else []
        except:
            raw_data = []
        
        if isinstance(raw_data, dict):
            self.url_data = raw_data.get('urls', [])
            self.auto_mark = raw_data.get('auto_mark', False)
            if not self.marked_url:
                self.marked_url = raw_data.get('marked_url')
        else:
            for u in raw_data:
                if isinstance(u, str):
                    self.url_data.append({"url": u, "active": True})
                else:
                    self.url_data.append(u)
                     
        self._init_ui()
        self._load_urls()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # URL Input
        input_layout = QHBoxLayout()
        self.url_input = ProtectedLineEdit()
        self.url_input.setPlaceholderText(_("Enter URL (https://...)"))
        self.url_input.returnPressed.connect(self._add_url)
        input_layout.addWidget(self.url_input)
        
        add_btn = QPushButton("➕ " + _("Add"))
        add_btn.clicked.connect(self._add_url)
        input_layout.addWidget(add_btn)
        layout.addLayout(input_layout)

        # Header Labels (Standardized to match URLItemWidget)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(5, 5, 5, 5)
        header_layout.setSpacing(5)
        
        # Padding for drag handle area
        h_drag = QLabel("")
        h_drag.setFixedWidth(24)
        header_layout.addWidget(h_drag)
        
        h_active = QLabel(_("Active"))
        h_active.setFixedWidth(36)
        h_active.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_active.setStyleSheet("color: #aaa; font-size: 11px;")
        header_layout.addWidget(h_active)
        
        h_pref = QLabel(_("Priority"))
        h_pref.setFixedWidth(36)
        h_pref.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_pref.setStyleSheet("color: #aaa; font-size: 11px;")
        header_layout.addWidget(h_pref)
        
        h_url = QLabel("URL")
        h_url.setStyleSheet("color: #aaa; font-size: 11px; padding-left: 5px;")
        header_layout.addWidget(h_url, 1)
        
        h_test = QLabel("✓")
        h_test.setFixedWidth(36)
        h_test.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_test.setStyleSheet("color: #aaa; font-size: 11px;")
        header_layout.addWidget(h_test)
        
        h_link = QLabel(_("Link"))
        h_link.setFixedWidth(36)
        h_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_link.setStyleSheet("color: #aaa; font-size: 11px;")
        header_layout.addWidget(h_link)
        
        h_del = QLabel(_("Delete"))
        h_del.setFixedWidth(36)
        h_del.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_del.setStyleSheet("color: #aaa; font-size: 11px;")
        header_layout.addWidget(h_del)
        layout.addLayout(header_layout)
        
        # List Widget with Drag-Drop
        self.list_widget = QListWidget()
        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setDropIndicatorShown(True)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.list_widget)
        
        # Toolbar
        btns = QHBoxLayout()
        
        auto_mark_layout = QHBoxLayout()
        auto_mark_label = QLabel(_("Auto-mark last accessed URL (🔗):"))
        auto_mark_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self.auto_mark_chk = SlideButton()
        self.auto_mark_chk.setChecked(self.auto_mark)
        auto_mark_layout.addWidget(auto_mark_label)
        auto_mark_layout.addWidget(self.auto_mark_chk)
        auto_mark_layout.addStretch()
        layout.addLayout(auto_mark_layout)

        test_all_btn = QPushButton(_("🔍 Test All && Open First Working"))
        test_all_btn.clicked.connect(self._test_and_open_first)
        test_all_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        btns.addWidget(test_all_btn)
        
        clear_btn = QPushButton(_("🗑 Clear All"))
        clear_btn.clicked.connect(self._clear_all)
        btns.addWidget(clear_btn)
        btns.addStretch()
        
        ok_btn = QPushButton(_("OK"))
        ok_btn.clicked.connect(self.accept)
        btns.addWidget(ok_btn)
        
        layout.addLayout(btns)

    def _load_urls(self):
        self.list_widget.clear()
        for data in self.url_data:
            url = data.get('url', '')
            self._add_item(data, is_marked=(url == self.marked_url))

    def _add_item(self, data, is_marked=False):
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 36))
        item.setData(Qt.ItemDataRole.UserRole, data.get('url'))
        
        widget = URLItemWidget(data, is_marked, self)
        widget.removed.connect(self._on_item_removed)
        widget.changed.connect(self._sync_urls_from_list)
        
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def _add_url(self):
        url = self.url_input.text().strip()
        if url:
            new_data = {"url": url, "active": True}
            self.url_data.append(new_data)
            self._add_item(new_data)
            self.url_input.clear()

    def _on_item_removed(self, widget):
        url = widget.url
        for data in self.url_data:
            if data['url'] == url:
                self.url_data.remove(data)
                break
        if url == self.marked_url:
            self.marked_url = None
        self._load_urls()

    def _on_rows_moved(self, parent, start, end, destination, row):
        self._sync_urls_from_list()

    def _sync_urls_from_list(self):
        self.url_data = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                self.url_data.append({"url": widget.url, "active": widget.is_active})
                if widget.is_marked:
                    self.marked_url = widget.url

    def set_marked_url(self, url: str):
        self.marked_url = url
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                widget.set_marked(widget.url == url)
        self.changed.emit()

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #2d2d2d; color: #e0e0e0; } QMenu::item:selected { background-color: #3d5a80; }")
        
        mark_action = menu.addAction(_("🔗 Mark as Working"))
        move_top = menu.addAction(_("⬆ Move to Top"))
        move_bottom = menu.addAction(_("⬇ Move to Bottom"))
        menu.addSeparator()
        delete_action = menu.addAction(_("❌ Remove"))
        
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        url = item.data(Qt.ItemDataRole.UserRole)
        
        if action == mark_action:
            self.marked_url = url
            self._load_urls()
        elif action == move_top:
            self._move_to_top(item)
        elif action == move_bottom:
            self._move_to_bottom(item)
        elif action == delete_action:
            for data in self.url_data:
                if data['url'] == url:
                    self.url_data.remove(data)
                    break
            if url == self.marked_url:
                self.marked_url = None
            self._load_urls()

    def _move_to_top(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        target = None
        for d in self.url_data:
            if d['url'] == url:
                target = d
                break
        if target:
            self.url_data.remove(target)
            self.url_data.insert(0, target)
        self._load_urls()
        self.list_widget.setCurrentRow(0)

    def _move_to_bottom(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        target = None
        for d in self.url_data:
            if d['url'] == url:
                target = d
                break
        if target:
            self.url_data.remove(target)
            self.url_data.append(target)
        self._load_urls()
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def _test_and_open_first(self):
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
        for data in self.url_data:
            if not data.get('active', True): continue
            url = data.get('url')
            try:
                req = urllib.request.Request(url, method='HEAD')
                req.add_header('User-Agent', user_agent)
                urllib.request.urlopen(req, timeout=5)
                self.marked_url = url
                self._load_urls()
                webbrowser.open(url)
                return
            except urllib.error.HTTPError as e:
                if e.code == 405:
                    try:
                        req = urllib.request.Request(url, method='GET')
                        req.add_header('User-Agent', user_agent)
                        urllib.request.urlopen(req, timeout=5)
                        self.marked_url = url
                        self._load_urls()
                        webbrowser.open(url)
                        return
                    except:
                        continue
                continue
            except:
                continue
        
        QMessageBox.warning(self, _("No Working URL"), _("No active links.\n\nAll registered URLs failed to connect."))

    def _on_url_opened(self, url):
        if self.auto_mark_chk.isChecked():
            self.marked_url = url
            self._load_urls()

    def _clear_all(self):
        self.url_data = []
        self.marked_url = None
        self.list_widget.clear()

    def get_data(self):
        self._sync_urls_from_list()
        result = {
            "urls": self.url_data,
            "auto_mark": self.auto_mark_chk.isChecked(),
            "marked_url": self.marked_url
        }
        return json.dumps(result)
