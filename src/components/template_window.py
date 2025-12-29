""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout
from src.ui.frameless_window import FramelessWindow

class TemplateWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Template Window Verification")
        self.resize(600, 400)
        
        self._init_content()

    def _init_content(self):
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        label = QLabel("This is a Template Frameless Window.\n\n- Drag the top bar to move.\n- Use the bottom-right grip to resize.\n- Use custom buttons to Close/Minimize.")
        label.setStyleSheet("color: #ecf0f1; font-size: 14px;")
        layout.addWidget(label)
        layout.addStretch()
        
        self.set_content_widget(content_widget)
