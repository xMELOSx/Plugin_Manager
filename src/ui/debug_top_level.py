"""
Diagnostic script to show top-level widgets count.
Run this from within the application to identify ghost windows.
"""
from PyQt6.QtWidgets import QApplication

def show_top_level_widgets():
    """Print all top-level widgets to console for debugging."""
    app = QApplication.instance()
    if not app:
        print("No QApplication instance found.")
        return
    
    widgets = app.topLevelWidgets()
    print(f"\n=== TOP LEVEL WIDGETS COUNT: {len(widgets)} ===")
    for i, w in enumerate(widgets):
        class_name = w.__class__.__name__
        obj_name = w.objectName() or "(no name)"
        is_visible = w.isVisible()
        is_hidden = w.isHidden()
        size = f"{w.width()}x{w.height()}"
        flags = str(w.windowFlags())
        parent = w.parent().__class__.__name__ if w.parent() else "None"
        
        print(f"  [{i}] {class_name} | ObjectName: {obj_name}")
        print(f"      Visible: {is_visible} | Hidden: {is_hidden} | Size: {size}")
        print(f"      Parent: {parent}")
        print(f"      Flags: {flags[:80]}...")
    print("=" * 50)
    return len(widgets)

if __name__ == "__main__":
    print("This script should be called from within the running application.")
    print("Add this import and call show_top_level_widgets() from a debug button.")
