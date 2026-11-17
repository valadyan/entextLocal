# Text Scanner

Text Scanner is a local desktop application for building a frequency-sorted vocabulary from documents or pasted text. It helps you find word occurrences, review translations, track learned words, and import or export vocabulary tables.

The application runs entirely on your computer. It has no network service, telemetry, or database.

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| Ctrl+O | Open a document |
| Ctrl+S | Export CSV |
| Ctrl+N | New workspace |
| Ctrl+F | Focus the vocabulary filter |
| F5 | Rescan edited source text |
| Ctrl+A | Select all visible vocabulary rows |
| Delete | Remove selected words after confirmation |
| Return | Mark selected words learned or return them to the learning list |
| Escape | Clear the filter, otherwise clear selection |
| Ctrl++ / Ctrl+- | Zoom in or out |
| Ctrl+0 | Reset zoom |
| Ctrl+mouse wheel | Zoom where supported |


### Main features

- Extract words from text files, documents, ebooks, and pasted text.
- Edit source text and rescan it without losing learned status for words that remain.
- Sort and filter vocabulary by word, frequency, or translation.
- Click a word to highlight its occurrences in the source text.
- Open complete dictionary entries for translated words.
- Mark words as learned or return them to the learning list.
- Import and export CSV vocabulary tables.
- Switch between English and Russian interfaces with the **RU/EN** button.
- Use light and dark themes and adjustable interface zoom.

### Running the application

The application saves `state.json` in its current working directory when it closes normally. Launching from a read-only directory prevents session saving.

To run from source, use Python 3.10 or later:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

On Windows, use `.venv\Scripts\python` instead of `.venv/bin/python`.

### Basic workflow

1. Click **Open document**, or paste text into the source editor.
2. After editing the source, click **Rescan text** or press **F5**. Editing alone does not update word counts.
3. Use **To learn** and **Learned** to switch between vocabulary groups.
4. Type in the filter field to search both words and their loaded translations.
5. Click a word to highlight its source occurrences. Repeated clicks cycle through matches.
6. Click a translated cell to open its complete dictionary entry. The popup closes when you click outside it, press **Escape**, or use **Close**.
7. Select words and mark them learned, return them to the learning list, or remove them.

You can select multiple table rows with normal Ctrl/Shift selection or by pressing the left mouse button and dragging across rows. Dragging does not open translations or trigger source navigation.

### Dictionaries

The dictionary dropdown at the top controls translation lookup. It is separate from the **RU/EN** interface-language button.

Thirteen source-to-Russian dictionaries are bundled: Catalan, Czech, German, Greek, English, French, Italian, Japanese, Dutch, Polish, Spanish, Swedish, and Chinese.

Lookup first tries the exact headword and then dictionary-validated lemmas for supported languages. Japanese and Chinese use exact lookup only. Lemmatization is automatic but not perfect or context-sensitive.

### CSV import and export

- Export writes the active tab, regardless of the current filter.
- CSV files use UTF-8 with a BOM and the header `word,occurrences,translate`.
- Import reads words and counts but ignores translation columns.
- For duplicate or existing words, the larger count is retained.
- Imported words receive the learned status associated with the active tab.

### Supported document formats

Plain text and several common source/document extensions work without additional packages. Unknown extensions are also tried as plain text.

PDF, DOCX, EPUB, RTF, HTML, and XHTML parsing is included through required dependencies installed from `requirements.txt`: `pypdf`, `python-docx`, `EbookLib`, `striprtf`, and `html2text`.

Notes:

- Scanned PDFs require external OCR before text extraction.
- LIT files must first be converted externally, for example with Calibre.
- Chinese and Japanese text needs spaces or another external segmentation step between words.


### Session data and privacy

The complete session is saved only during normal window close. It includes source text, word counts, learned words, interface settings, source path, and selected dictionary.

**The source text in `state.json` may be sensitive.** Do not share or commit that file unless you are comfortable sharing its contents. Both `state.json` and `state.json.tmp` are excluded from Git.

The Info button near the source editor contains an application overview, usage instructions, and shortcuts.

## For developers

### Project structure

- `main.py` — minimal development entry point.
- `textscanner/app.py` — Tkinter UI, dialogs, events, shortcuts, themes, zoom, and coordination.
- `textscanner/documents.py` — document decoding, HTML cleanup, text extraction, and word regular expressions.
- `textscanner/library.py` — vocabulary counts, learned words, filtering, sorting, totals, and table actions.
- `textscanner/translations.py` — dictionary discovery/loading, lemmatization, lookup caching, and translation summaries.
- `textscanner/localization.py` — English interface strings and Russian translations.
- `textscanner/storage.py` — session normalization, JSON persistence, and CSV reading/writing.
- `textscanner/theme.py` — light and dark color palettes.
- `textscanner/windowing.py` — Windows titlebar styling with a no-op fallback elsewhere.
- `dicts/` — bundled dictionary index/data pairs and upstream notices.
- `main.spec` — persistent one-file, windowed PyInstaller configuration.

The normal data flow is:

```text
document or edited source
    -> documents.extract_words()
    -> WordLibrary
    -> App and vocabulary Treeview
```

Keep document parsing, vocabulary logic, translation management, localization, and storage independent of Tkinter. GUI behavior belongs in `App`.

### Development setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Required dependencies are pinned in `requirements.txt`: LemmInflect, Simplemma, pypdf, python-docx, EbookLib, striprtf, and html2text. NumPy, lxml, and typing-extensions are installed transitively. All document parsers are regular application imports and are included in packaged builds.

Dictionary resources and the development session file are resolved relative to the process working directory. Run commands from the project root unless using a packaged `_MEIPASS` resource directory.

### Verification

There is no automated test suite or configured linter, formatter, type-checker, or CI. Do not assume those tools are available.

After Python changes, run:

```bash
.venv/bin/python -m py_compile main.py textscanner/*.py
```

Exercise affected pure helpers directly without constructing `App`. Use temporary paths for storage checks and never overwrite the real `state.json` for testing.

A syntax check does not validate Tkinter behavior. With a real display, manually check affected workflows, including document scanning, source rescanning, filtering, sorting, drag and extended selection, occurrence navigation, translation popups, CSV round-trips, session restoration, dictionary switching, themes, interface languages, and zoom.

### PyInstaller build

Build from the project virtual environment using the checked-in spec:

```bash
.venv/bin/pyinstaller --clean --noconfirm main.spec
```

`main.spec` includes:

- Application modules discovered through `main.py`.
- All bundled `dicts` files.
- LemmInflect resource files.
- Simplemma `.plzma` language dictionaries.
- Required PDF, DOCX, EPUB, RTF, and HTML parser packages.
- NumPy through PyInstaller's existing hooks, including the `numpy.core.multiarray` compatibility import required by LemmInflect's pickled models.

The explicit LemmInflect and Simplemma data entries are required. Without them, packaged translation lookup can fail with missing files beneath the temporary `_MEI...` directory. The NumPy compatibility import is also required because PyInstaller does not discover modules referenced dynamically by those pickles.

Verify startup, translation lookup, and every document format on each target operating system; a Linux executable is not a Windows executable.

Launch packaged builds from a writable directory so the session can be saved.
