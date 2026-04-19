import urllib.request
import urllib.parse
import json
import os
import threading
from aqt.gui_hooks import editor_did_init_buttons
from aqt import mw
from aqt.utils import tooltip

# --- HELPER UTILITIES ---

def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode())

def safe_set_field(note, field_name, value):
    if field_name in note:
        note[field_name] = value
    else:
        print(f"[Addon] Field '{field_name}' not found in note type.")

def quick_translate(text, lang="my"):
    try:
        url = (
            f"https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=auto&tl={lang}&dt=t&q={urllib.parse.quote(text)}"
        )
        return get_json(url)[0][0][0]
    except Exception as e:
        print(f"[Addon] Translation failed: {e}")
        return ""

# --- FEATURE 1: Inline Translation (Ctrl+Shift+M) ---
# Inserts "word (မြန်မာဘာသာ)" beside the selected text

def translate_selection_inline(editor):
    selected_text = editor.web.selectedText().strip()
    if not selected_text:
        tooltip("No text selected.")
        return
    def worker():
        myanmar_text = quick_translate(selected_text)
        def on_done():
            if myanmar_text:
                new_text = f"{selected_text} ({myanmar_text})"
                editor.web.eval(
                    f"document.execCommand('insertHTML', false, {json.dumps(new_text)});"
                )
            else:
                tooltip("Translation failed.")
        mw.taskman.run_on_main(on_done)
    threading.Thread(target=worker, daemon=True).start()

# --- FEATURE 2: Notification Translation (Alt+M) ---
# Shows "Translation: မြန်မာဘာသာ" in tooltip only, no insertion

def translate_selection_notify(editor):
    selected_text = editor.web.selectedText().strip()
    if not selected_text:
        tooltip("No text selected.")
        return
    def worker():
        myanmar_text = quick_translate(selected_text)
        def on_done():
            if myanmar_text:
                tooltip(f"Translation: {myanmar_text}", period=4000)
            else:
                tooltip("Translation failed.")
        mw.taskman.run_on_main(on_done)
    threading.Thread(target=worker, daemon=True).start()

# --- FEATURE 3: Full Card Generator (Ctrl+Shift+Alt+M) ---
# Fills Definition (Burmese), Synonyms, and Pronunciation fields

def run_full_generator(editor):
    note = editor.note
    if "Front" not in note:
        tooltip("Note has no 'Front' field.")
        return
    word = note["Front"].strip().lower()
    if not word:
        tooltip("'Front' field is empty.")
        return

    def worker():
        # Translation
        translated = quick_translate(word)
        if translated:
            safe_set_field(note, "Definition (Burmese)", translated)

        # Synonyms
        try:
            dict_data = get_json(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            )[0]
            synonyms = dict_data["meanings"][0].get("synonyms", [])
            safe_set_field(note, "Synonyms", ", ".join(synonyms)[:50] or "None")
        except Exception as e:
            print(f"[Addon] Synonym fetch failed: {e}")
            safe_set_field(note, "Synonyms", "None")

        # Audio
        try:
            fname = f"en_audio_{word}.mp3"
            path = os.path.join(mw.col.media.dir(), fname)
            if not os.path.exists(path):
                audio_url = (
                    f"https://translate.google.com/translate_tts"
                    f"?ie=UTF-8&q={urllib.parse.quote(word)}&tl=en&client=tw-ob"
                )
                req = urllib.request.Request(
                    audio_url, headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    with open(path, "wb") as f:
                        f.write(r.read())
            safe_set_field(note, "Pronunciation", f"[sound:{fname}]")
        except Exception as e:
            print(f"[Addon] Audio download failed: {e}")

        def on_done():
            editor.loadNote()
            tooltip(f"Card filled for: {word}")
        mw.taskman.run_on_main(on_done)

    threading.Thread(target=worker, daemon=True).start()

# --- UI INTEGRATION ---

def setup_editor_buttons(buttons, editor):
    # Ctrl+Shift+M — inline beside word
    buttons.append(
        editor.addButton(
            icon=None,
            cmd="inline_tr",
            func=lambda e=editor: translate_selection_inline(e),
            tip="Translate Selection Inline (Ctrl+Shift+M)",
            keys="Ctrl+Shift+M",
        )
    )
    # Alt+M — tooltip notification only
    buttons.append(
        editor.addButton(
            icon=None,
            cmd="notify_tr",
            func=lambda e=editor: translate_selection_notify(e),
            tip="Show Translation (Alt+M)",
            keys="Alt+M",
        )
    )
    # Ctrl+Shift+Alt+M — full card fill
    buttons.append(
        editor.addButton(
            icon=None,
            cmd="full_gen",
            func=lambda e=editor: run_full_generator(e),
            tip="Fill Whole Card (Ctrl+Shift+Alt+M)",
            keys="Ctrl+Shift+Alt+M",
        )
    )
    return buttons

editor_did_init_buttons.append(setup_editor_buttons)