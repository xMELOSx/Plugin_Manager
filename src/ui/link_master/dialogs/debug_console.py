"""
Debug Console Dialog
EXE実行時でもログ出力を確認できるデバッグコンソール。
マーカー挿入ボタンで直前の動作を追跡しやすくする。
"""
import logging
from datetime import datetime
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel, QWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor
from src.ui.frameless_window import FramelessDialog
from src.core.lang_manager import _


class DebugConsoleDialog(FramelessDialog):
    """EXE実行時のログ出力確認用デバッグコンソール"""
    
    _instance = None  # Singleton for persistent visibility
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Debug Console"))
        self.setMinimumSize(700, 400)
        self.resize(900, 500)
        
        self._marker_count = 0
        self._init_ui()
        self._setup_log_handler()
        
    def _init_ui(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # ===== Header with controls =====
        header = QHBoxLayout()
        
        # Marker Button
        self.marker_btn = QPushButton(_("📌 Insert Marker"))
        self.marker_btn.setToolTip(_("Insert a visible marker line to track actions"))
        self.marker_btn.clicked.connect(self._insert_marker)
        self.marker_btn.setStyleSheet("""
            QPushButton { 
                background-color: #e74c3c; 
                color: white; 
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        header.addWidget(self.marker_btn)
        
        header.addStretch()
        
        # Clear Button
        self.clear_btn = QPushButton(_("Clear"))
        self.clear_btn.clicked.connect(self._clear_log)
        header.addWidget(self.clear_btn)
        
        # Auto-scroll toggle
        self.scroll_btn = QPushButton(_("Auto-scroll: ON"))
        self.scroll_btn.setCheckable(True)
        self.scroll_btn.setChecked(True)
        self.scroll_btn.toggled.connect(self._toggle_autoscroll)
        header.addWidget(self.scroll_btn)
        
        layout.addLayout(header)
        
        # ===== Log Output Area =====
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        self.log_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.log_text)
        
        # ===== Status Bar =====
        self.status_label = QLabel(_("Ready"))
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        self.set_content_widget(content)
        
        # Auto-scroll flag
        self._autoscroll = True
        
    def _setup_log_handler(self):
        """Pythonロギングシステムからログを受信するハンドラーを設定"""
        self.log_handler = DebugConsoleHandler(self)
        self.log_handler.setLevel(logging.DEBUG)
        
        # Format: [TIME] LEVEL - MESSAGE
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        self.log_handler.setFormatter(formatter)
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        
        # Also capture uncaught exceptions to the log
        self._original_excepthook = None
        
    def append_log(self, message: str, level: str = "INFO"):
        """ログメッセージを追加"""
        # Color coding by level
        color_map = {
            "DEBUG": "#888888",
            "INFO": "#d4d4d4",
            "WARNING": "#e6a700",
            "ERROR": "#e74c3c",
            "CRITICAL": "#ff0000",
            "MARKER": "#ff69b4"  # Hot pink for markers
        }
        color = color_map.get(level, "#d4d4d4")
        
        # Add colored HTML
        self.log_text.appendPlainText(message)
        
        if self._autoscroll:
            self.log_text.moveCursor(QTextCursor.MoveOperation.End)
            
        # Update status
        self.status_label.setText(f"{_('Last')}: {datetime.now().strftime('%H:%M:%S')}")
        
    def _insert_marker(self):
        """可視マーカーを挿入して動作追跡を支援（ロギングとUIの両方に出力）"""
        self._marker_count += 1
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        marker_line = f"{'='*60}\n=== MARKER #{self._marker_count} === {timestamp} ===\n{'='*60}"
        
        # Output to Python logging (rich console) as well
        logging.info(f"\n{marker_line}")
        
        if self._autoscroll:
            self.log_text.moveCursor(QTextCursor.MoveOperation.End)
            
        self.status_label.setText(f"Marker #{self._marker_count} inserted")
        
    def _clear_log(self):
        """ログをクリア"""
        self.log_text.clear()
        self._marker_count = 0
        self.status_label.setText(_("Cleared"))
        
    def _toggle_autoscroll(self, checked: bool):
        """自動スクロールの切り替え"""
        self._autoscroll = checked
        self.scroll_btn.setText(_("Auto-scroll: ON") if checked else _("Auto-scroll: OFF"))
        
    def closeEvent(self, event):
        """閉じる時にハンドラーを削除"""
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_handler)
        super().closeEvent(event)
        
    @classmethod
    def show_console(cls, parent=None):
        """シングルトンインスタンスを表示（二重インスタンス防止）"""
        # Check if instance exists and is not destroyed
        try:
            if cls._instance is not None:
                # Try to access the instance to ensure it's not deleted
                _ = cls._instance.isVisible()
        except RuntimeError:
            # Instance was deleted (C++ object destroyed)
            cls._instance = None
        
        if cls._instance is None:
            cls._instance = DebugConsoleDialog(parent)
        
        cls._instance.show()
        cls._instance.raise_()
        cls._instance.activateWindow()
        return cls._instance


class DebugConsoleHandler(logging.Handler):
    """DebugConsoleDialogにログを送信するカスタムハンドラー"""
    
    def __init__(self, console: DebugConsoleDialog):
        super().__init__()
        self.console = console
        
    def emit(self, record):
        try:
            msg = self.format(record)
            level = record.levelname
            # Use QTimer to safely update UI from any thread
            QTimer.singleShot(0, lambda: self.console.append_log(msg, level))
        except Exception:
            self.handleError(record)
