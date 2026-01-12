# NOTE: setup_error_handling must be called BEFORE other src imports
# to ensure rich traceback handling is correctly initialized globally.
from src.main_setup import setup_error_handling, HAS_RICH 
setup_error_handling()

import sys
import os
import logging
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from src.apps.link_master_window import LinkMasterWindow
# setup_error_handling is now imported from main_setup and called at the top of this file.

def set_app_user_model_id():
    """Ensure the process name and taskbar icon are correctly identified as Dionys Control."""
    if sys.platform == 'win32':
        import ctypes
        from src.core.version import VERSION
        # APPID format: CompanyName.ProductName.SubProduct.VersionInformation
        myappid = f'xMELOSx.DionysControl.LinkMaster.{VERSION}'
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            logging.error(f"Failed to set AppUserModelID: {e}")

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        # For development, assume project root is 2 levels up from src/main.py
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def main():
    set_app_user_model_id()
    try:
        app = QApplication(sys.argv)
        # Set application name for the OS to see
        from src.core.version import APP_NAME
        app.setApplicationName(APP_NAME)
        
        from src.ui.styles import TooltipStyles
        app.setStyleSheet(TooltipStyles.DARK)
        
        # アイコンの読み込み (EXE対応)
        icon_path = resource_path(os.path.join("src", "resource", "icon", "icon.ico"))
        if not os.path.exists(icon_path):
            icon_path = resource_path(os.path.join("src", "resource", "icon", "icon.jpg"))
            
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        window = LinkMasterWindow()
        window.show()
        from src.core.version import VERSION_STRING
        logging.info(f"Launched {VERSION_STRING} Window.")
        
        sys.exit(app.exec())
    except Exception:
        logging.error("Fatal error in main loop", exc_info=True)
        if HAS_RICH:
            # logging.error(exc_info=True) が RichHandler によって既に処理されているはずだが、
            # 万が一のために、より詳細な例外表示をコンソールに行う
            from rich.console import Console
            Console().print_exception(show_locals=True)
        else:
            import traceback
            traceback.print_exc()
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
