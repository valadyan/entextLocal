import os
import re
from html.parser import HTMLParser


WORD_RE = re.compile(r"[A-Za-z0-9\u0400-\u04FF]+(?:-[A-Za-z0-9\u0400-\u04FF]+)*")
WORD_CHAR_RE = re.compile(r"[A-Za-z0-9\u0400-\u04FF-]")

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


class _TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._hidden_depth += 1
        elif not self._hidden_depth and tag in (
            "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"
        ):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._hidden_depth:
            self._hidden_depth -= 1
        elif not self._hidden_depth and tag in ("p", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._hidden_depth:
            self.parts.append(data)

    def get_text(self):
        return re.sub(r"[ \t]+", " ", "".join(self.parts))


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
    try:
        import html2text
    except ImportError:
        parser = _TextHTMLParser()
        parser.feed(raw)
        parser.close()
        return parser.get_text()
    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    return converter.handle(raw)


def _extract_pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError(
            "PDF support requires the 'pypdf' package.\n"
            "Install it with: pip install pypdf"
        )
    parts = []
    for page in PdfReader(path).pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts)


def _extract_docx(path):
    try:
        import docx
    except ImportError:
        raise ValueError(
            "DOCX support requires the 'python-docx' package.\n"
            "Install it with: pip install python-docx"
        )
    document = docx.Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def _extract_epub(path):
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        raise ValueError(
            "EPUB support requires the 'EbookLib' package.\n"
            "Install it with: pip install EbookLib"
        )
    book = epub.read_epub(path)
    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        try:
            raw = item.get_content().decode("utf-8", errors="replace")
        except Exception:
            continue
        parts.append(_html_to_text(raw))
    return "\n".join(parts)


def extract_text_from_file(path):
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
        try:
            from striprtf.striprtf import rtf_to_text
        except ImportError:
            raise ValueError(
                "RTF support requires the 'striprtf' package.\n"
                "Install it with: pip install striprtf"
            )
        return rtf_to_text(_read_text_bytes(path))
    if extension in (".html", ".htm", ".xhtml"):
        return _html_to_text(_read_text_bytes(path))
    if extension == ".lit":
        raise ValueError(
            "LIT files are not supported directly.\n"
            "Convert the file to TXT or HTML first, for example with Calibre:\n\n"
            "ebook-convert \"book.lit\" \"book.txt\""
        )
    try:
        return _read_text_bytes(path)
    except OSError as error:
        raise ValueError(f"Unsupported file type '{extension}': {error}")
