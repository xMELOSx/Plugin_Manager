import os
import math
from pathlib import Path

def get_package_size_fast(package_path):
    """
    フォルダ内の全ファイルを走査して合計サイズを返す。
    os.scandir を内部で使用する Path.rglob('*') を活用。
    """
    total = 0
    try:
        if not os.path.exists(package_path):
            return 0
        # Use rglob to iterate over all files and directories
        for entry in Path(package_path).rglob('*'):
            try:
                if entry.is_file():
                    # Get size from stat metadata
                    total += entry.stat().st_size
            except (PermissionError, FileNotFoundError):
                continue
    except Exception as e:
        print(f"Error scanning {package_path}: {e}")
    return total

def format_size(size_bytes):
    """人間が読みやすい形式に変換 (B, KB, MB, GB, TB)"""
    if size_bytes <= 0: return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    try:
        i = int(math.floor(math.log(size_bytes, 1024)))
        if i >= len(units): i = len(units) - 1
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {units[i]}"
    except (ValueError, OverflowError):
        return f"{size_bytes} B"
