import csv
import os
import sys
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from .documents import FILE_TYPES, WORD_CHAR_RE, extract_text_from_file
from .library import WordLibrary
from .storage import (
    STATE_FILE,
    load_state,
    load_translations,
    read_word_table,
    save_state,
    write_word_table,
)
from .theme import DARK, LIGHT


def set_titlebar_color(window, hex_color, dark=True):
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        color = hex_color.lstrip("#")
        red, green, blue = (int(color[index:index + 2], 16) for index in (0, 2, 4))
        colorref = ctypes.c_int((blue << 16) | (green << 8) | red)
        hwnd = wintypes.HWND(window.winfo_id())
        user32 = ctypes.windll.user32
        hwnd = wintypes.HWND(user32.GetAncestor(hwnd, 2))
        dwm = ctypes.windll.dwmapi
        dark_flag = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):
            if dwm.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(dark_flag), ctypes.sizeof(dark_flag)
            ) == 0:
                break
        for attribute in (35, 34):
            dwm.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(colorref), ctypes.sizeof(colorref)
            )
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
        return True
    except (AttributeError, OSError, ValueError):
        return False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Text Scanner")
        self.minsize(960, 600)

        self._state = load_state()
        self.library = WordLibrary(
            self._state.get("dictionary", {}), self._state.get("learned", [])
        )
        self.translations, translation_error = load_translations()
        self.theme_name = self._state.get("theme", "light")
        if self.theme_name not in ("light", "dark"):
            self.theme_name = "light"
        self.palette = DARK if self.theme_name == "dark" else LIGHT
        try:
            self.scale = max(0.5, min(3.0, float(self._state.get("scale", 1.0))))
        except (TypeError, ValueError):
            self.scale = 1.0

        self.current_tab = self._state.get("current_tab", "all")
        if self.current_tab not in ("all", "learned"):
            self.current_tab = "all"
        self.source_path = self._state.get("source_path", "")
        if not isinstance(self.source_path, str):
            self.source_path = ""
        self.selected = set()
        self.rows_data = []
        self.sort_column = "count"
        self.sort_reverse = True
        self.last_click_word = None
        self.last_occurrence = 0
        self._source_dirty = False

        self.query_var = tk.StringVar()
        self.stats_var = tk.StringVar()
        self.source_stats_var = tk.StringVar()
        self.document_var = tk.StringVar()
        self.selection_var = tk.StringVar(value="No words selected")
        self.status_var = tk.StringVar(value="Open a document or paste text to begin.")
        self.zoom_var = tk.StringVar()

        self._setup_style()
        self._build_ui()
        self.query_var.trace_add("write", self._on_query_changed)
        self._bind_shortcuts()
        self._restore_state()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._show_startup_warning, translation_error)

    def _px(self, value):
        return max(1, int(round(value * self.scale)))

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        palette = self.palette
        self.configure(bg=palette["bg"])

        style.configure(
            ".", background=palette["bg"], foreground=palette["text"],
            font=("Segoe UI", self._px(10)), bordercolor=palette["border"],
        )
        style.configure("TFrame", background=palette["bg"])
        style.configure("Card.TFrame", background=palette["card"])
        style.configure("TLabel", background=palette["bg"], foreground=palette["text"])
        style.configure("Card.TLabel", background=palette["card"], foreground=palette["text"])
        style.configure(
            "Muted.TLabel", background=palette["card"], foreground=palette["muted"],
            font=("Segoe UI", self._px(9)),
        )
        style.configure(
            "Status.TLabel", background=palette["bg"], foreground=palette["muted"],
            font=("Segoe UI", self._px(9)),
        )
        style.configure(
            "Title.TLabel", background=palette["card"], foreground=palette["text"],
            font=("Segoe UI Semibold", self._px(19)),
        )
        style.configure(
            "Section.TLabel", background=palette["card"], foreground=palette["text"],
            font=("Segoe UI Semibold", self._px(12)),
        )
        style.configure(
            "TButton", padding=(self._px(11), self._px(7)), relief="flat",
            background=palette["heading"], foreground=palette["text"], borderwidth=1,
        )
        style.map(
            "TButton",
            background=[("active", palette["accent_soft"]), ("pressed", palette["accent_soft2"])],
            foreground=[("disabled", palette["muted"])],
            bordercolor=[("focus", palette["accent"]), ("!focus", palette["border"])],
        )
        style.configure(
            "Primary.TButton", background=palette["accent"], foreground="#ffffff",
            bordercolor=palette["accent"], font=("Segoe UI Semibold", self._px(10)),
        )
        style.map(
            "Primary.TButton",
            background=[("active", palette["accent_hover"]), ("pressed", palette["accent_hover"])],
            foreground=[("disabled", palette["muted"])],
        )
        style.configure(
            "Danger.TButton", background=palette["danger_bg"], foreground=palette["danger"],
        )
        style.map("Danger.TButton", background=[("active", palette["danger_hover"])])
        style.configure(
            "Tab.TButton", padding=(self._px(14), self._px(7)),
            background=palette["heading"], foreground=palette["muted"],
        )
        style.configure(
            "TabActive.TButton", padding=(self._px(14), self._px(7)),
            background=palette["accent_soft"], foreground=palette["accent"],
            font=("Segoe UI Semibold", self._px(10)),
        )
        style.configure(
            "TEntry", fieldbackground=palette["input"], foreground=palette["text"],
            bordercolor=palette["border"], lightcolor=palette["border"],
            darkcolor=palette["border"], padding=(self._px(8), self._px(7)),
        )
        style.map("TEntry", bordercolor=[("focus", palette["accent"])])
        style.configure(
            "Treeview", background=palette["card"], fieldbackground=palette["card"],
            foreground=palette["text"], rowheight=self._px(34), borderwidth=0,
            font=("Segoe UI", self._px(10)),
        )
        style.configure(
            "Treeview.Heading", background=palette["heading"], foreground=palette["muted"],
            relief="flat", font=("Segoe UI Semibold", self._px(9)),
            padding=(self._px(8), self._px(8)),
        )
        style.map(
            "Treeview",
            background=[("selected", palette["selection"])],
            foreground=[("selected", palette["text"])],
        )
        style.map("Treeview.Heading", background=[("active", palette["accent_soft"])])
        style.configure(
            "Vertical.TScrollbar", background=palette["scroll"], troughcolor=palette["card"],
            borderwidth=0, arrowsize=self._px(12),
        )
        style.map("Vertical.TScrollbar", background=[("active", palette["muted"])])

    def _build_ui(self):
        header = ttk.Frame(self, style="Card.TFrame", padding=(self._px(20), self._px(14)))
        header.pack(fill=tk.X)
        title_group = ttk.Frame(header, style="Card.TFrame")
        title_group.pack(side=tk.LEFT)
        ttk.Label(title_group, text="Text Scanner", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_group, text="Turn your reading into a personal vocabulary", style="Muted.TLabel"
        ).pack(anchor="w", pady=(self._px(2), 0))
        self.theme_button = ttk.Button(header, command=self.toggle_theme)
        self.theme_button.pack(side=tk.RIGHT)

        toolbar = ttk.Frame(self, padding=(self._px(16), self._px(12)))
        toolbar.pack(fill=tk.X)
        ttk.Button(
            toolbar, text="Open document", style="Primary.TButton", command=self.open_document
        ).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="New workspace", command=self.new_workspace).pack(
            side=tk.LEFT, padx=(self._px(8), 0)
        )
        ttk.Button(toolbar, text="Export CSV", command=self.save_csv).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Import CSV", command=self.load_csv).pack(
            side=tk.RIGHT, padx=(0, self._px(8))
        )

        self.paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, bg=self.palette["bg"], sashwidth=self._px(7),
            sashrelief=tk.FLAT, bd=0, opaqueresize=True,
        )
        self.paned.pack(
            fill=tk.BOTH, expand=True, padx=self._px(16), pady=(0, self._px(12))
        )
        self._build_source_panel()
        self._build_vocabulary_panel()

        footer = ttk.Frame(self, padding=(self._px(18), 0, self._px(18), self._px(10)))
        footer.pack(fill=tk.X)
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT)
        ttk.Button(footer, text="Reset zoom", command=self._zoom_reset).pack(side=tk.RIGHT)
        ttk.Label(footer, textvariable=self.zoom_var, style="Status.TLabel").pack(
            side=tk.RIGHT, padx=(0, self._px(8))
        )
        self._update_theme_button()
        self._update_zoom_label()

    def _build_source_panel(self):
        left = ttk.Frame(self.paned, style="Card.TFrame")
        self.paned.add(left, minsize=self._px(300), stretch="always")
        heading = ttk.Frame(
            left, style="Card.TFrame", padding=(self._px(16), self._px(14))
        )
        heading.pack(fill=tk.X)
        ttk.Label(heading, text="Source text", style="Section.TLabel").pack(anchor="w")
        ttk.Label(heading, textvariable=self.document_var, style="Muted.TLabel").pack(
            anchor="w", pady=(self._px(3), 0)
        )

        text_frame = ttk.Frame(
            left, style="Card.TFrame", padding=(self._px(12), 0, self._px(12), 0)
        )
        text_frame.pack(fill=tk.BOTH, expand=True)
        self.text = tk.Text(
            text_frame, wrap=tk.WORD, undo=True, relief="flat", bd=0,
            padx=self._px(10), pady=self._px(10), font=("Consolas", self._px(10)),
            bg=self.palette["input"], fg=self.palette["text"],
            insertbackground=self.palette["text"], selectbackground=self.palette["accent_soft2"],
            selectforeground=self.palette["text"], spacing1=self._px(2), spacing3=self._px(2),
            highlightthickness=1, highlightbackground=self.palette["border"],
            highlightcolor=self.palette["accent"],
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.tag_configure("highlight", background=self.palette["highlight"])
        self.text.tag_configure("current", background=self.palette["current"])
        self.text.bind("<<Modified>>", self._on_text_modified)

        source_footer = ttk.Frame(
            left, style="Card.TFrame", padding=(self._px(14), self._px(10))
        )
        source_footer.pack(fill=tk.X)
        ttk.Label(source_footer, textvariable=self.source_stats_var, style="Muted.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Button(source_footer, text="Rescan text  (F5)", command=self.rescan_text).pack(
            side=tk.RIGHT
        )

    def _build_vocabulary_panel(self):
        right = ttk.Frame(self.paned, style="Card.TFrame")
        self.paned.add(right, minsize=self._px(430), stretch="always")
        heading = ttk.Frame(
            right, style="Card.TFrame", padding=(self._px(16), self._px(14), self._px(16), 0)
        )
        heading.pack(fill=tk.X)
        ttk.Label(heading, text="Vocabulary", style="Section.TLabel").pack(anchor="w")
        ttk.Label(heading, textvariable=self.stats_var, style="Muted.TLabel").pack(
            anchor="w", pady=(self._px(4), 0)
        )

        controls = ttk.Frame(
            right, style="Card.TFrame", padding=(self._px(14), self._px(12), self._px(14), 0)
        )
        controls.pack(fill=tk.X)
        self.tab_buttons = {}
        for key, label in (("all", "To learn"), ("learned", "Learned")):
            button = ttk.Button(
                controls, text=label, style="Tab.TButton",
                command=lambda tab=key: self.switch_tab(tab),
            )
            button.pack(side=tk.LEFT, padx=(0, self._px(6)))
            self.tab_buttons[key] = button

        search_frame = ttk.Frame(
            right, style="Card.TFrame", padding=(self._px(14), self._px(10), self._px(14), 0)
        )
        search_frame.pack(fill=tk.X)
        ttk.Label(search_frame, text="Filter", style="Muted.TLabel").pack(
            side=tk.LEFT, padx=(0, self._px(8))
        )
        self.search_entry = ttk.Entry(search_frame, textvariable=self.query_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.insert(0, "")
        ttk.Button(search_frame, text="Clear", command=self.clear_search).pack(
            side=tk.LEFT, padx=(self._px(6), 0)
        )

        table_frame = ttk.Frame(
            right, style="Card.TFrame", padding=(self._px(12), self._px(10), self._px(12), 0)
        )
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("word", "count", "translation", "actions")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="extended"
        )
        self._columns = (
            ("word", 180, "Word", "w"),
            ("count", 95, "Count", "center"),
            ("translation", 240, "Translation", "w"),
            ("actions", 125, "Action", "center"),
        )
        for column, width, label, anchor in self._columns:
            self.tree.column(column, width=self._px(width), anchor=anchor, stretch=True)
            if column != "actions":
                self.tree.heading(column, text=label, command=lambda c=column: self.sort_by(c))
            else:
                self.tree.heading(column, text=label)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.tag_configure("odd", background=self.palette["zebra"])
        self.tree.tag_configure("even", background=self.palette["row"])
        self.tree.tag_configure("untranslated", foreground=self.palette["untranslated"])
        self.tree.tag_configure("action", foreground=self.palette["accent"])
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<ButtonPress-1>", self._on_tree_press)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_release)
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Delete>", lambda event: self.remove_selected())
        self.tree.bind("<Return>", lambda event: self.toggle_selected())
        self.tree.bind("<Control-a>", self._select_all)
        self.tree.bind("<Control-A>", self._select_all)

        selection_bar = ttk.Frame(
            right, style="Card.TFrame", padding=(self._px(14), self._px(12))
        )
        selection_bar.pack(fill=tk.X)
        ttk.Label(selection_bar, textvariable=self.selection_var, style="Muted.TLabel").pack(
            anchor="w", pady=(0, self._px(8))
        )
        actions = ttk.Frame(selection_bar, style="Card.TFrame")
        actions.pack(fill=tk.X)
        self.learn_button = ttk.Button(actions, text="Mark learned", command=self.learn_selected)
        self.learn_button.pack(side=tk.LEFT)
        self.return_button = ttk.Button(actions, text="Move to learn", command=self.unlearn_selected)
        self.remove_button = ttk.Button(
            actions, text="Remove", style="Danger.TButton", command=self.remove_selected
        )
        self.remove_button.pack(side=tk.RIGHT)
        self.clear_button = ttk.Button(actions, text="Clear selection", command=self.clear_selection)
        self.clear_button.pack(side=tk.RIGHT, padx=(0, self._px(6)))

    def _bind_shortcuts(self):
        self.bind_all("<Control-o>", lambda event: self.open_document())
        self.bind_all("<Control-O>", lambda event: self.open_document())
        self.bind_all("<Control-s>", lambda event: self.save_csv())
        self.bind_all("<Control-S>", lambda event: self.save_csv())
        self.bind_all("<Control-n>", lambda event: self.new_workspace())
        self.bind_all("<Control-N>", lambda event: self.new_workspace())
        self.bind_all("<Control-f>", self._focus_search)
        self.bind_all("<Control-F>", self._focus_search)
        self.bind_all("<F5>", lambda event: self.rescan_text())
        self.bind_all("<Escape>", self._on_escape)
        for sequence in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.bind_all(sequence, lambda event: self._zoom_by(1))
        for sequence in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.bind_all(sequence, lambda event: self._zoom_by(-1))
        for sequence in ("<Control-0>", "<Control-KP_0>"):
            self.bind_all(sequence, lambda event: self._zoom_reset())
        self.bind_all("<Control-MouseWheel>", self._on_ctrl_wheel)
        self.bind_all("<Control-Button-4>", lambda event: self._zoom_by(1))
        self.bind_all("<Control-Button-5>", lambda event: self._zoom_by(-1))

    def _show_startup_warning(self, error):
        if error:
            messagebox.showwarning(
                "Translation dictionary",
                f'Failed to load "dict.json":\n{error}\n\nTranslations will be empty.',
                parent=self,
            )

    def _restore_state(self):
        geometry = self._state.get("geometry")
        if isinstance(geometry, str) and geometry:
            try:
                self.geometry(geometry)
            except tk.TclError:
                self.geometry("1280x760")
        else:
            self.geometry("1280x760")
        text = self._state.get("text", "")
        self._set_text(text if isinstance(text, str) else "")

    def _set_text(self, text):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self._source_dirty = False
        self._update_source_stats()

    def _on_text_modified(self, event=None):
        if not self.text.edit_modified():
            return
        self._source_dirty = True
        self.text.edit_modified(False)
        self._update_source_stats()

    def _update_source_stats(self):
        content = self.text.get("1.0", "end-1c")
        lines = len(content.splitlines()) if content else 0
        suffix = " · unsaved scan changes" if self._source_dirty else ""
        self.source_stats_var.set(f"{lines} lines · {len(content)} characters{suffix}")
        if self.source_path:
            name = os.path.basename(self.source_path)
        elif content:
            name = "Pasted or edited text"
        else:
            name = "No document loaded"
        self.document_var.set(name)

    def _refresh(self):
        self._update_tab_labels()
        self._update_sort_headings()
        entries = self.library.entries(
            self.current_tab, self.query_var.get(), self.translations,
            self.sort_column, self.sort_reverse,
        )
        visible_words = {word for word, _ in entries}
        self.selected.intersection_update(visible_words)
        self.tree.delete(*self.tree.get_children())
        self.rows_data = entries
        selected_ids = []
        for index, (word, count) in enumerate(entries):
            translation = self.translations.get(word, "")
            action = "Move to learn" if self.current_tab == "learned" else "Mark learned"
            tags = ["odd" if index % 2 else "even"]
            if not translation:
                tags.append("untranslated")
            item = self.tree.insert(
                "", "end", iid=f"row{index}",
                values=(word, count, translation or "—", action), tags=tuple(tags),
            )
            if word in self.selected:
                selected_ids.append(item)
        if selected_ids:
            self.tree.selection_set(selected_ids)
        self._update_stats()
        self._update_selection_ui()

    def _update_tab_labels(self):
        to_learn = len(self.library.counts) - len(self.library.learned)
        labels = {"all": f"To learn  {to_learn}", "learned": f"Learned  {len(self.library.learned)}"}
        for key, button in self.tab_buttons.items():
            button.configure(
                text=labels[key],
                style="TabActive.TButton" if key == self.current_tab else "Tab.TButton",
            )

    def _update_sort_headings(self):
        for column, _width, label, _anchor in self._columns:
            if column == "actions":
                continue
            suffix = ""
            if column == self.sort_column:
                suffix = "  ▼" if self.sort_reverse else "  ▲"
            self.tree.heading(column, text=label + suffix)

    def _update_stats(self):
        totals = self.library.totals(self.current_tab, self.query_var.get(), self.translations)
        if not self.library.counts:
            self.stats_var.set("Your word list is empty")
            return
        text = (
            f"{totals['visible_words']} words · {totals['visible_occurrences']} occurrences"
        )
        if self.query_var.get().strip():
            text += f" · filtered from {totals['total_words']} unique words"
        self.stats_var.set(text)

    def _update_selection_ui(self):
        count = len(self.selected)
        self.selection_var.set("No words selected" if not count else f"{count} selected")
        state = "normal" if count else "disabled"
        self.clear_button.configure(state=state)
        self.remove_button.configure(state=state)
        self.learn_button.configure(state=state if self.current_tab == "all" else "disabled")
        self.return_button.configure(state=state if self.current_tab == "learned" else "disabled")
        self.learn_button.pack_forget()
        self.return_button.pack_forget()
        target = self.learn_button if self.current_tab == "all" else self.return_button
        target.pack(side=tk.LEFT)

    def _on_query_changed(self, *args):
        if hasattr(self, "tree"):
            self.selected.clear()
            self._refresh()

    def _on_tree_select(self, event=None):
        self.selected = {
            self.rows_data[int(item[3:])][0]
            for item in self.tree.selection() if item.startswith("row")
        }
        self._update_selection_ui()

    def _on_tree_press(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        item = self.tree.identify_row(event.y)
        if item and self.tree.identify_column(event.x) == "#4":
            word = self._row_word(item)
            if self.current_tab == "all":
                self.library.mark_learned([word])
            else:
                self.library.mark_unlearned([word])
            self.selected.discard(word)
            self._refresh()
            self.status_var.set(f"Updated '{word}'.")
            return "break"

    def _on_tree_release(self, event):
        if event.state & 0x0005 or self.tree.identify_region(event.x, event.y) != "cell":
            return
        item = self.tree.identify_row(event.y)
        if not item or self.tree.identify_column(event.x) == "#4":
            return
        word = self._row_word(item)
        if word == self.last_click_word:
            self.last_occurrence += 1
        else:
            self.last_occurrence = 0
            self.last_click_word = word
        self._jump_to_word(word, self.last_occurrence)

    def _on_tree_motion(self, event):
        item = self.tree.identify_row(event.y)
        is_action = bool(item) and self.tree.identify_column(event.x) == "#4"
        self.tree.configure(cursor="hand2" if is_action else "")

    def _row_word(self, item):
        return self.rows_data[int(item[3:])][0]

    def _find_word_positions(self, word):
        positions = []
        count = tk.IntVar()
        start = "1.0"
        while True:
            position = self.text.search(word, start, stopindex="end", nocase=True, count=count)
            if not position or not count.get():
                break
            end = f"{position}+{count.get()}c"
            before = self.text.get(f"{position}-1c", position) if position != "1.0" else ""
            after = self.text.get(end, f"{end}+1c")
            if not WORD_CHAR_RE.match(before or " ") and not WORD_CHAR_RE.match(after or " "):
                positions.append((position, end))
            start = end
        return positions

    def _jump_to_word(self, word, occurrence=0):
        positions = self._find_word_positions(word)
        self.text.tag_remove("highlight", "1.0", "end")
        self.text.tag_remove("current", "1.0", "end")
        if not positions:
            self.status_var.set(f"'{word}' is not present in the current source text.")
            return
        for start, end in positions:
            self.text.tag_add("highlight", start, end)
        start, end = positions[occurrence % len(positions)]
        self.text.tag_add("current", start, end)
        self.text.see(start)
        self.status_var.set(
            f"'{word}': occurrence {occurrence % len(positions) + 1} of {len(positions)}"
        )

    def switch_tab(self, tab):
        self.current_tab = tab
        self.selected.clear()
        self.last_click_word = None
        self._refresh()

    def sort_by(self, column):
        if column == self.sort_column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = column == "count"
        self._refresh()

    def learn_selected(self):
        words = set(self.selected)
        self.library.mark_learned(words)
        self.selected.clear()
        self._refresh()
        self.status_var.set(f"Marked {len(words)} words as learned.")

    def unlearn_selected(self):
        words = set(self.selected)
        self.library.mark_unlearned(words)
        self.selected.clear()
        self._refresh()
        self.status_var.set(f"Moved {len(words)} words back to the learning list.")

    def toggle_selected(self):
        if self.current_tab == "all":
            self.learn_selected()
        else:
            self.unlearn_selected()
        return "break"

    def remove_selected(self):
        words = set(self.selected)
        if not words:
            return "break"
        if not messagebox.askyesno(
            "Remove words", f"Remove {len(words)} words from this workspace?", parent=self
        ):
            return "break"
        self.library.remove(words)
        self.selected.clear()
        self._refresh()
        self.status_var.set(f"Removed {len(words)} words.")
        return "break"

    def clear_selection(self):
        self.tree.selection_remove(self.tree.selection())
        self.selected.clear()
        self._update_selection_ui()

    def _select_all(self, event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def clear_search(self):
        self.query_var.set("")
        self.search_entry.focus_set()

    def _focus_search(self, event=None):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")
        return "break"

    def _on_escape(self, event=None):
        if self.query_var.get():
            self.clear_search()
        else:
            self.clear_selection()
        return "break"

    def _confirm_discard(self):
        if not self.library.counts and not self.text.get("1.0", "end-1c").strip():
            return True
        return messagebox.askyesno(
            "Replace workspace",
            "Replace the current text and word counts? Your previous session is saved only when the app closes.",
            parent=self,
        )

    def new_workspace(self):
        if not self._confirm_discard():
            return
        self.library.clear()
        self.source_path = ""
        self.selected.clear()
        self.query_var.set("")
        self._set_text("")
        self._refresh()
        self.status_var.set("New workspace ready.")

    def open_document(self):
        path = filedialog.askopenfilename(parent=self, filetypes=FILE_TYPES)
        if not path:
            return
        try:
            text = extract_text_from_file(path)
        except (ValueError, OSError) as error:
            messagebox.showerror("Open document", str(error), parent=self)
            return
        except Exception as error:
            messagebox.showerror(
                "Open document", f"The document could not be parsed:\n{error}", parent=self
            )
            return
        if not text.strip():
            messagebox.showwarning(
                "Open document",
                f"No text could be extracted from {os.path.basename(path)}.\n\n"
                "If this is a scanned PDF, OCR is required first.",
                parent=self,
            )
            return
        if not self._confirm_discard():
            return
        self.library.clear()
        unique_count = self.library.replace_text(text)
        if not unique_count:
            messagebox.showwarning("Scan document", "No words found in the text.", parent=self)
            return
        self.source_path = path
        self.current_tab = "all"
        self.selected.clear()
        self.query_var.set("")
        self._set_text(text)
        self._refresh()
        self.status_var.set(
            f"Loaded {os.path.basename(path)}: {unique_count} unique words, "
            f"{sum(self.library.counts.values())} occurrences."
        )

    def rescan_text(self):
        text = self.text.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Rescan text", "Paste or open some text first.", parent=self)
            return
        count = self.library.replace_text(text)
        if not count:
            messagebox.showwarning("Rescan text", "No words found in the text.", parent=self)
            return
        self.selected.clear()
        self._source_dirty = False
        self.text.edit_modified(False)
        self._update_source_stats()
        self._refresh()
        self.status_var.set(f"Scan complete: {count} unique words.")

    def load_csv(self):
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            counts = read_word_table(path)
        except (OSError, csv.Error) as error:
            messagebox.showerror("Import CSV", f"Failed to load the CSV file:\n{error}", parent=self)
            return
        self.library.merge_counts(counts, learned=self.current_tab == "learned")
        self._refresh()
        self.status_var.set(f"Imported {len(counts)} words into the active tab.")

    def save_csv(self):
        entries = self.library.tab_entries(self.current_tab, self.translations)
        if not entries:
            messagebox.showinfo("Export CSV", "The active tab has no words to export.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv",
            initialfile=f"{self.current_tab}_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            write_word_table(path, entries, self.translations)
        except OSError as error:
            messagebox.showerror("Export CSV", f"Failed to save the file:\n{error}", parent=self)
            return
        self.status_var.set(f"Exported {len(entries)} words to {path}.")

    def toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.palette = DARK if self.theme_name == "dark" else LIGHT
        self._rebuild_ui()

    def _update_theme_button(self):
        self.theme_button.configure(text="Use light theme" if self.theme_name == "dark" else "Use dark theme")

    def _rebuild_ui(self):
        geometry = self.geometry()
        content = self.text.get("1.0", "end-1c")
        yview = self.text.yview()
        dirty = self._source_dirty
        for child in list(self.winfo_children()):
            child.destroy()
        self._setup_style()
        self._build_ui()
        self.geometry(geometry)
        self._set_text(content)
        self._source_dirty = dirty
        self._update_source_stats()
        self.text.yview_moveto(yview[0])
        self._refresh()
        self.update_idletasks()
        set_titlebar_color(self, self.palette["card"], dark=self.theme_name == "dark")

    def _zoom_by(self, direction):
        self._set_scale(round(self.scale + direction * 0.1, 2))
        return "break"

    def _zoom_reset(self):
        self._set_scale(1.0)
        return "break"

    def _set_scale(self, value):
        value = max(0.5, min(3.0, value))
        if abs(value - self.scale) < 0.001:
            return
        self.scale = value
        self._rebuild_ui()

    def _update_zoom_label(self):
        self.zoom_var.set(f"Zoom {round(self.scale * 100)}%")

    def _on_ctrl_wheel(self, event):
        return self._zoom_by(1 if event.delta > 0 else -1)

    def _save_state(self):
        state = {
            "geometry": self.geometry(),
            "text": self.text.get("1.0", "end-1c"),
            "dictionary": self.library.counts,
            "learned": sorted(self.library.learned),
            "current_tab": self.current_tab,
            "theme": self.theme_name,
            "scale": self.scale,
            "source_path": self.source_path,
        }
        try:
            save_state(state)
        except OSError as error:
            messagebox.showwarning(
                "Session", f'Failed to save "{STATE_FILE}":\n{error}', parent=self
            )

    def _on_close(self):
        self._save_state()
        self.destroy()
