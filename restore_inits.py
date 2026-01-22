
import os

src_root = r'c:\Users\xMELOSx\.gemini\antigravity\scratch\Projects\Plugin_Manager\src'

def ensure_init(path):
    init_path = os.path.join(path, '__init__.py')
    if not os.path.exists(init_path):
        with open(init_path, 'w', encoding='utf-8') as f:
            f.write('')
        print(f"Created {init_path}")

for root, dirs, files in os.walk(src_root):
    # Only if it has python files or subdirs with python files
    has_py = any(f.endswith('.py') for f in files)
    if has_py:
        ensure_init(root)
