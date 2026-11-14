import csv
import gzip
import json
import os
import re
import sys
import zlib


DICTS_DIR = "dicts"
DEFAULT_DICTIONARY = "eng-rus"
DICT_BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
STATE_FILE = "state.json"
LANGUAGE_NAMES = {
    "cat": "Catalan", "ces": "Czech", "deu": "German", "ell": "Greek",
    "eng": "English", "fra": "French", "ita": "Italian", "jpn": "Japanese",
    "nld": "Dutch", "pol": "Polish", "rus": "Russian", "spa": "Spanish",
    "swe": "Swedish", "zho": "Chinese",
}


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def available_dictionaries():
    dictionaries = []
    try:
        entries = os.scandir(resource_path(DICTS_DIR))
    except OSError:
        return []
    with entries:
        for entry in entries:
            if not entry.is_dir():
                continue
            name = entry.name
            index_path = os.path.join(entry.path, name + ".index")
            data_path = os.path.join(entry.path, name + ".dict.dz")
            if not os.path.isfile(index_path) or not os.path.isfile(data_path):
                continue
            source, separator, target = name.partition("-")
            if separator and source in LANGUAGE_NAMES and target in LANGUAGE_NAMES:
                label = f"{LANGUAGE_NAMES[source]} → {LANGUAGE_NAMES[target]}"
            else:
                label = name
            dictionaries.append((name, label))
    return sorted(
        dictionaries, key=lambda item: (item[0] != DEFAULT_DICTIONARY, item[1])
    )


def _decode_dict_number(value):
    number = 0
    try:
        if not value:
            raise ValueError
        for character in value:
            number = number * 64 + DICT_BASE64_ALPHABET.index(character)
    except ValueError:
        raise ValueError(f"invalid base64 number {value!r}") from None
    return number


_IRREGULAR_LEMMAS = {
    "ate": "eat", "began": "begin", "begun": "begin", "bought": "buy",
    "brought": "bring", "came": "come", "children": "child", "did": "do",
    "done": "do", "drank": "drink", "driven": "drive", "drove": "drive",
    "eaten": "eat", "feet": "foot", "felt": "feel", "flew": "fly",
    "flown": "fly", "found": "find", "gave": "give", "given": "give",
    "gone": "go", "got": "get", "gotten": "get", "grew": "grow",
    "grown": "grow", "had": "have", "held": "hold", "knew": "know",
    "known": "know", "left": "leave", "made": "make", "men": "man",
    "mice": "mouse", "ran": "run", "said": "say", "saw": "see",
    "seen": "see", "spoken": "speak", "spoke": "speak", "taken": "take",
    "teeth": "tooth", "thought": "think", "told": "tell", "took": "take",
    "was": "be", "went": "go", "were": "be", "women": "woman",
    "wrote": "write", "written": "write",
}


def lemma_candidates(word):
    candidates = []
    if word in _IRREGULAR_LEMMAS:
        candidates.append(_IRREGULAR_LEMMAS[word])
    if word.endswith("ies") and len(word) > 3:
        candidates.append(word[:-3] + "y")
    if word.endswith("ied") and len(word) > 3:
        candidates.append(word[:-3] + "y")
    for suffix in ("ing", "ed", "est", "er"):
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            stem = word[:-len(suffix)]
            candidates.append(stem + "e")
            candidates.append(stem)
            if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] in "bcdfgklmnprstz":
                candidates.append(stem[:-1])
            break
    if word.endswith("ier") and len(word) > 3:
        candidates.append(word[:-3] + "y")
    if word.endswith("iest") and len(word) > 4:
        candidates.append(word[:-4] + "y")
    if word.endswith("es") and len(word) > 2:
        candidates.append(word[:-2])
        candidates.append(word[:-1])
    elif word.endswith("s") and not word.endswith(("ss", "us", "is")) and len(word) > 1:
        candidates.append(word[:-1])
    return dict.fromkeys(candidates)


def lookup_translation(word, translations, use_english_fallback=True):
    word = word.lower()
    if word in translations:
        return word, translations[word]
    if use_english_fallback:
        for candidate in lemma_candidates(word):
            if candidate in translations:
                return candidate, translations[candidate]
    return None, None


def short_translation(definition):
    for line in definition.splitlines():
        line = re.sub(r"^\s*\d+\.\s*", "", line)
        line = re.split(r"[,;]", line, maxsplit=1)[0].strip()
        line = re.sub(r"^(?:\([^)]*\)\s*)+", "", line)
        match = re.match(r"[\u0400-\u04ff][\u0400-\u04ff\u0301'’-]*", line)
        if match:
            return match.group().replace("\u0301", "").strip("-'’")
    return ""


def _load_dict_translations(index_path, data_path):
    with gzip.open(data_path, "rb") as file:
        data = file.read()
    translations = {}
    with open(index_path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            try:
                word, encoded_offset, encoded_size = line.rstrip("\r\n").split("\t")
                offset = _decode_dict_number(encoded_offset)
                size = _decode_dict_number(encoded_size)
            except ValueError as error:
                raise ValueError(f"{index_path}: line {line_number}: {error}") from None
            end = offset + size
            if end > len(data):
                raise ValueError(
                    f"{index_path}: line {line_number}: entry exceeds dictionary data"
                )
            definition = data[offset:end].decode("utf-8").strip()
            word = word.lower()
            if word and definition:
                previous = translations.get(word)
                translations[word] = f"{previous}\n\n{definition}" if previous else definition
    return translations


def load_translations(dictionary_name=DEFAULT_DICTIONARY):
    if dictionary_name not in {name for name, label in available_dictionaries()}:
        return {}, f'Unknown dictionary "{dictionary_name}".'
    base_path = os.path.join(DICTS_DIR, dictionary_name, dictionary_name)
    try:
        return _load_dict_translations(
            resource_path(base_path + ".index"), resource_path(base_path + ".dict.dz")
        ), None
    except (OSError, ValueError, EOFError, zlib.error) as error:
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
