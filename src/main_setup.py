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

    # セッションログ
    sh = logging.FileHandler(session_file, encoding='utf-8')
    sh.setFormatter(formatter)
    sh.setLevel(logging.INFO)
    root.addHandler(sh)

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
        
    ch.setLevel(logging.INFO) 
    root.addHandler(ch)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    status = "ACTIVE" if HAS_RICH else "INACTIVE (rich not found)"
    logging.info(f"--- LinkMaster Production Session Started (Rich Traceback: {status}) ---")
