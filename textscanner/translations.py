import gzip
import os
import re
import sys
import zlib


DICTS_DIR = "dicts"
DEFAULT_DICTIONARY = "eng-rus"
DICT_BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
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


SIMPLEMMA_LANGUAGES = {
    "cat": "ca", "ces": "cs", "deu": "de", "ell": "el", "fra": "fr",
    "ita": "it", "nld": "nl", "pol": "pl", "spa": "es", "swe": "sv",
}


def lemma_candidates(word, source_language="eng"):
    if source_language == "eng":
        from lemminflect import getLemma

        candidates = []
        for upos in ("NOUN", "VERB", "ADJ", "ADV"):
            candidates.extend(getLemma(word, upos=upos))
        return dict.fromkeys(candidates)
    language = SIMPLEMMA_LANGUAGES.get(source_language)
    if not language:
        return ()
    from simplemma import lemmatize

    return (lemmatize(word, lang=language),)


def lookup_translation(word, translations, source_language="eng"):
    word = word.lower()
    if word in translations:
        return word, translations[word]
    for candidate in lemma_candidates(word, source_language):
        candidate = candidate.lower()
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


class TranslationManager:
    def __init__(self, dictionary_name=DEFAULT_DICTIONARY):
        self.dictionaries = available_dictionaries()
        self.dictionary_labels = {label: name for name, label in self.dictionaries}
        dictionary_names = {name for name, label in self.dictionaries}
        if not isinstance(dictionary_name, str) or dictionary_name not in dictionary_names:
            dictionary_name = (
                DEFAULT_DICTIONARY if DEFAULT_DICTIONARY in dictionary_names
                else self.dictionaries[0][0] if self.dictionaries else ""
            )
        self.dictionary_name = dictionary_name
        self.full_translations = {}
        self.translations = {}
        self._translation_cache = {}
        if dictionary_name:
            self.full_translations, self.error = load_translations(dictionary_name)
        else:
            self.error = 'No valid dictionaries found in "dicts".'

    @property
    def dictionary_label(self):
        return next(
            (label for name, label in self.dictionaries if name == self.dictionary_name), ""
        )

    def name_for_label(self, label):
        return self.dictionary_labels.get(label)

    def switch(self, dictionary_name):
        translations, error = load_translations(dictionary_name)
        if error:
            return error
        self.dictionary_name = dictionary_name
        self.full_translations = translations
        self.translations = {}
        self._translation_cache.clear()
        self.error = None
        return None

    def _entry(self, word):
        if word not in self._translation_cache:
            self._translation_cache[word] = lookup_translation(
                word, self.full_translations,
                source_language=self.dictionary_name.partition("-")[0],
            )
        return self._translation_cache[word]

    def entry(self, word):
        return self._entry(word)

    def update(self, words):
        self.translations = {
            word: short_translation(self._entry(word)[1] or "")
            for word in words
        }
        return self.translations
