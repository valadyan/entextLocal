import os
import re

import docx
import ebooklib
import html2text
from ebooklib import epub
from pypdf import PdfReader
from striprtf.striprtf import rtf_to_text

from .localization import tr


WORD_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*")
WORD_CHAR_RE = re.compile(r"(?:[^\W_]|-)")

FILE_TYPES = [
    (
        "Books and documents",
        "*.txt *.text *.md *.markdown *.rtf *.pdf *.docx *.epub "
        "*.html *.htm *.xhtml *.lit *.log *.srt",
    ),
    ("Text files", "*.txt *.text *.log *.md"),
    ("PDF", "*.pdf"),
    ("DOCX", "*.docx"),
    ("EPUB", "*.epub"),
    ("RTF", "*.rtf"),
    ("HTML", "*.html *.htm *.xhtml"),
    ("LIT (convert first)", "*.lit"),
    ("All files", "*.*"),
]


def extract_words(text):
    return [match.group(0).lower() for match in WORD_RE.finditer(text)]


def _read_text_bytes(path):
    with open(path, "rb") as file:
        raw = file.read()
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1251", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _html_to_text(raw):
    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    return converter.handle(raw)


def _extract_pdf(path):
    parts = []
    for page in PdfReader(path).pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts)


def _extract_docx(path):
    document = docx.Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def _extract_epub(path):
    book = epub.read_epub(path)
    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        try:
            raw = item.get_content().decode("utf-8", errors="replace")
        except Exception:
            continue
        parts.append(_html_to_text(raw))
    return "\n".join(parts)


def extract_text_from_file(path, language="en"):
    extension = os.path.splitext(path)[1].lower()
    plain_extensions = {
        "", ".txt", ".text", ".log", ".md", ".markdown", ".csv", ".tsv",
        ".json", ".xml", ".yml", ".yaml", ".py", ".js", ".ts", ".c", ".h",
        ".cpp", ".java", ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".bat",
        ".ini", ".cfg", ".conf", ".srt", ".tex",
    }
    if extension in plain_extensions:
        return _read_text_bytes(path)
    if extension == ".pdf":
        return _extract_pdf(path)
    if extension == ".docx":
        return _extract_docx(path)
    if extension == ".epub":
        return _extract_epub(path)
    if extension == ".rtf":
        return rtf_to_text(_read_text_bytes(path))
    if extension in (".html", ".htm", ".xhtml"):
        return _html_to_text(_read_text_bytes(path))
    if extension == ".lit":
        raise ValueError(tr(
            language,
            "LIT files are not supported directly.\n"
            "Convert the file to TXT or HTML first, for example with Calibre:\n\n"
            "ebook-convert \"book.lit\" \"book.txt\"",
        ))
    try:
        return _read_text_bytes(path)
    except OSError as error:
        raise ValueError(tr(
            language, "Unsupported file type '{extension}': {error}",
            extension=extension, error=error,
        ))
