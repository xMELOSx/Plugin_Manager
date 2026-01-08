
import sys
import time

print("Script Starting...", flush=True)

try:
    import ctypes
    from ctypes import wintypes
    print("Imports ctypes success", flush=True)
    
    from PyQt6.QtWidgets import QMainWindow, QApplication, QWidget, QVBoxLayout, QPushButton
    from PyQt6.QtCore import Qt, QPoint
    print("Imports PyQt6 success", flush=True)

    # Windows Constants
    GWL_STYLE = -16
    WS_MAXIMIZEBOX = 0x00010000
    WS_THICKFRAME = 0x00040000
    WS_CAPTION = 0x00C00000
    WM_NCCALCSIZE = 0x0083
    WM_NCHITTEST = 0x0084

    class ModernFramelessWindow(QMainWindow):
        def __init__(self):
            print("Window __init__ start", flush=True)
            super().__init__()
            
            # 1. PyQt Flags
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinMaxButtonsHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            self.setCentralWidget(QWidget())
            self.centralWidget().setLayout(QVBoxLayout())
            self.centralWidget().layout().addWidget(QPushButton("WinAPI Test"))
            self.centralWidget().setStyleSheet("background-color: rgba(0, 100, 0, 200);")

            # 2. Force Window Handle - REMOVED from __init__
            # print("Attempting to get winId...", flush=True)
            # self.hwnd = int(self.winId())
            # print(f"Window Handle Created: {self.hwnd}", flush=True)

            # 3. Apply Style - MOVED to showEvent
            self.styles_applied = False

        def showEvent(self, event):
            print("showEvent triggered", flush=True)
            super().showEvent(event)
            if not self.styles_applied:
                 try:
                    print("Attempting to get winId in showEvent...", flush=True)
                    self.hwnd = int(self.winId())
                    print(f"Window Handle Created: {self.hwnd}", flush=True)
                    
                    print("Attempting SetWindowLongW...", flush=True)
                    user32 = ctypes.windll.user32
                    style = user32.GetWindowLongW(self.hwnd, GWL_STYLE)
                    print(f"Original Style: {hex(style)}", flush=True)
                    
                    new_style = style | WS_THICKFRAME | WS_CAPTION | WS_MAXIMIZEBOX
                    user32.SetWindowLongW(self.hwnd, GWL_STYLE, new_style)
                    print("SetWindowLongW executed", flush=True)
                    
                    user32.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0, 0x0020 | 0x0002 | 0x0001 | 0x0004)
                    print("SetWindowPos executed", flush=True)
                    self.styles_applied = True
                 except Exception as e:
                    print(f"WinAPI Error in showEvent: {e}", flush=True)

        def nativeEvent(self, event_type, message):
            try:
                if event_type == b"windows_generic_MSG":
                    msg = wintypes.MSG.from_address(int(message))
                    
                    if msg.message == WM_NCCALCSIZE:
                        return True, 0

                    if msg.message == WM_NCHITTEST:
                        # Robust extraction for signed 16-bit values (multi-monitor)
                        x = ctypes.c_short(msg.lParam & 0xffff).value
                        y = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
                        
                        local_pos = self.mapFromGlobal(QPoint(x, y))
                        lx, ly = local_pos.x(), local_pos.y()
                        w, h = self.width(), self.height()
                        
                        margin = 8 
                        
                        # Corners
                        if lx < margin and ly < margin: return True, 13 # TOPLEFT
                        if lx > w - margin and ly < margin: return True, 14 # TOPRIGHT
                        if lx < margin and ly > h - margin: return True, 16 # BOTTOMLEFT
                        if lx > w - margin and ly > h - margin: return True, 17 # BOTTOMRIGHT
                        
                        # Edges
                        if lx < margin: return True, 10 # LEFT
                        if lx > w - margin: return True, 11 # RIGHT
                        if ly < margin: return True, 12 # TOP
                        if ly > h - margin: return True, 15 # BOTTOM
                        
                        if ly < 40:
                            return True, 2 # CAPTION

                            
            except Exception as e:
                 print(f"NativeEvent Error: {e}", flush=True)
            
            return False, 0



    print("QApplication init...", flush=True)
    app = QApplication(sys.argv)
    print("MainWindow init...", flush=True)
    window = ModernFramelessWindow()
    print("Window show...", flush=True)
    window.show()
    print("Exec...", flush=True)
    sys.exit(app.exec())

except Exception as e:
    print(f"\nCRITICAL ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
