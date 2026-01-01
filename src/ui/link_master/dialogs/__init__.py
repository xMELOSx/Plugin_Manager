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
    PreviewTableDialog,
    FullPreviewDialog,
    FolderPropertiesDialog,
    TagManagerDialog,
    TagCreationDialog,
    CropLabel,
    IconCropDialog,
    ImportTypeDialog,
    PresetPropertiesDialog,
)
from src.ui.link_master.dialogs.file_management import FileManagementDialog
from src.ui.link_master.dialogs.quick_view_manager import QuickViewManagerDialog


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
]

