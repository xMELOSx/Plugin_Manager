""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QApplication, QMenu
)
from src.ui.frameless_window import FramelessDialog
from PyQt6.QtCore import Qt, pyqtSignal
from src.core.lang_manager import _
from src.ui.common_widgets import ProtectedLineEdit, StyledButton, StyledSpinBox
from src.ui.slide_button import SlideButton

class PasswordListDialog(FramelessDialog):
    """Dialog to manage application-specific passwords."""
    
    def __init__(self, parent=None, password_list_json: str = '[]'):
        super().__init__(parent)
        self.setWindowTitle(_("Manage Passwords"))
        self.resize(400, 500)
        self.set_default_icon()
        
        try:
            self.passwords = json.loads(password_list_json)
            if not isinstance(self.passwords, list):
                self.passwords = []
        except:
            self.passwords = []
            
        self.show_passwords = False
        self._init_ui()
        self._refresh_list()
        
    def _init_ui(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header / Toggle
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(_("Stored Passwords:")))
        top_layout.addStretch()
        
        self.toggle_btn = QPushButton("👁")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setToolTip(_("Show/Hide Passwords"))
        self.toggle_btn.toggled.connect(self._toggle_visibility)
        top_layout.addWidget(self.toggle_btn)
        layout.addLayout(top_layout)
        
        # List
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #555;
                color: #eee;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #3d5a80;
            }
        """)
        layout.addWidget(self.list_widget)
        
        # Input Area
        input_layout = QHBoxLayout()
        self.input_field = ProtectedLineEdit()
        self.input_field.setPlaceholderText(_("Enter Password"))
        self.input_field.setEchoMode(ProtectedLineEdit.EchoMode.Password)
        self.input_field.returnPressed.connect(self._add_password)
        
        add_btn = StyledButton("➕ " + _("Add"), style_type="Blue")
        add_btn.clicked.connect(self._add_password)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(add_btn)
        layout.addLayout(input_layout)
        
        # Toolbar
        btn_layout = QHBoxLayout()
        
        del_btn = StyledButton(_("Remove"), style_type="Gray")
        del_btn.clicked.connect(self._remove_selected)
        
        up_btn = StyledButton("⬆", style_type="Gray")
        up_btn.setFixedWidth(40)
        up_btn.clicked.connect(self._move_up)
        
        down_btn = StyledButton("⬇", style_type="Gray")
        down_btn.setFixedWidth(40)
        down_btn.clicked.connect(self._move_down)
        
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(up_btn)
        btn_layout.addWidget(down_btn)
        layout.addLayout(btn_layout)
        
        layout.addSpacing(10)
        
        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        ok_btn = StyledButton(_("OK"), style_type="Blue")
        ok_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(ok_btn)
        
        # Cancel not strictly needed if we treat this as a direct editor, 
        # but standard dialog behavior expects it.
        cancel_btn = StyledButton(_("Cancel"), style_type="Gray")
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(cancel_btn)
        
        layout.addLayout(bottom_layout)
        self.set_content_widget(content)
        
    def _toggle_visibility(self, checked):
        self.show_passwords = checked
        self.input_field.setEchoMode(ProtectedLineEdit.EchoMode.Normal if checked else ProtectedLineEdit.EchoMode.Password)
        self.toggle_btn.setText("🔒" if checked else "👁")
        self._refresh_list()
        
    def _refresh_list(self):
        curr_row = self.list_widget.currentRow()
        self.list_widget.clear()
        
        for pwd in self.passwords:
            display_text = pwd if self.show_passwords else "●" * 8
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, pwd)
            self.list_widget.addItem(item)
            
        if 0 <= curr_row < self.list_widget.count():
            self.list_widget.setCurrentRow(curr_row)
            
    def _add_password(self):
        text = self.input_field.text().strip()
        if not text: return
        
        if text in self.passwords:
            # Move to top if exists? Or just ignore? User request said "last hit moves to top", manual entry implies priority.
            # Let's just add it. If user wants to reorder, they can.
            # Avoid dupes.
            self.passwords.remove(text)
            
        self.passwords.insert(0, text) # Add to top
        self.input_field.clear()
        self._refresh_list()
        self.list_widget.setCurrentRow(0)
        
    def _remove_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.passwords.pop(row)
            self._refresh_list()
            
    def _move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            self.passwords[row], self.passwords[row-1] = self.passwords[row-1], self.passwords[row]
            self._refresh_list()
            self.list_widget.setCurrentRow(row-1)
            
    def _move_down(self):
        row = self.list_widget.currentRow()
        if row < len(self.passwords) - 1 and row >= 0:
            self.passwords[row], self.passwords[row+1] = self.passwords[row+1], self.passwords[row]
            self._refresh_list()
            self.list_widget.setCurrentRow(row+1)
            
    def get_data(self):
        """Return JSON string of password list."""
        return json.dumps(self.passwords)
