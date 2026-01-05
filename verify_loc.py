import gettext
import os

def test_translations():
    localedir = 'config/locale'
    try:
        t = gettext.translation('linkmaster', localedir=localedir, languages=['ja'])
        t.install()
        
        test_strings = [
            "Show in Folder Area",
            "Show in Item Area",
            "Final Confirmation",
            "This will permanently delete the database for '{name}'.\nAre you absolutely sure?"
        ]
        
        print("--- Translation Verification ---")
        for s in test_strings:
            translated = _(s)
            print(f"ID: {s}")
            print(f"TR: {translated}")
            if translated == s:
                print("!! ERROR: Translation not found or matches ID !!")
            print("-" * 30)
            
    except Exception as e:
        print(f"Failed to load translations: {e}")

if __name__ == "__main__":
    test_translations()
