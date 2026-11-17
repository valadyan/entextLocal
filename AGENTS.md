# Project overview

Text Scanner is a local, single-process Tkinter desktop application that extracts words from documents or pasted text and builds a frequency-sorted vocabulary. It supports editable source text, whole-word occurrence highlighting, translations, learned-word tracking, filtering, sorting, multi-selection actions, light/dark themes, UI zoom, and CSV import/export.

There is no backend, network service, database, or independently installable Python package. Source comments, docstrings, and UI text are in English; keep project documentation in English as well.

## Project structure and architecture

- `main.py`: minimal development entry point; constructs `App` and starts its Tk event loop.
- `textscanner/app.py`: `App(tk.Tk)`, all Tkinter/`ttk` UI construction, event handling, shortcuts, dialogs, theme/zoom rebuilding, and coordination between helpers.
- `textscanner/documents.py`: word regular expressions, plain-text decoding, HTML cleanup, and format-specific document extraction.
- `textscanner/library.py`: `WordLibrary`, which owns word counts and learned words and implements rescanning, merging, filtering, sorting, totals, and vocabulary actions.
- `textscanner/translations.py`: dictionary discovery/loading, multilingual lemmatization, short-entry extraction, and `TranslationManager`, which owns the selected dictionary, full definitions, lookup cache, and short translations.
- `textscanner/storage.py`: session normalization and snapshots, session JSON loading, atomic session writes, and CSV reading/writing.
- `textscanner/localization.py`: English interface source strings, Russian translations, and string formatting for both interface languages.
- `textscanner/theme.py`: self-contained `LIGHT` and `DARK` color palette dictionaries.
- `textscanner/windowing.py`: Windows titlebar styling with a no-op fallback on other platforms.
- `textscanner/__init__.py`: package docstring only.
- `dicts/`: thirteen bundled source-to-Russian dictionary directories: Catalan, Czech, German, Greek, English, French, Italian, Japanese, Dutch, Polish, Spanish, Swedish, and Chinese. Each contains a matching `.index`/`.dict.dz` pair plus upstream `README`, `INSTALL`, and `COPYING` files.
- `requirements.txt`: the Python dependency manifest; it pins LemmInflect, Simplemma, and all document parsers, with NumPy, lxml, and typing-extensions installed transitively.
- `.gitignore`: excludes Python bytecode, virtual environments, build output, tool caches, and session files.

The normal data flow is `documents.extract_text_from_file()` or edited source text -> `documents.extract_words()` -> `WordLibrary` -> the vocabulary `Treeview` in `App`. `TranslationManager` supplies table summaries and full popup entries. `storage.py` handles session and CSV data at the application boundary. Keep document parsing, vocabulary logic, translation management, and storage independent of Tkinter; GUI behavior belongs in `App`, while reusable non-GUI behavior belongs in the appropriate helper module.

Application state is held in memory while the UI runs. The complete session is written only during normal window close. Editing source text marks it as having unscanned changes but does not update counts until the user rescans.

## Technology, configuration, and dependencies

The implementation uses Python, the standard library (principally `tkinter`, `csv`, `json`, and `re`), LemmInflect for English lemmatization, Simplemma for other supported languages, pypdf for PDF, python-docx for DOCX, EbookLib for EPUB, striprtf for RTF, and html2text for HTML. NumPy is LemmInflect's runtime dependency. Simplemma 2.0 requires Python 3.10 or later. A working Tk installation and graphical display are required to run the application; do not construct Tk windows in a headless environment.

Project configuration is held in `requirements.txt`, `.gitignore`, and `main.spec`; user and developer documentation is in `README.md`. There is no `pyproject.toml`, `setup.py`, lockfile, linter, formatter, type-checker, test-runner, or CI. Do not describe unconfigured tools as available.

From the project root, set up a project-local virtual environment and run the development entry point with:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

The working directory matters: dictionary resources and `state.json` are resolved relative to the process working directory unless a packaged application supplies PyInstaller's `_MEIPASS` resource directory.

LemmInflect and Simplemma are imported lazily only for fallback lookups in their supported languages. They must be installed for inflection support rather than silently falling back to incomplete custom rules. Japanese and Chinese use exact dictionary lookup only.

All document parsers are required dependencies and regular imports in `documents.py`. They are installed through `requirements.txt` and included in PyInstaller builds. PDF, DOCX, EPUB, RTF, HTML, and XHTML use their dedicated parsers; HTML and EPUB both use html2text. LIT files are not parsed directly and must be converted externally, for example with Calibre. Scanned PDFs require external OCR before text extraction.

Plain text and several source/document extensions are decoded by trying UTF-8 with BOM, UTF-8, UTF-16, CP1251, and Latin-1. Unknown extensions also fall back to the plain-text reader. PDF, DOCX, EPUB, RTF, HTML, and LIT receive their explicit handling in `documents.py`.

## Build and verification commands

No compilation or bundling step is required for development. Use this syntax-only check after Python changes:

```bash
python -m py_compile main.py textscanner/*.py
```

This creates ignored `__pycache__` directories and bytecode; remove generated bytecode if it is not wanted.

There is no automated test suite. Do not add test files or testing scaffolding unless requested. After behavior changes:

1. Run the syntax check above.
2. Exercise affected pure helpers in `documents.py`, `library.py`, `translations.py`, and `storage.py` directly, without constructing `App`. Use temporary paths for CSV/session checks rather than overwriting the real `state.json`.
3. Manually exercise affected GUI flows with a real display by running `.venv/bin/python main.py`.
4. When relevant, verify document scanning, source rescanning, filtering, sorting, selection actions, occurrence navigation, CSV round-trips, session restoration, translation loading, theme switching, and zoom.

A syntax check cannot validate Tkinter layout, callbacks, file dialogs, or session restoration, so it is not a substitute for manual GUI verification.

## Code style and change guidelines

- Follow the existing compact, imperative Python style, four-space indentation, `snake_case` names, module-level helpers, sparse annotations, and package-relative imports.
- Internal `App` methods use a leading underscore. Keep reusable non-GUI logic out of `app.py` and keep Tkinter imports out of helper modules.
- Use the established Tkinter/`ttk` widgets and `LIGHT`/`DARK` palettes rather than introducing another UI framework.
- Keep all document parser dependencies required and imported normally in `documents.py`. Preserve user-facing parsing errors for invalid or unreadable documents.
- Preserve lowercasing and the Unicode word syntax in `documents.py`: letters/digits from all Unicode scripts, excluding underscores, with hyphens allowed only between word-character runs. Source occurrence highlighting uses the corresponding whole-word boundary expression and case-insensitive search. Chinese/Japanese text still needs spaces or another external segmentation step between words.
- Update affected behavior and persistence code together. In particular, keep `App._save_state()`, `make_session_state()`, `normalize_state()`, and `App.__init__()` restoration defaults consistent when adding session fields.

## Application behavior to preserve

- Opening a document extracts its text before asking to replace the current workspace. A confirmed open clears previous counts/learned status and scans the new text. Rescanning edited source replaces counts while retaining learned status only for words still present.
- The **To learn** tab excludes learned words; **Learned** contains only learned words. Count sorting is descending by default with alphabetical tie-breaking. Word, count, and translation headings are sortable.
- Filtering searches both words and loaded translations. The table supports normal Tkinter extended selection, left-button drag-range selection, Ctrl+A, learned/unlearned actions, Return to toggle the active action, and confirmed removal. Dragging does not trigger source navigation or translation popups; translated rows are highlighted while hovering their translation cells.
- Clicking a word highlights whole-word source matches. Repeated clicks cycle through matches and scroll to the current occurrence.
- The Translation column shows only the first Russian equivalent. Clicking a translated cell opens the complete multi-line dictionary entry in a read-only window that closes when the user clicks outside it. Hovering highlights only the translation cell text through an overlay, not the entire row.
- The Info button below the source editor opens localized application information, usage instructions, and shortcuts.
- The Dictionary dropdown lists valid dictionary folders with friendly language-pair labels. Switching preserves the source text, counts, learned status, and active filter while rebuilding translations. A failed switch keeps the previous dictionary active.
- Lookup prefers exact headwords, then tries dictionary-validated lemmas. English uses LemmInflect noun, verb, adjective, and adverb candidates, including out-of-vocabulary forms. Catalan, Czech, German, Greek, French, Italian, Dutch, Polish, Spanish, and Swedish use Simplemma. Japanese and Chinese use exact lookup only. Lemmatization is broad but not perfect or context-sensitive. A popup opened through an inflected word identifies the resolved headword.
- CSV export writes a UTF-8 BOM and the header `word,occurrences,translate` for the active tab, independent of the current filter. CSV import reads words/counts, ignores translation columns, keeps the larger count for duplicate/existing words, and applies the active tab's learned status to imported words.
- Important shortcuts are Ctrl+O (open), Ctrl+S (export), Ctrl+N (new workspace), Ctrl+F (filter), F5 (rescan), Escape (clear filter, otherwise clear selection), Delete (remove selected), and Ctrl plus/minus/0 (zoom). Ctrl+mouse wheel also zooms where supported.
- Theme, zoom, and interface-language changes rebuild the UI while preserving source text, geometry, scroll position, and unscanned-change status. The header language button switches between English and Russian. Zoom is clamped to 50%-300%.

## Persistence, resources, and security

- Each `dicts/<name>/<name>.index` and matching `.dict.dz` pair is discovered as a selectable dictionary. The index stores headwords with numeric base64 byte offsets and lengths into the gzip-compressed UTF-8 dictionary data. Paths are resolved relative to PyInstaller `_MEIPASS` when present and otherwise relative to the process working directory. Missing or invalid selected content produces a startup warning and empty translations.
- Translation loading decompresses the selected dictionary data, preserves multi-line definitions, merges duplicate headwords, and lowercases keys. The app caches exact/fallback lookups for the current vocabulary and derives one-word summaries for the table, filtering, sorting, and CSV export while retaining full definitions for the popup. `dict.json` is not used for translations.
- `state.json` is read from and written to the process working directory, not the source file's directory. It stores geometry, complete source text, counts, learned words, active tab, theme, zoom, source path, selected translation dictionary, and interface language. Missing or invalid state silently becomes an empty session; an unavailable saved dictionary falls back to English–Russian or the first available dictionary.
- Session writes use `state.json.tmp` followed by `os.replace`. Save failures produce a warning during close.
- The complete source text in `state.json` may be sensitive. Do not commit it or copy it into logs, fixtures, or documentation without user consent. Both `state.json` and `state.json.tmp` are ignored by Git.
- Runtime application writes are limited to the established session files and user-selected CSV export paths. The application reads user-selected documents/imports and dictionary resources; it has no network functionality.
- Avoid logging document contents, adding telemetry, or broadening file access without an explicit requirement. Preserve the bundled dictionaries' upstream license and notice files.

## Deployment and packaging

`main.spec` configures a one-file, windowed PyInstaller build. It includes the application modules through `main.py`, the `dicts` resources, LemmInflect resources, Simplemma language data, all required document parsers, and NumPy through PyInstaller's existing hooks. The `numpy.core.multiarray` hidden import is required for LemmInflect's pickled models with NumPy 2.x. Build it from the project virtual environment with:

```bash
.venv/bin/pyinstaller --clean --noconfirm main.spec
```

`resource_path()` resolves bundled dictionaries through `_MEIPASS`. All document parsers are installed through `requirements.txt` and bundled in the executable. Verify startup, translation lookup, and every document format on each target operating system. The session still uses the process working directory, so launch the executable from a writable location. Windows-only titlebar styling in `windowing.py` already degrades to a no-op on other platforms.
