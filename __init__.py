from aqt import mw, gui_hooks
from aqt.utils import getFile, showInfo
from anki.models import NoteType
from aqt import QAction
from aqt.editor import Editor
import os
import shutil
import re
import json
import sys

card_name = "Hanzi Writer Card"

#Debug errors/printouts to log file.
def log_debug(message):
    with open(os.path.join(addon_dir, "debug.log"), "a") as f:
        f.write(f"{message}\n")

# Get the directory of this add-on
addon_dir = os.path.dirname(__file__)
dictFileName = os.path.join(addon_dir, "mandarin-dictionary.json")
mandarinDict = {}

#Add audio to note from audio button.
def add_audio_to_note(editor: Editor):
    if editor.note.model()["name"] != card_name:
        return
    # Prompt user to select an audio file
    file_path = getFile(editor.widget, "Select Audio File", None, filter="Audio Files (*.mp3 *.wav *.m4a)")
    if not file_path:
        return
    # Get the filename and copy it to the media folder
    filename = os.path.basename(file_path)
    media_dir = mw.col.media.dir()
    dest_path = os.path.join(media_dir, filename)
    if not os.path.exists(dest_path):
        with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
            dst.write(src.read())
    # Insert the audio reference into a field (e.g., "Audio")
    editor.note["Audio"] = f"[sound:{filename}]"
    editor.loadNote()

#Include button to add audio file to Audio field (if exists).
def setup_editor_buttons(buttons, editor):
    try:
        newBtn = editor.addButton(
            icon=None,
            cmd="add_audio",
            func=lambda e=editor: add_audio_to_note(e),
            tip="Add Audio File",
            label="Add Audio"
        )
        buttons.append(newBtn)
    except:
        log_debug("Error occurred when adding audio button.")

def load_template(file_name):
    #Load an HTML template from a file.
    with open(os.path.join(addon_dir, file_name), "r", encoding="utf-8") as f:
        return f.read()

def copy_media_file():
    #Copy hanzi-writer.min.js to collection.media if not already present.
    source_path = os.path.join(addon_dir, "hanzi-writer.min.js")
    media_dir = mw.col.media.dir()
    dest_path = os.path.join(media_dir, "hanzi-writer.min.js")
    if not os.path.exists(dest_path):
        shutil.copy(source_path, dest_path)

def setup_hanziwriter_card():
    model_name = card_name
    existing_models = [model["name"] for model in mw.col.models.all()]
    if model_name not in existing_models:
        model = mw.col.models.new(model_name)
        mw.col.models.addField(model, mw.col.models.newField("Hanzi"))
        mw.col.models.addField(model, mw.col.models.newField("Pinyin"))
        mw.col.models.addField(model, mw.col.models.newField("Meaning"))
        mw.col.models.addField(model, mw.col.models.newField("Audio"))
        mw.col.models.addField(model, mw.col.models.newField("Proficiency"))
        tmpl = mw.col.models.newTemplate("Card 1")
        tmpl["qfmt"] = load_template("front_template.html")
        tmpl["afmt"] = load_template("back_template.html")
        mw.col.models.addTemplate(model, tmpl)
        model["css"] = "/* Global styles */"
        mw.col.models.add(model)
        mw.col.models.save(model)
        showInfo(f"Created note type: {model_name}")
    else:
        refresh_templates()

#If plugin already installed, ensure user has latest front-end/back-end card designs.
def refresh_templates():
    #Reload templates into the existing note type.
    model_name = card_name
    model = mw.col.models.byName(model_name)
    if model:
        tmpl = model["tmpls"][0]  # First template (Card 1)
        tmpl["qfmt"] = load_template("front_template.html")
        tmpl["afmt"] = load_template("back_template.html")
        mw.col.models.save(model)
        showInfo("Templates refreshed. Review a card to see changes.")
    else:
        showInfo("Error: HanziWriter Card note type not found.")


def update_proficiency(card, ease):
    #Update Proficiency based on review ease (1=Again, 2=Hard, 3=Good, 4=Easy).
    note = card.note()
    if note.model()["name"] == card_name:
        current_prof = int(note["Proficiency"] or "0")
        if ease == 1:  # Again
            new_prof = max(0, current_prof - 1)
        elif ease == 2:  # Hard
            new_prof = current_prof
        elif ease == 3:  # Good
            new_prof = min(5, current_prof + 1)
        elif ease == 4:  # Easy
            new_prof = min(5, current_prof + 2)
        note["Proficiency"] = str(new_prof)
        note.flush()  # Save to database

#Automatically populate the pinyin field based on the hanzi field.
def update_pinyin_field(wasChanged, note, field_idx):
    global current_editor
    try:
        if note and note.model()["name"] == card_name and field_idx == 0:
            hanzi_idx = current_editor.note._fieldOrd("Hanzi")
            if field_idx == hanzi_idx:
                current_editor.note["Pinyin"] = "blah"
                hanzi = current_editor.note["Hanzi"][:]
                hanziFilteredStr = re.sub(r'[^\u4E00-\u9FFF]', '', hanzi)
                if hanziFilteredStr:
                    foundPinyin = " ".join([item[0] for item in mandarinDict[hanziFilteredStr]["pinyin"]]) if mandarinDict[hanziFilteredStr]["pinyin"] else ""
                    meaning = mandarinDict[hanziFilteredStr]["translation"]["english"]
                    current_editor.note["Pinyin"] = foundPinyin
                    current_editor.note["Meaning"] = meaning
                    current_editor.loadNote()
    except:
        log_debug("Error when updating the pinyin field.")


# Ensure that necessary files for plugin are synced so this tool works on mobile.
def on_profile_load():
    copy_media_file()
    setup_hanziwriter_card()
gui_hooks.profile_did_open.append(on_profile_load)

# Menu options
# setup_action = QAction("Setup HanziWriter Card", mw)
# setup_action.triggered.connect(lambda: [copy_media_file(), setup_hanziwriter_card()])
# mw.form.menuTools.addAction(setup_action)

# refresh_action = QAction("Refresh HanziWriter Templates", mw)
# refresh_action.triggered.connect(refresh_templates)
# mw.form.menuTools.addAction(refresh_action)

# Hooks
current_editor = None

def on_editor_init(editor):
    global current_editor
    global mandarinDict
    current_editor = editor
    try:
        with open(dictFileName, 'r', encoding="utf-8") as mandarinDictFile:
            mandarinDict = json.loads(mandarinDictFile.read())
    except:
        log_debug("Error opening mandarin dictionary.")

gui_hooks.editor_did_init.append(on_editor_init)
gui_hooks.editor_did_unfocus_field.append(lambda wasChanged, note, field_idx: update_pinyin_field(wasChanged, note, field_idx))
gui_hooks.reviewer_did_answer_card.append(lambda editor, card, ease: update_proficiency(card, ease))
gui_hooks.editor_did_init_buttons.append(setup_editor_buttons)