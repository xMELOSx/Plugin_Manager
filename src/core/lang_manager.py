""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
ただし、言語ファイルは例外として直接読み書きを許可。
"""

import os
import gettext
import logging
from PyQt6.QtCore import QObject, pyqtSignal


class LangManager(QObject):
    """
    Singleton language manager for internationalization using gettext.
    Loads language files from config/locale/ directory.
    Default language: Japanese (ja)
    """
    
    _instance = None
    language_changed = pyqtSignal(str)  # Emitted when language changes
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        
        self.logger = logging.getLogger("LangManager")
        
        # Get paths (Support for PyInstaller sys._MEIPASS)
        import sys
        # Get paths (Support for PyInstaller sys._MEIPASS / External Config)
        import sys
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Phase 58: Use external directory next to EXE for config/locale
            # This allows user to modify translations without rebuilding EXE
            project_root = os.path.dirname(sys.executable)
        else:
            # Development path
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
        self.locale_dir = os.path.join(project_root, "config", "locale")
        
        # config/window.json should always be in the REAL project root (next to EXE or in development dir)
        # to ensure it's writable and persists changes.
        if hasattr(sys, '_MEIPASS'):
             # Real executable location
             real_root = os.path.dirname(sys.executable)
             self.config_path = os.path.join(real_root, "config", "window.json")
        else:
             self.config_path = os.path.join(project_root, "config", "window.json")
        
        # Ensure locale directory exists (only check if not in MEIPASS usually, or just check both)
        if not os.path.exists(self.locale_dir):
            try:
                os.makedirs(self.locale_dir, exist_ok=True)
            except Exception:
                pass # Read-only inside EXE usually
        
        # Current language
        self._current_lang_code = "ja"  # Default to Japanese
        self._translator = None
        self._help_cache = {}  # Cache for help.yaml data
        
        # Language display names
        self._lang_names = {
            "ja": "日本語",
            "en": "English"
        }
        
        # Load saved language preference from window.json
        saved_lang = self._load_saved_language()
        if saved_lang:
            if saved_lang == "system":
                self._current_lang_code = self._get_system_language()
            else:
                self._current_lang_code = saved_lang
        
        # Load language
        self._load_language(self._current_lang_code)

    def _get_system_language(self) -> str:
        """Determine system language (ja or en) via QLocale."""
        from PyQt6.QtCore import QLocale
        sys_name = QLocale.system().name()
        if sys_name.startswith("ja"):
            return "ja"
        return "en"
    
    def _load_saved_language(self) -> str:
        """Load saved language preference from window.json."""
        if not os.path.exists(self.config_path):
            return None
        try:
            import json
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get('language', None)
        except Exception as e:
            self.logger.warning(f"Failed to load language from window.json: {e}")
            return None
    
    def _save_language_preference(self):
        """Save language preference to window.json."""
        try:
            import json
            config = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            config['language'] = self._current_lang_code
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            self.logger.info(f"Saved language preference: {self._current_lang_code}")
        except Exception as e:
            self.logger.error(f"Failed to save language to window.json: {e}")
    

    def _compile_po_to_mo(self, lang_code: str) -> bool:
        """Compile .po file to .mo file if needed."""
        po_path = os.path.join(self.locale_dir, lang_code, "LC_MESSAGES", "linkmaster.po")
        mo_path = os.path.join(self.locale_dir, lang_code, "LC_MESSAGES", "linkmaster.mo")
        
        if not os.path.exists(po_path):
            return False
        
        # Check if .mo needs to be rebuilt
        if os.path.exists(mo_path):
            po_mtime = os.path.getmtime(po_path)
            mo_mtime = os.path.getmtime(mo_path)
            if mo_mtime >= po_mtime:
                return True  # Already up to date
        
        # Compile .po to .mo using msgfmt
        try:
            import subprocess
            result = subprocess.run(
                ["msgfmt", "-o", mo_path, po_path],
                capture_output=True, text=True, encoding='utf-8', errors='replace'
            )
            if result.returncode == 0:
                self.logger.info(f"Compiled {po_path} -> {mo_path}")
                return True
            else:
                self.logger.warning(f"msgfmt failed: {result.stderr}")
                # Fallback: try Python's msgfmt module
                return self._compile_with_python(po_path, mo_path)
        except FileNotFoundError:
            # msgfmt not available, use Python fallback
            return self._compile_with_python(po_path, mo_path)
    
    def _compile_with_python(self, po_path: str, mo_path: str) -> bool:
        """Compile .po to .mo using Python's built-in tools."""
        try:
            import msgfmt
            msgfmt.make(po_path, mo_path)
            self.logger.info(f"Compiled with Python msgfmt: {po_path} -> {mo_path}")
            return True
        except:
            # Last resort: parse .po file manually
            return self._parse_po_file(po_path)
    
    def _parse_po_file(self, po_path: str) -> bool:
        """Parse .po file directly as fallback when msgfmt is not available."""
        try:
            translations = {}
            with open(po_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_msgid = None
            current_msgstr = None
            in_msgid = False
            in_msgstr = False
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('msgid '):
                    # Save previous entry
                    if current_msgid is not None and current_msgstr is not None:
                        translations[current_msgid] = current_msgstr
                    
                    # Start new msgid
                    current_msgid = line[7:-1]  # Remove 'msgid "' and trailing '"'
                    current_msgstr = None
                    in_msgid = True
                    in_msgstr = False
                    
                elif line.startswith('msgstr '):
                    current_msgstr = line[8:-1]  # Remove 'msgstr "' and trailing '"'
                    in_msgid = False
                    in_msgstr = True
                    
                elif line.startswith('"') and line.endswith('"'):
                    # Continuation line
                    content = line[1:-1]  # Remove quotes
                    # Unescape \n and \" for fallback parser
                    content = content.replace('\\n', '\n').replace('\\"', '"')
                    if in_msgid:
                        current_msgid += content
                    elif in_msgstr:
                        current_msgstr += content
                        
                elif not line or line.startswith('#'):
                    # Empty line or comment - save entry if complete
                    if current_msgid is not None and current_msgstr is not None:
                        translations[current_msgid] = current_msgstr
                    current_msgid = None
                    current_msgstr = None
                    in_msgid = False
                    in_msgstr = False
            
            # Save last entry
            if current_msgid is not None and current_msgstr is not None:
                translations[current_msgid] = current_msgstr
            
            self._fallback_translations = translations
            self.logger.info(f"Parsed .po file directly: {len(translations)} strings")
            return True
        except Exception as e:
            self.logger.error(f"Failed to parse .po file: {e}")
            self._fallback_translations = {}
            return False

    
    def _load_language(self, lang_code: str) -> bool:
        """Load language for given language code."""
        # Try to compile .po to .mo
        self._compile_po_to_mo(lang_code)
        mo_path = os.path.join(self.locale_dir, lang_code, "LC_MESSAGES", "linkmaster.mo")
        if os.path.exists(mo_path):
            try:
                # Use standard gettext built-in for potentially better system compatibility
                trans = gettext.translation(
                    'linkmaster', 
                    localedir=self.locale_dir, 
                    languages=[lang_code],
                    fallback=False
                )
                self._translator = trans
                self._current_lang_code = lang_code
                self.logger.info(f"Loaded language from .mo via gettext.translation: {lang_code}")
                return True
            except Exception as e:
                self.logger.debug(f"gettext.translation failed ({lang_code}), trying manual GNUTranslations: {repr(e)}")
                # Manual fallback for custom directory structures
                try:
                    with open(mo_path, 'rb') as f:
                        self._translator = gettext.GNUTranslations(f)
                    
                    # If we got here, check if it actually works
                    try:
                        # Test if we can at least get an empty string or metadata
                        self._translator.gettext("") 
                    except UnicodeDecodeError:
                        # If gettext("") fails, it might be due to a weird header
                        # but common translations might still work. 
                        # However, it's safer to use the fallback parser.
                        raise ValueError("MO header decoding failed (UnicodeDecodeError)")
                        
                    self._current_lang_code = lang_code
                    self.logger.info(f"Loaded language from .mo (manual): {lang_code}")
                    return True
                except Exception as e2:
                    self.logger.warning(f"Failed to load .mo file ({lang_code}): {repr(e2)}")
                    self._translator = None
        
        # Fallback: try to parse .po directly
        po_path = os.path.join(self.locale_dir, lang_code, "LC_MESSAGES", "linkmaster.po")
        if os.path.exists(po_path):
            if self._parse_po_file(po_path):
                self._translator = None  # Use fallback translations
                self._current_lang_code = lang_code
                return True
        
        # No translation found
        self.logger.warning(f"No translation found for: {lang_code}")
        self._translator = None
        self._fallback_translations = {}
        return False
    
    def gettext(self, message: str) -> str:
        """Translate a message."""
        if self._translator:
            return self._translator.gettext(message)
        elif hasattr(self, '_fallback_translations') and message in self._fallback_translations:
            translated = self._fallback_translations.get(message)
            return translated if translated else message
        return message
    
    def set_language(self, lang_code: str) -> bool:
        """Switch to a different language."""
        if lang_code == self._current_lang_code:
            return True
        
        old_lang = self._current_lang_code
        if self._load_language(lang_code):
            self.logger.info(f"[LangProfile] set_language: {old_lang} -> {lang_code}")
            # Clear help cache so it reloads from YAML for the new language
            self._help_cache = {}
            self._save_language_preference()
            self.language_changed.emit(lang_code)
            return True
        return False
    
    @property
    def current_language(self) -> str:
        """Get current language code."""
        return self._current_lang_code
    
    @property
    def current_language_name(self) -> str:
        """Get current language display name."""
        return self._lang_names.get(self._current_lang_code, self._current_lang_code)
    
    def get_available_languages(self) -> list:
        """Get list of available language codes with names."""
        languages = []
        if os.path.exists(self.locale_dir):
            for dirname in os.listdir(self.locale_dir):
                lang_dir = os.path.join(self.locale_dir, dirname)
                if os.path.isdir(lang_dir):
                    po_path = os.path.join(lang_dir, "LC_MESSAGES", "linkmaster.po")
                    mo_path = os.path.join(lang_dir, "LC_MESSAGES", "linkmaster.mo")
                    if os.path.exists(po_path) or os.path.exists(mo_path):
                        name = self._lang_names.get(dirname, dirname)
                        languages.append((dirname, name))
        return languages
    
    # =========================================================================
    # Help Data Management (YAML-based)
    # =========================================================================
    
    def _get_help_yaml_path(self, lang_code: str = None) -> str:
        """Get path to help.yaml for a language."""
        lang = lang_code or self._current_lang_code
        return os.path.join(self.locale_dir, lang, "help.yaml")
    
    def _load_help_yaml(self, lang_code: str = None) -> dict:
        """Load help.yaml for the given or current language."""
        yaml_path = self._get_help_yaml_path(lang_code)
        if not os.path.exists(yaml_path):
            return {"help_notes": {}}
        
        try:
            # Try ruamel.yaml first for comment preservation
            try:
                from ruamel.yaml import YAML
                yaml = YAML()
                yaml.preserve_quotes = True
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.load(f)
                return data if data else {"help_notes": {}}
            except ImportError:
                # Fallback to PyYAML
                import yaml
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                return data if data else {"help_notes": {}}
        except Exception as e:
            self.logger.error(f"Failed to load help.yaml: {e}")
            return {"help_notes": {}}
    
    def _save_help_yaml(self, data: dict, lang_code: str = None) -> bool:
        """Save help.yaml for the given or current language."""
        yaml_path = self._get_help_yaml_path(lang_code)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
        
        try:
            # Try ruamel.yaml first for comment preservation
            try:
                from ruamel.yaml import YAML
                yaml = YAML()
                yaml.preserve_quotes = True
                yaml.default_flow_style = False
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f)
                return True
            except ImportError:
                # Fallback to PyYAML
                import yaml
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                return True
        except Exception as e:
            self.logger.error(f"Failed to save help.yaml: {e}")
            return False
    
    def _to_regular_dict(self, obj):
        """Convert ruamel.yaml CommentedMap/CommentedSeq to regular dict/list."""
        if hasattr(obj, 'items'):  # dict-like
            return {k: self._to_regular_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._to_regular_dict(item) for item in obj]
        else:
            return obj
    
    def get_help_data(self, element_id: str) -> dict:
        """Get help sticky note data for an element in current language."""
        if self._current_lang_code not in self._help_cache:
            self._help_cache[self._current_lang_code] = self._load_help_yaml()
        
        all_data = self._help_cache[self._current_lang_code]
        help_notes = all_data.get("help_notes", {})
        note = help_notes.get(element_id, {})
        # Convert ruamel.yaml types to regular dict/list
        return self._to_regular_dict(note)
    
    def set_help_data(self, element_id: str, note_data: dict) -> bool:
        """Save help sticky note data for an element in current language."""
        data = self._load_help_yaml()
        if "help_notes" not in data:
            data["help_notes"] = {}
        data["help_notes"][element_id] = note_data
        return self._save_help_yaml(data)
    
    def import_help_from_language(self, element_id: str, source_lang_code: str) -> dict:
        """Import help data for an element from another language."""
        source_data = self._load_help_yaml(source_lang_code)
        help_notes = source_data.get("help_notes", {})
        note = help_notes.get(element_id, {})
        # Convert ruamel.yaml types to regular dict/list
        return self._to_regular_dict(note)

# Singleton accessor
_lang_manager = None

def get_lang_manager() -> LangManager:
    """Get or create the singleton LangManager instance."""
    global _lang_manager
    if _lang_manager is None:
        _lang_manager = LangManager()
    return _lang_manager


# Convenience function - the standard gettext shorthand
def _(message: str) -> str:
    """Translate a message. Standard gettext shorthand."""
    return get_lang_manager().gettext(message)
