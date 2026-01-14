""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import json
import webbrowser
import urllib.request
import urllib.error
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QCheckBox, QMenu,
    QAbstractItemView, QMessageBox, QApplication, QHeaderView, QStyledItemDelegate
)
from src.ui.frameless_window import FramelessDialog
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon
from src.core.lang_manager import _
from src.ui.common_widgets import StyledLineEdit, ProtectedLineEdit
from src.ui.slide_button import SlideButton
from src.ui.styles import TooltipStyles


# Column indices
COL_ACTIVE = 0    # 有効
COL_PRIORITY = 1  # 優先
COL_URL = 2       # URL
COL_TEST = 3      # ✓ (Test)
COL_LINK = 4      # リンク
COL_DELETE = 5    # 削除


class ElidedItemDelegate(QStyledItemDelegate):
    """Delegate to elide text in table cells."""
    def displayText(self, value, locale):
        return value


class URLListDialog(FramelessDialog):
    """Dialog to manage multiple URLs with connectivity testing using QTableWidget."""
    changed = pyqtSignal()  # Emitted when URLs change
    
    def __init__(self, parent=None, url_list_json: str = '[]', marked_url: str = None, caller_id: str = "default"):
        super().__init__(parent)
        self.caller_id = caller_id
        self.setWindowTitle(_("Manage URLs"))
        self.resize(850, 400)  # Wider to show more URL
        self.set_default_icon()
        
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
        self._restore_geometry()
        
        # Save geometry on close
        self.finished.connect(self._save_geometry)
    
    def _restore_geometry(self):
        """Restore saved geometry for this caller_id."""
        from PyQt6.QtCore import QSettings
        settings = QSettings("LinkMaster", "URLListDialog")
        geometry = settings.value(f"geometry_{self.caller_id}")
        if geometry:
            self.restoreGeometry(geometry)
    
    def _save_geometry(self):
        """Save current geometry for this caller_id."""
        from PyQt6.QtCore import QSettings
        settings = QSettings("LinkMaster", "URLListDialog")
        settings.setValue(f"geometry_{self.caller_id}", self.saveGeometry())

    def _init_ui(self):
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        # URL Input
        input_layout = QHBoxLayout()
        input_field = ProtectedLineEdit()
        self.url_input = ProtectedLineEdit()
        self.url_input.setPlaceholderText(_("Enter URL (https://...)"))
        self.url_input.returnPressed.connect(self._add_url)
        input_layout.addWidget(self.url_input)
        
        add_btn = QPushButton("➕ " + _("Add"))
        add_btn.clicked.connect(self._add_url)
        input_layout.addWidget(add_btn)
        layout.addLayout(input_layout)

        # Table Widget - Hide built-in header, use Row 0 as custom header
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        
        # HIDE the built-in header completely
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        
        # Column widths - fixed layout
        self.table.setColumnWidth(COL_ACTIVE, 55)
        self.table.setColumnWidth(COL_PRIORITY, 55)
        self.table.setColumnWidth(COL_TEST, 45)
        self.table.setColumnWidth(COL_LINK, 45)
        self.table.setColumnWidth(COL_DELETE, 45)
        
        # URL column stretches
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_ACTIVE, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_PRIORITY, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_URL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_TEST, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_LINK, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_DELETE, QHeaderView.ResizeMode.Fixed)
        
        # Table settings
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Insert header row (Row 0) - uses same cell structure as data
        self.table.insertRow(0)
        self.table.setRowHeight(0, 32)
        header_labels = [_("Active"), _("Priority"), "URL", "✓", _("Link"), _("Delete")]
        for col, text in enumerate(header_labels):
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Not editable, not selectable
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(Qt.GlobalColor.darkGray)
            item.setForeground(Qt.GlobalColor.white)  # White for better visibility
            self.table.setItem(0, col, item)
        
        layout.addWidget(self.table)
        
        # Auto-mark setting
        auto_mark_layout = QHBoxLayout()
        auto_mark_label = QLabel(_("Auto-mark last accessed URL (🔗):"))
        auto_mark_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self.auto_mark_chk = SlideButton()
        self.auto_mark_chk.setChecked(self.auto_mark)
        auto_mark_layout.addWidget(auto_mark_label)
        auto_mark_layout.addWidget(self.auto_mark_chk)
        auto_mark_layout.addStretch()
        layout.addLayout(auto_mark_layout)

        # Toolbar
        btns = QHBoxLayout()
        
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
        self.set_content_widget(content_widget)

    def _load_urls(self):
        """Load URLs into the table. Preserves header row (Row 0)."""
        # Remove all rows except header (Row 0)
        while self.table.rowCount() > 1:
            self.table.removeRow(1)
        # Add data rows starting from Row 1
        for data in self.url_data:
            self._add_row(data)

    def _add_row(self, data: dict):
        """Add a row to the table for the given URL data."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, 36)  # Set proper row height
        
        url = data.get('url', '')
        is_active = data.get('active', True)
        is_marked = (url == self.marked_url)
        
        # Helper function to create centered button container - NO margins
        def create_btn_container(btn):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)  # No margins to prevent clipping
            layout.setSpacing(0)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(btn)
            return container
        
        # Active button - size fits within column width (55) and row height (36)
        active_btn = QPushButton("👁" if is_active else "🌑")
        active_btn.setFixedSize(50, 32)
        active_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        active_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 18px; } QPushButton:hover { background-color: #444; border-radius: 3px; }")
        active_btn.setProperty("row", row)
        active_btn.setProperty("active", is_active)
        active_btn.clicked.connect(lambda checked, r=row: self._toggle_active(r))
        self.table.setCellWidget(row, COL_ACTIVE, create_btn_container(active_btn))
        
        # Priority indicator
        priority_btn = QPushButton("🔗" if is_marked else "")
        priority_btn.setFixedSize(50, 32)
        priority_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        priority_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; font-size: 18px; color: {'#2ecc71' if is_marked else '#444'}; }} QPushButton:hover {{ background-color: #444; border-radius: 3px; }}")
        priority_btn.clicked.connect(lambda checked, r=row: self._mark_row(r))
        self.table.setCellWidget(row, COL_PRIORITY, create_btn_container(priority_btn))
        
        # URL cell (editable)
        url_item = QTableWidgetItem(url)
        url_item.setToolTip(url)
        url_item.setFlags(url_item.flags() | Qt.ItemFlag.ItemIsEditable)
        if not is_active:
            url_item.setForeground(Qt.GlobalColor.darkGray)
        self.table.setItem(row, COL_URL, url_item)
        
        # Test button - size fits within column width (45)
        test_btn = QPushButton("🔍")
        test_btn.setFixedSize(40, 32)
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.setToolTip(_("Test connectivity"))
        test_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 16px; } QPushButton:hover { background-color: #5d5d5d; border-radius: 3px; }")
        test_btn.clicked.connect(lambda checked, r=row: self._test_url(r))
        self.table.setCellWidget(row, COL_TEST, create_btn_container(test_btn))
        
        # Link button
        link_btn = QPushButton("🌐")
        link_btn.setFixedSize(40, 32)
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.setToolTip(_("Open in browser"))
        link_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 16px; } QPushButton:hover { background-color: #5d5d5d; border-radius: 3px; }")
        link_btn.clicked.connect(lambda checked, r=row: self._open_url(r))
        self.table.setCellWidget(row, COL_LINK, create_btn_container(link_btn))
        
        # Delete button
        del_btn = QPushButton("❌")
        del_btn.setFixedSize(40, 32)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 16px; } QPushButton:hover { background-color: #5d5d5d; border-radius: 3px; }")
        del_btn.clicked.connect(lambda checked, r=row: self._remove_row(r))
        self.table.setCellWidget(row, COL_DELETE, create_btn_container(del_btn))

    def _add_url(self):
        """Add URL from input field."""
        url = self.url_input.text().strip()
        if url:
            self.url_data.append({"url": url, "active": True})
            self._add_row({"url": url, "active": True})
            self.url_input.clear()

    def _toggle_active(self, row: int):
        """Toggle active state for a row."""
        btn = self.table.cellWidget(row, COL_ACTIVE)
        if btn:
            is_active = btn.property("active")
            new_active = not is_active
            btn.setProperty("active", new_active)
            btn.setText("👁" if new_active else "🌑")
            
            # Update URL item style
            url_item = self.table.item(row, COL_URL)
            if url_item:
                if new_active:
                    url_item.setForeground(Qt.GlobalColor.white)
                else:
                    url_item.setForeground(Qt.GlobalColor.darkGray)
            
            self._sync_data()

    def _mark_row(self, row: int):
        """Mark a row as preferred."""
        url_item = self.table.item(row, COL_URL)
        if url_item:
            self.marked_url = url_item.text()
            self._refresh_priority_indicators()
            self.changed.emit()

    def _refresh_priority_indicators(self):
        """Refresh all priority indicators. Skip header row (Row 0)."""
        for r in range(1, self.table.rowCount()):  # Start from Row 1
            container = self.table.cellWidget(r, COL_PRIORITY)
            if container:
                btn = container.findChild(QPushButton)
                url_item = self.table.item(r, COL_URL)
                if btn and url_item:
                    is_marked = (url_item.text() == self.marked_url)
                    btn.setText("🔗" if is_marked else "")
                    btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; font-size: 18px; color: {'#2ecc71' if is_marked else '#444'}; }} QPushButton:hover {{ background-color: #444; border-radius: 3px; }}")

    def _test_url(self, row: int):
        """Test connectivity for a URL."""
        url_item = self.table.item(row, COL_URL)
        if not url_item: return
        
        url = url_item.text()
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        try:
            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', user_agent)
            urllib.request.urlopen(req, timeout=5)
            QMessageBox.information(self, _("Success"), _("✅ Reachable"))
        except Exception as e:
            QMessageBox.warning(self, _("Failed"), _("❌ Failed: {error}").format(error=e))

    def _open_url(self, row: int):
        """Open URL in browser."""
        url_item = self.table.item(row, COL_URL)
        if url_item:
            url = url_item.text()
            webbrowser.open(url)
            if self.auto_mark_chk.isChecked():
                self.marked_url = url
                self._refresh_priority_indicators()

    def _remove_row(self, row: int):
        """Remove a row from the table."""
        url_item = self.table.item(row, COL_URL)
        if url_item and url_item.text() == self.marked_url:
            self.marked_url = None
        self.table.removeRow(row)
        self._sync_data()
        # Re-connect button signals for remaining rows
        self._reconnect_buttons()

    def _reconnect_buttons(self):
        """Reconnect button signals after row removal. Skip header row (Row 0)."""
        for r in range(1, self.table.rowCount()):  # Start from Row 1
            # Active button
            active_btn = self.table.cellWidget(r, COL_ACTIVE)
            if active_btn:
                try: active_btn.clicked.disconnect()
                except: pass
                active_btn.clicked.connect(lambda checked, row=r: self._toggle_active(row))
            
            # Priority button
            priority_btn = self.table.cellWidget(r, COL_PRIORITY)
            if priority_btn:
                try: priority_btn.clicked.disconnect()
                except: pass
                priority_btn.clicked.connect(lambda checked, row=r: self._mark_row(row))
            
            # Test button
            test_btn = self.table.cellWidget(r, COL_TEST)
            if test_btn:
                try: test_btn.clicked.disconnect()
                except: pass
                test_btn.clicked.connect(lambda checked, row=r: self._test_url(row))
            
            # Link button
            link_btn = self.table.cellWidget(r, COL_LINK)
            if link_btn:
                try: link_btn.clicked.disconnect()
                except: pass
                link_btn.clicked.connect(lambda checked, row=r: self._open_url(row))
            
            # Delete button
            del_btn = self.table.cellWidget(r, COL_DELETE)
            if del_btn:
                try: del_btn.clicked.disconnect()
                except: pass
                del_btn.clicked.connect(lambda checked, row=r: self._remove_row(row))

    def _sync_data(self):
        """Sync url_data from table state. Skip header row (Row 0)."""
        self.url_data = []
        for r in range(1, self.table.rowCount()):  # Start from Row 1
            url_item = self.table.item(r, COL_URL)
            container = self.table.cellWidget(r, COL_ACTIVE)
            if url_item and container:
                btn = container.findChild(QPushButton)
                is_active = btn.property("active") if btn else True
                self.url_data.append({"url": url_item.text(), "active": is_active})

    def _show_context_menu(self, pos):
        """Show context menu for table."""
        row = self.table.rowAt(pos.y())
        if row <= 0: return  # Skip header row
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #2d2d2d; color: #e0e0e0; } QMenu::item:selected { background-color: #3d5a80; }")
        
        mark_action = menu.addAction(_("🔗 Mark as Working"))
        move_top = menu.addAction(_("⬆ Move to Top"))
        move_bottom = menu.addAction(_("⬇ Move to Bottom"))
        menu.addSeparator()
        delete_action = menu.addAction(_("❌ Remove"))
        
        action = menu.exec(self.table.mapToGlobal(pos))
        
        if action == mark_action:
            self._mark_row(row)
        elif action == move_top:
            self._move_to_top(row)
        elif action == move_bottom:
            self._move_to_bottom(row)
        elif action == delete_action:
            self._remove_row(row)

    def _move_to_top(self, row: int):
        """Move row to top."""
        if row <= 0: return
        self._sync_data()
        item = self.url_data.pop(row)
        self.url_data.insert(0, item)
        self._load_urls()
        self.table.selectRow(0)

    def _move_to_bottom(self, row: int):
        """Move row to bottom."""
        if row >= self.table.rowCount() - 1: return
        self._sync_data()
        item = self.url_data.pop(row)
        self.url_data.append(item)
        self._load_urls()
        self.table.selectRow(self.table.rowCount() - 1)

    def _test_and_open_first(self):
        """Test all URLs and open first working one."""
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
        self._sync_data()
        for data in self.url_data:
            if not data.get('active', True): continue
            url = data.get('url')
            try:
                req = urllib.request.Request(url, method='HEAD')
                req.add_header('User-Agent', user_agent)
                urllib.request.urlopen(req, timeout=5)
                self.marked_url = url
                self._refresh_priority_indicators()
                webbrowser.open(url)
                return
            except urllib.error.HTTPError as e:
                if e.code == 405:
                    try:
                        req = urllib.request.Request(url, method='GET')
                        req.add_header('User-Agent', user_agent)
                        urllib.request.urlopen(req, timeout=5)
                        self.marked_url = url
                        self._refresh_priority_indicators()
                        webbrowser.open(url)
                        return
                    except:
                        continue
                continue
            except:
                continue
        
        QMessageBox.warning(self, _("No Working URL"), _("No active links.\n\nAll registered URLs failed to connect."))

    def _clear_all(self):
        """Clear all URLs. Preserve header row (Row 0)."""
        self.url_data = []
        self.marked_url = None
        # Remove all rows except header (Row 0)
        while self.table.rowCount() > 1:
            self.table.removeRow(1)

    def set_marked_url(self, url: str):
        """Set the marked URL from external call."""
        self.marked_url = url
        self._refresh_priority_indicators()

    def get_data(self):
        """Return URL data as JSON string."""
        self._sync_data()
        result = {
            "urls": self.url_data,
            "auto_mark": self.auto_mark_chk.isChecked(),
            "marked_url": self.marked_url
        }
        return json.dumps(result)
