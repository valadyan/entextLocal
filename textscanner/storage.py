import csv
import json
import os


STATE_FILE = "state.json"


def normalize_state(state):
    if not isinstance(state, dict):
        state = {}
    theme_name = state.get("theme", "light")
    if theme_name not in ("light", "dark"):
        theme_name = "light"
    try:
        scale = max(0.5, min(3.0, float(state.get("scale", 1.0))))
    except (TypeError, ValueError):
        scale = 1.0
    current_tab = state.get("current_tab", "all")
    if current_tab not in ("all", "learned"):
        current_tab = "all"
    geometry = state.get("geometry", "")
    text = state.get("text", "")
    source_path = state.get("source_path", "")
    return {
        "geometry": geometry if isinstance(geometry, str) and geometry else "1280x760",
        "text": text if isinstance(text, str) else "",
        "dictionary": state.get("dictionary", {}),
        "learned": state.get("learned", []),
        "current_tab": current_tab,
        "theme": theme_name,
        "scale": scale,
        "source_path": source_path if isinstance(source_path, str) else "",
        "translation_dictionary": state.get("translation_dictionary"),
    }


def make_session_state(
    geometry, text, counts, learned, current_tab, theme_name, scale, source_path,
    translation_dictionary,
):
    return {
        "geometry": geometry,
        "text": text,
        "dictionary": counts,
        "learned": sorted(learned),
        "current_tab": current_tab,
        "theme": theme_name,
        "scale": scale,
        "source_path": source_path,
        "translation_dictionary": translation_dictionary,
    }


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def save_state(state):
    temporary_path = STATE_FILE + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
    os.replace(temporary_path, STATE_FILE)


def read_word_table(path):
    counts = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        for row in csv.reader(file):
            if not row or row[0].strip().lower() == "word":
                continue
            word = row[0].strip().lower()
            if not word:
                continue
            try:
                count = max(0, int(row[1])) if len(row) > 1 and row[1].strip() else 0
            except ValueError:
                count = 0
            counts[word] = max(counts.get(word, 0), count)
    return counts


def write_word_table(path, entries, translations):
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["word", "occurrences", "translate"])
        for word, count in entries:
            writer.writerow([word, count, translations.get(word, "")])
