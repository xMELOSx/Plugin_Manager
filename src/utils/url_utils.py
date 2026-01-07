""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import json
import urllib.request
import urllib.error
import webbrowser
from PyQt6.QtWidgets import QMessageBox
from src.core.lang_manager import _


# Return values for open_first_working_url
URL_OPENED = "opened"          # Successfully opened a URL
URL_FORCE_OPENED = "force"     # User chose to force open
URL_OPEN_MANAGER = "manage"    # User chose to open URL manager
URL_CANCELLED = "cancelled"    # User cancelled or no action
URL_NO_URLS = "no_urls"        # No URLs exist at all


def open_first_working_url(url_list_json: str, parent=None, db=None, rel_path=None, show_fallback_dialog=True):
    """
    URL Probing Utility: Check all URLs and open the prioritized one (marked > first active).
    
    Args:
        url_list_json: JSON string of URL data (list or dict format)
        parent: Parent widget for QMessageBox dialogs
        db: Database object for auto-mark persistence (optional)
        rel_path: Relative path for DB update (optional)
        show_fallback_dialog: If True, show 3-option dialog when URLs fail
    
    Returns:
        str: One of URL_OPENED, URL_FORCE_OPENED, URL_OPEN_MANAGER, URL_CANCELLED, URL_NO_URLS
    """
    try:
        data = json.loads(url_list_json) if isinstance(url_list_json, str) else url_list_json
    except:
        data = []
    
    # Parse URL structure
    urls = []
    auto_mark = True
    marked_url = None
    
    if isinstance(data, dict):
        urls = data.get('urls', [])
        auto_mark = data.get('auto_mark', True)
        marked_url = data.get('marked_url')
    elif isinstance(data, list):
        for u in data:
            if isinstance(u, str):
                urls.append({"url": u, "active": True})
            else:
                urls.append(u)
    
    # Filter active URLs
    active_urls = [u for u in urls if u.get('active', True)]
    if not active_urls:
        # No active URLs - show dialog or return
        if not urls:
            # No URLs at all
            return URL_NO_URLS
        
        # All URLs inactive
        if show_fallback_dialog and parent:
            return _show_fallback_dialog(parent, _("No active URLs (all disabled)."), None)
        return URL_CANCELLED
    
    # Build priority order: Marked first, then all others
    target_urls = []
    if marked_url:
        for u in active_urls:
            if u['url'] == marked_url:
                target_urls.append(u['url'])
                break
    
    for u in active_urls:
        if u['url'] not in target_urls:
            target_urls.append(u['url'])
    
    # Probe URLs
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    for url in target_urls:
        try:
            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', user_agent)
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as e:
            if e.code == 405:
                try:
                    req = urllib.request.Request(url, method='GET')
                    req.add_header('User-Agent', user_agent)
                    urllib.request.urlopen(req, timeout=5)
                except:
                    continue
            else:
                continue
        except:
            continue
        
        # Found a working URL!
        webbrowser.open(url)
        
        # Auto-mark if enabled and DB available
        if auto_mark and url != marked_url and db and rel_path:
            try:
                updated_data = data if isinstance(data, dict) else {'urls': urls, 'auto_mark': True}
                updated_data['marked_url'] = url
                new_json = json.dumps(updated_data)
                db.update_folder_display_config(rel_path, url_list=new_json)
            except:
                pass
        
        return URL_OPENED
    
    # All tests failed
    if show_fallback_dialog and parent:
        first_url = active_urls[0]['url'] if active_urls else None
        result = _show_fallback_dialog(parent, _("Could not connect to registered URLs."), first_url)
        
        if result == URL_FORCE_OPENED and first_url:
            webbrowser.open(first_url)
        
        return result
    
    return URL_CANCELLED


def _show_fallback_dialog(parent, message: str, first_url: str = None):
    """Show 3-option dialog: Force Open / Open Manager / Cancel"""
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(_("URL Connection"))
    msg_box.setText(message)
    msg_box.setInformativeText(_("What would you like to do?"))
    
    # Add custom buttons
    if first_url:
        force_btn = msg_box.addButton("🌐 " + _("Force Open"), QMessageBox.ButtonRole.AcceptRole)
    else:
        force_btn = None
    manage_btn = msg_box.addButton("⚙ " + _("Open URL Manager"), QMessageBox.ButtonRole.ActionRole)
    cancel_btn = msg_box.addButton(_("Cancel"), QMessageBox.ButtonRole.RejectRole)
    
    msg_box.setDefaultButton(manage_btn)
    
    from src.ui.styles import DialogStyles
    msg_box.setStyleSheet(DialogStyles.ENHANCED_MSG_BOX)
    
    msg_box.exec()
    
    clicked = msg_box.clickedButton()
    if clicked == force_btn:
        return URL_FORCE_OPENED
    elif clicked == manage_btn:
        return URL_OPEN_MANAGER
    else:
        return URL_CANCELLED
