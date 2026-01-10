"""
Link Master Dialogs Package
Re-exports all dialog classes for backward compatibility.

This package was created by refactoring dialogs.py into smaller modules.
All original imports like `from src.ui.link_master.dialogs import X` remain valid.

Phase 20: Refactored - All classes remain in dialogs_legacy.py for stability.
Future extractions will create separate files and update imports here.
"""

# Import all dialog classes from the legacy file
from src.ui.link_master.dialogs_legacy import (
    AppRegistrationDialog,
    FolderPropertiesDialog,
    TagManagerDialog,
    TagCreationDialog,
    CropLabel,
    IconCropDialog,
    ImportTypeDialog,
    PresetPropertiesDialog,
    FrequentTagEditDialog,
    TestStyleDialog,
)
from src.ui.link_master.dialogs.file_management import FileManagementDialog
from src.ui.link_master.dialogs.quick_view_manager import QuickViewManagerDialog
from src.ui.link_master.dialogs.executables_manager import ExecutablesManagerDialog
from src.ui.link_master.dialogs.library_dialogs import LibraryDependencyDialog, LibraryRegistrationDialog
from src.ui.link_master.dialogs.url_list_dialog import URLItemWidget, URLListDialog
from src.ui.link_master.dialogs.preview_dialogs import PreviewItemWidget, PreviewTableDialog, FullPreviewDialog

__all__ = [
    'AppRegistrationDialog',
    'PreviewTableDialog',
    'FullPreviewDialog',
    'FolderPropertiesDialog',
    'TagManagerDialog',
    'TagCreationDialog',
    'CropLabel',
    'IconCropDialog',
    'ImportTypeDialog',
    'PresetPropertiesDialog',
    'FileManagementDialog',
    'QuickViewManagerDialog',
    'ExecutablesManagerDialog',
    'LibraryDependencyDialog',
    'LibraryRegistrationDialog',
    'URLItemWidget',
    'URLListDialog',
    'PreviewItemWidget',
    'FrequentTagEditDialog',
    'TestStyleDialog',
]

