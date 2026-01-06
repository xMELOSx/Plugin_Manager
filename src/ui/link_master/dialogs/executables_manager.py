""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QWidget, QFileDialog, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from src.ui.common_widgets import StyledLineEdit
from src.core.lang_manager import _
import os


class ExecutablesManagerDialog(QDialog):
    """Dialog to manage executable links for an app with styling and reordering."""
    def __init__(self, parent=None, executables: list = None):
        super().__init__(parent)
        self.setWindowTitle(_("Manage Executables"))
        self.setMinimumSize(600, 500)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #e0e0e0; }
            QTableWidget { background-color: #2d2d2d; color: #e0e0e0; gridline-color: #3d3d3d; }
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; padding: 5px 10px; border-radius: 4px; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        
        self.executables = list(executables) if executables else []
        self._init_ui()
        self._load_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Form for adding/editing
        form_group = QGroupBox(_("Add / Edit Executable"))
        form_group.setStyleSheet("QGroupBox { color: #aaa; font-weight: bold; }")
        form_layout = QFormLayout(form_group)
        
        self.name_edit = StyledLineEdit()
        self.name_edit.setPlaceholderText(_("Display Name (e.g. 'Launch Game')"))
        form_layout.addRow(_("Name:"), self.name_edit)
        
        path_layout = QHBoxLayout()
        self.path_edit = StyledLineEdit()
        self.path_edit.setPlaceholderText(_("Executable path (.exe)"))
        path_layout.addWidget(self.path_edit)
        browse_btn = QPushButton(_("Browse"))
        browse_btn.clicked.connect(self._browse_exe)
        path_layout.addWidget(browse_btn)
        form_layout.addRow(_("Path:"), path_layout)
        
        self.args_edit = StyledLineEdit()
        self.args_edit.setPlaceholderText(_("Command line arguments (optional)"))
        form_layout.addRow(_("Args:"), self.args_edit)
        
        # Color selections
        color_layout = QHBoxLayout()
        self.btn_color = "#3498db"
        self.txt_color = "#ffffff"
        
        self.btn_color_preview = QPushButton(_("■ BG Color"))
        self.btn_color_preview.setStyleSheet(f"background-color: {self.btn_color}; color: white; border: 1px solid #555;")
        self.btn_color_preview.clicked.connect(self._pick_btn_color)
        color_layout.addWidget(self.btn_color_preview)
        
        self.txt_color_preview = QPushButton(_("T Text Color"))
        self.txt_color_preview.setStyleSheet(f"background-color: #333; color: {self.txt_color}; border: 1px solid #555;")
        self.txt_color_preview.clicked.connect(self._pick_txt_color)
        color_layout.addWidget(self.txt_color_preview)
        
        form_layout.addRow(_("Style:"), color_layout)
        
        self.add_btn = QPushButton(_("➕ Register/Update"))
        self.add_btn.clicked.connect(self._add_or_update_exe)
        self.add_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        form_layout.addRow("", self.add_btn)
        
        layout.addWidget(form_group)
        
        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([_("Name"), _("Path"), _("Args"), _("Actions")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        
        # Reorder and Actions
        bottom_layout = QHBoxLayout()
        
        up_btn = QPushButton(_("▲ Up"))
        up_btn.clicked.connect(lambda: self._move_exe(-1))
        bottom_layout.addWidget(up_btn)
        
        down_btn = QPushButton(_("▼ Down"))
        down_btn.clicked.connect(lambda: self._move_exe(1))
        bottom_layout.addWidget(down_btn)
        
        bottom_layout.addStretch()
        
        save_btn = QPushButton(_("OK (Save Changes)"))
        save_btn.clicked.connect(self.accept)
        save_btn.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; width: 150px;")
        bottom_layout.addWidget(save_btn)
        
        layout.addLayout(bottom_layout)

    def _pick_btn_color(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(QColor(self.btn_color), self, _("Select Button Color"))
        if color.isValid():
            self.btn_color = color.name()
            self.btn_color_preview.setStyleSheet(f"background-color: {self.btn_color}; color: white; border: 1px solid #555;")

    def _pick_txt_color(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(QColor(self.txt_color), self, _("Select Text Color"))
        if color.isValid():
            self.txt_color = color.name()
            self.txt_color_preview.setStyleSheet(f"background-color: #333; color: {self.txt_color}; border: 1px solid #555;")

    def _browse_exe(self):
        path, _filter = QFileDialog.getOpenFileName(self, _("Select Executable"), "", _("Executables (*.exe);;All Files (*)"))
        if path:
            self.path_edit.setText(path)

    def _add_or_update_exe(self):
        name = self.name_edit.text().strip()
        path = self.path_edit.text().strip()
        args = self.args_edit.text().strip()
        
        if not name or not path:
            QMessageBox.warning(self, _("Error"), _("Name and Path are required."))
            return
        
        new_exe = {
            "name": name, 
            "path": path, 
            "args": args,
            "btn_color": self.btn_color,
            "text_color": self.txt_color
        }
        
        # If we have a selected row, update it, otherwise add new
        row = self.table.currentRow()
        if row >= 0:
            self.executables[row] = new_exe
            self.table.setCurrentCell(-1, -1)
        else:
            self.executables.append(new_exe)
        
        self._load_table()
        self._clear_form()

    def _clear_form(self):
        self.name_edit.clear()
        self.path_edit.clear()
        self.args_edit.clear()
        self.btn_color = "#3498db"
        self.txt_color = "#ffffff"
        self.btn_color_preview.setStyleSheet(f"background-color: {self.btn_color}; color: white; border: 1px solid #555;")
        self.txt_color_preview.setStyleSheet(f"background-color: #333; color: {self.txt_color}; border: 1px solid #555;")

    def _load_table(self):
        self.table.setRowCount(0)
        for i, exe in enumerate(self.executables):
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            name_item = QTableWidgetItem(exe['name'])
            # Apply custom colors to name preview in table
            name_item.setBackground(QColor(exe.get('btn_color', '#3498db')))
            name_item.setForeground(QColor(exe.get('text_color', '#ffffff')))
            
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(os.path.basename(exe['path'])))
            self.table.setItem(row, 2, QTableWidgetItem(exe.get('args', '')))
            
            # Action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(4)
            
            edit_btn = QPushButton("✏")
            edit_btn.setFixedSize(24, 24)
            edit_btn.clicked.connect(lambda ch, r=row: self._edit_row(r))
            actions_layout.addWidget(edit_btn)
            
            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(24, 24)
            del_btn.setStyleSheet("background-color: #c0392b;")
            del_btn.clicked.connect(lambda ch, r=row: self._delete_row(r))
            actions_layout.addWidget(del_btn)
            
            self.table.setCellWidget(row, 3, actions_widget)

    def _edit_row(self, row):
        if 0 <= row < len(self.executables):
            exe = self.executables[row]
            self.name_edit.setText(exe['name'])
            self.path_edit.setText(exe['path'])
            self.args_edit.setText(exe.get('args', ''))
            self.btn_color = exe.get('btn_color', '#3498db')
            self.txt_color = exe.get('text_color', '#ffffff')
            self.btn_color_preview.setStyleSheet(f"background-color: {self.btn_color}; color: white; border: 1px solid #555;")
            self.txt_color_preview.setStyleSheet(f"background-color: #333; color: {self.txt_color}; border: 1px solid #555;")
            self.table.selectRow(row)

    def _delete_row(self, row):
        if 0 <= row < len(self.executables):
            self.executables.pop(row)
            self._load_table()

    def _move_exe(self, delta):
        row = self.table.currentRow()
        if row < 0: return
        
        new_row = row + delta
        if 0 <= new_row < len(self.executables):
            self.executables[row], self.executables[new_row] = self.executables[new_row], self.executables[row]
            self._load_table()
            self.table.selectRow(new_row)

    def get_executables(self):
        return self.executables
