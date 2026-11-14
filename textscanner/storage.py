import csv
import json
import os
import sys


DICT_FILE = "dict.json"
STATE_FILE = "state.json"


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def load_translations():
    try:
        with open(resource_path(DICT_FILE), "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("dict.json must contain a JSON object")
        return {str(key).lower(): str(value) for key, value in data.items()}, None
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {}, str(error)


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
