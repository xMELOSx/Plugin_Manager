import sys
import os
import logging
from datetime import datetime

# Check if rich is available for pretty tracebacks
try:
    from rich.console import Console
    from rich.traceback import install
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

def setup_error_handling():
    """リッチなエラー表示 ＋ ログ保存の設定"""
    # ハンドラを強制リセットして、自分たちの設定が反映されるようにする
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)

    log_dir = os.path.abspath("logs/log")
    error_dir = os.path.abspath("logs/error")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(error_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_file = os.path.join(log_dir, f"session_{timestamp}.log")
    error_file = os.path.join(error_dir, f"error_{timestamp}.log")

    # 3. Richによる画面表示 (CMD用)
    if HAS_RICH:
        # install は traceback の表示を直接乗っ取るためのもの
        install(show_locals=True, width=120)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | [%(name)s] %(message)s')

    # Phase 40: Dynamic Log Level (Load from persistent settings if available)
    log_level = logging.INFO
    
    # Try to load from debug_settings.json
    try:
        import json
        # EXE-compatible path resolution
        if getattr(sys, 'frozen', False):
            # EXE mode: project root is next to executable
            project_root = os.path.dirname(sys.executable)
        else:
            # Dev mode: src/main_setup.py -> 1 level up to project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        settings_path = os.path.join(project_root, 'config', 'debug_settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                lv_text = data.get('log_level', 'INFO')
                log_level = getattr(logging, lv_text, logging.INFO)
    except Exception as e:
        # Avoid print/logging here as it might not be ready, or just use basic print
        print(f"[MainSetup] Warning: Failed to load debug_settings.json: {e}")

    # Environment variable override
    if os.environ.get('LM_DEBUG') == '1':
        log_level = logging.DEBUG
        
    logging.getLogger().setLevel(log_level)
    
    # Session Log (Overwrite each time for fresh history)
    session_handler = logging.FileHandler(os.path.join(log_dir, "session.log"), mode='w', encoding='utf-8')
    session_handler.setFormatter(formatter)
    session_handler.setLevel(log_level)
    logging.getLogger().addHandler(session_handler)

    # エラーログ
    eh = logging.FileHandler(error_file, encoding='utf-8')
    eh.setFormatter(formatter)
    eh.setLevel(logging.ERROR)
    root.addHandler(eh)

    # コンソール出力 (richがあればRichHandler)
    if HAS_RICH:
        from rich.logging import RichHandler
        # RichHandler の引数には rich_tracebacks=True を指定
        ch = RichHandler(rich_tracebacks=True, markup=True)
        ch.setFormatter(logging.Formatter('%(message)s'))
    else:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        
    ch.setLevel(log_level) 
    root.addHandler(ch)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    status = "ACTIVE" if HAS_RICH else "INACTIVE (rich not found)"
    from src.core.version import VERSION_STRING
    logging.info(f"--- {VERSION_STRING} Production Session Started (Rich Traceback: {status}) ---")
