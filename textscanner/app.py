import csv
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from .documents import FILE_TYPES, WORD_CHAR_RE, extract_text_from_file
from .library import WordLibrary
from .localization import tr
from .storage import (
    STATE_FILE,
    load_state,
    make_session_state,
    normalize_state,
    read_word_table,
    save_state,
    write_word_table,
)
from .theme import DARK, LIGHT
from .translations import TranslationManager
from .windowing import set_titlebar_color

from .waiting_window import WaitingWindow 


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Text Scanner")
        self.minsize(960, 600)

        self._state = normalize_state(load_state())
        self.library = WordLibrary(
            self._state["dictionary"], self._state["learned"]
        )
        self.translator = TranslationManager(self._state["translation_dictionary"])
        self.theme_name = self._state["theme"]
        self.palette = DARK if self.theme_name == "dark" else LIGHT
        self.scale = self._state["scale"]
        self.current_tab = self._state["current_tab"]
        self.source_path = self._state["source_path"]
        self.language = self._state["language"]
        self.selected = set()
        self.rows_data = []
        self.sort_column = "count"
        self.sort_reverse = True
        self.last_click_word = None
        self.last_occurrence = 0
        self._source_dirty = False

        self.dictionary_var = tk.StringVar(
            value=self._dictionary_label(self.translator.dictionary_name)
        )
        self.query_var = tk.StringVar()
        self.stats_var = tk.StringVar()
        self.source_stats_var = tk.StringVar()
        self.document_var = tk.StringVar()
        self.selection_var = tk.StringVar(value=self._tr("No words selected"))
        self.status_var = tk.StringVar(
            value=self._tr("Open a document or paste text to begin.")
        )
        self.zoom_var = tk.StringVar()
        self.title(self._tr("Text Scanner"))

        self._setup_style()
        self._build_ui()
        self.query_var.trace_add("write", self._on_query_changed)
        self._bind_shortcuts()
        self._restore_state()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._show_startup_warning, self.translator.error)

    def _tr(self, text, **values):
        return tr(self.language, text, **values)

    def _dictionary_label(self, dictionary_name):
        label = next(
            (label for name, label in self.translator.dictionaries if name == dictionary_name),
            "",
        )
        source, separator, target = dictionary_name.partition("-")
        if separator and label:
            source_label, _, target_label = label.partition(" → ")
            return f"{self._tr(source_label)} → {self._tr(target_label)}"
        return label

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
            font=("Segoe UI Semibold", self._px(16)),
        )
        style.configure(
            "Section.TLabel", background=palette["card"], foreground=palette["text"],
            font=("Segoe UI Semibold", self._px(11)),
        )
        style.configure(
            "TButton", padding=(self._px(9), self._px(5)), relief="flat",
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
            "Tab.TButton", padding=(self._px(10), self._px(5)),
            background=palette["heading"], foreground=palette["muted"],
        )
        style.configure(
            "TabActive.TButton", padding=(self._px(10), self._px(5)),
            background=palette["accent_soft"], foreground=palette["accent"],
            font=("Segoe UI Semibold", self._px(10)),
        )
        style.configure(
            "TEntry", fieldbackground=palette["input"], foreground=palette["text"],
            bordercolor=palette["border"], lightcolor=palette["border"],
            darkcolor=palette["border"], padding=(self._px(7), self._px(5)),
        )
        style.map("TEntry", bordercolor=[("focus", palette["accent"])])
        style.configure(
            "TCombobox", fieldbackground=palette["input"], foreground=palette["text"],
            background=palette["heading"], arrowcolor=palette["muted"],
            bordercolor=palette["border"], lightcolor=palette["border"],
            darkcolor=palette["border"], padding=(self._px(7), self._px(5)),
        )
        style.map(
            "TCombobox", fieldbackground=[("readonly", palette["input"])],
            foreground=[("readonly", palette["text"])],
            bordercolor=[("focus", palette["accent"])],
        )
        style.configure(
            "Treeview", background=palette["card"], fieldbackground=palette["card"],
            foreground=palette["text"], rowheight=self._px(30), borderwidth=0,
            font=("Segoe UI", self._px(10)),
        )
        style.configure(
            "Treeview.Heading", background=palette["heading"], foreground=palette["muted"],
            relief="flat", font=("Segoe UI Semibold", self._px(9)),
            padding=(self._px(8), self._px(6)),
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
        self.paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, bg=self.palette["bg"], sashwidth=self._px(5),
            sashrelief=tk.FLAT, bd=0, opaqueresize=True,
        )
        self.paned.pack(
            fill=tk.BOTH, expand=True, padx=self._px(12), pady=(0, self._px(6))
        )
        self._build_source_panel()
        self._build_vocabulary_panel()

        self._update_theme_button()
        self._update_language_button()
        self._update_zoom_label()

    def _build_source_panel(self):
        left = ttk.Frame(self.paned, style="Card.TFrame")
        self.paned.add(left, minsize=self._px(300), stretch="always")

        heading = ttk.Frame(
            left, style="Card.TFrame", padding=(self._px(8), self._px(8), self._px(8), 0)
        )
        heading.pack(fill=tk.X)
        ttk.Button(
            heading, text=self._tr("Open document"), style="Primary.TButton",
            command=self.open_document,
        ).pack(side=tk.LEFT)
        ttk.Button(
            heading, text=self._tr("New workspace"), command=self.new_workspace
        ).pack(side=tk.LEFT, padx=(self._px(6), 0))

        self.theme_button = ttk.Button(heading, command=self.toggle_theme)
        self.theme_button.pack(side=tk.RIGHT)
        self.language_button = ttk.Button(
            heading, command=self.toggle_language, width=3
        )
        self.language_button.pack(side=tk.RIGHT, padx=(0, self._px(6)))

        self.dictionary_combo = ttk.Combobox(
            heading, textvariable=self.dictionary_var,
            values=[
                self._dictionary_label(name)
                for name, _label in self.translator.dictionaries
            ],
            state="readonly" if self.translator.dictionaries else "disabled",
        )
        self.dictionary_combo.pack(side=tk.RIGHT, expand=True)
        self.dictionary_combo.bind("<<ComboboxSelected>>", self._on_dictionary_changed)

        ttk.Label(left, textvariable=self.status_var, style="Muted.TLabel").pack(
            anchor="center", pady=(self._px(4), 0)
        )

        text_frame = ttk.Frame(
            left, style="Card.TFrame", padding=(self._px(8), 0, self._px(8), 0)
        )
        text_frame.pack(fill=tk.BOTH, expand=True)
        self.text = tk.Text(
            text_frame, wrap=tk.WORD, undo=True, relief="flat", bd=0,
            padx=self._px(8), pady=self._px(8), font=("Consolas", self._px(10)),
            bg=self.palette["input"], fg=self.palette["text"],
            insertbackground=self.palette["text"], selectbackground=self.palette["accent_soft2"],
            selectforeground=self.palette["text"], spacing1=self._px(1), spacing3=self._px(1),
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
            left, style="Card.TFrame", padding=(self._px(10), self._px(6))
        )
        source_footer.pack(fill=tk.X)
        ttk.Label(source_footer, textvariable=self.source_stats_var, style="Muted.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Button(
            source_footer, text=self._tr("Rescan text  (F5)"), command=self.rescan_text
        ).pack(side=tk.RIGHT)
        ttk.Button(
            source_footer, text=self._tr("Info"), command=self._show_app_info
        ).pack(side=tk.RIGHT, padx=(0, self._px(6)))

    def _build_vocabulary_panel(self):
        right = ttk.Frame(self.paned, style="Card.TFrame")
        self.paned.add(right, minsize=self._px(430), stretch="always")

        controls = ttk.Frame(
            right, style="Card.TFrame", padding=(self._px(8), self._px(8), self._px(8), 0)
        )
        controls.pack(fill=tk.X)
        self.tab_buttons = {}
        for key, label in (("all", "To learn"), ("learned", "Learned")):
            button = ttk.Button(
                controls, text=self._tr(label), style="Tab.TButton",
                command=lambda tab=key: self.switch_tab(tab),
            )
            button.pack(side=tk.LEFT, padx=(0, self._px(4)))
            self.tab_buttons[key] = button


        self.search_entry = ttk.Entry(controls, textvariable=self.query_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.insert(0, "")
        ttk.Button(controls, text="x", width=2, command=self.clear_search).pack(
            side=tk.LEFT, padx=(self._px(4), self._px(6))
        )

        ttk.Button(
            controls, text=self._tr("Export table"), command=self.save_csv
        ).pack(side=tk.RIGHT)
        ttk.Button(
            controls, text=self._tr("Import table"), command=self.load_csv
        ).pack(side=tk.RIGHT, padx=(0, self._px(6)))

        ttk.Label(right, textvariable=self.stats_var, style="Muted.TLabel").pack(
            anchor="center", pady=(self._px(4), 0)
        )

        table_frame = ttk.Frame(
            right, style="Card.TFrame", padding=(self._px(8), 0, self._px(8), 0)
        )
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("word", "count", "translation", "actions")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="extended", height=5
        )
        self._columns = (
            ("word", 180, self._tr("Word"), "w"),
            ("count", 95, self._tr("Count"), "center"),
            ("translation", 240, self._tr("Translation"), "w"),
            ("actions", 125, self._tr("Action"), "center"),
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
            right, style="Card.TFrame", padding=(self._px(10), self._px(6))
        )
        selection_bar.pack(fill=tk.X)
        actions = ttk.Frame(selection_bar, style="Card.TFrame")
        actions.pack(fill=tk.X)

        self.learn_button = ttk.Button(
            actions, text=self._tr("Mark learned"), command=self.learn_selected
        )
        self.learn_button.pack(side=tk.LEFT)

        self.return_button = ttk.Button(
            actions, text=self._tr("Move to learn"), command=self.unlearn_selected
        )
        self.remove_button = ttk.Button(
            actions, text=self._tr("Remove"), style="Danger.TButton",
            command=self.remove_selected,
        )
        self.remove_button.pack(side=tk.RIGHT)
        self.clear_button = ttk.Button(
            actions, text=self._tr("Clear selection"), command=self.clear_selection
        )
        self.clear_button.pack(side=tk.RIGHT)

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
                self._tr("Translation dictionary"),
                self._tr(
                    "Failed to load \"{name}\":\n{error}\n\nTranslations will be empty.",
                    name=self.translator.dictionary_name, error=error,
                ),
                parent=self,
            )

    def _on_dictionary_changed(self, event=None):
        selected_label = self.dictionary_var.get()
        dictionary_name = next(
            (
                name for name, _label in self.translator.dictionaries
                if self._dictionary_label(name) == selected_label
            ),
            "",
        )
        if not dictionary_name or dictionary_name == self.translator.dictionary_name:
            return
        error = self.translator.switch(dictionary_name)
        if error:
            self.dictionary_var.set(
                self._dictionary_label(self.translator.dictionary_name)
            )
            messagebox.showwarning(
                self._tr("Translation dictionary"),
                self._tr(
                    "Failed to load \"{name}\":\n{error}\n\nThe previous dictionary is still active.",
                    name=dictionary_name, error=error,
                ),
                parent=self,
            )
            return
        self.selected.clear()
        self._refresh()
        self.status_var.set(self._tr(
            "Using {dictionary}: {count} entries.",
            dictionary=self.dictionary_var.get(),
            count=len(self.translator.full_translations),
        ))

    def _restore_state(self):
        try:
            self.geometry(self._state["geometry"])
        except tk.TclError:
            self.geometry("1280x760")
        self._set_text(self._state["text"])

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
        suffix = self._tr(" · unsaved scan changes") if self._source_dirty else ""
        if self.source_path:
            name = os.path.basename(self.source_path)
        elif content:
            name = self._tr("Pasted or edited text")
        else:
            name = self._tr("No document loaded")
        self.document_var.set(name)
        self.source_stats_var.set(self._tr(
            "{name} · {lines} lines · {characters} characters{suffix}",
            name=name, lines=lines, characters=len(content), suffix=suffix,
        ))

    def _refresh(self):
        self._hide_translation_hover()
        translations = self.translator.update(self.library.counts)
        self._update_tab_labels()
        self._update_sort_headings()
        entries = self.library.entries(
            self.current_tab, self.query_var.get(), translations,
            self.sort_column, self.sort_reverse,
        )
        visible_words = {word for word, _ in entries}
        self.selected.intersection_update(visible_words)
        self.tree.delete(*self.tree.get_children())
        self.rows_data = entries
        selected_ids = []
        for index, (word, count) in enumerate(entries):
            translation = translations.get(word, "")
            action = self._tr(
                "Move to learn" if self.current_tab == "learned" else "Mark learned"
            )
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
        labels = {
            "all": f"{self._tr('To learn')}  {to_learn}",
            "learned": f"{self._tr('Learned')}  {len(self.library.learned)}",
        }
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
        totals = self.library.totals(
            self.current_tab, self.query_var.get(), self.translator.translations
        )
        if not self.library.counts:
            self.stats_var.set(self._tr("Your word list is empty"))
            return
        translated = sum(
            bool(self.translator.translations.get(word)) for word, _count in self.rows_data
        )
        text = self._tr(
            "{occurrences} occurrences · {translated} translated",
            occurrences=totals["visible_occurrences"], translated=translated,
        )
        if self.query_var.get().strip():
            text += self._tr(" · of {total} total", total=totals["total_words"])
        self.stats_var.set(text)

    def _update_selection_ui(self):
        count = len(self.selected)
        self.selection_var.set(
            self._tr("No words selected") if not count
            else self._tr("{count} selected", count=count)
        )
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
        self._drag_start_item = None
        self._dragging = False
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
            self.status_var.set(self._tr("Updated '{word}'.", word=word))
            return "break"
        if item:
            self._drag_start_item = item

    def _on_tree_drag(self, event):
        start_item = getattr(self, "_drag_start_item", None)
        item = self.tree.identify_row(event.y)
        if not start_item or not item:
            return
        rows = self.tree.get_children()
        start = self.tree.index(start_item)
        end = self.tree.index(item)
        first, last = sorted((start, end))
        self.tree.selection_set(rows[first:last + 1])
        self.tree.focus(item)
        self._dragging = True
        self._on_tree_select()
        return "break"

    def _on_tree_release(self, event):
        was_dragging = getattr(self, "_dragging", False)
        self._drag_start_item = None
        self._dragging = False
        if was_dragging:
            return "break"
        if event.state & 0x0005 or self.tree.identify_region(event.x, event.y) != "cell":
            return
        item = self.tree.identify_row(event.y)
        if not item or self.tree.identify_column(event.x) == "#4":
            return
        if self.tree.identify_column(event.x) == "#3":
            return self._on_translation_click(event)
        word = self._row_word(item)
        if word == self.last_click_word:
            self.last_occurrence += 1
        else:
            self.last_occurrence = 0
            self.last_click_word = word
        self._jump_to_word(word, self.last_occurrence)

    def _on_translation_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#3":
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        word = self._row_word(item)
        matched_word, definition = self.translator.entry(word)
        if definition:
            self._show_translation(word, matched_word, definition)
            return "break"

    def _show_translation(self, word, matched_word, definition):
        window = tk.Toplevel(self)
        title = word if word == matched_word else f"{word} → {matched_word}"
        window.title(self._tr("Translation: {title}", title=title))
        window.transient(self)
        window.configure(bg=self.palette["bg"])
        window.minsize(self._px(360), self._px(240))
        window.geometry(f"{self._px(640)}x{self._px(480)}")

        frame = ttk.Frame(window, padding=self._px(12))
        frame.pack(fill=tk.BOTH, expand=True)
        text = tk.Text(
            frame, wrap=tk.WORD, relief="flat", bd=0,
            padx=self._px(10), pady=self._px(10), font=("Segoe UI", self._px(11)),
            bg=self.palette["input"], fg=self.palette["text"],
            selectbackground=self.palette["accent_soft2"],
            selectforeground=self.palette["text"], spacing1=self._px(2),
            spacing3=self._px(2), highlightthickness=1,
            highlightbackground=self.palette["border"], highlightcolor=self.palette["accent"],
        )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.insert("1.0", definition)
        text.configure(state="disabled")

        footer = ttk.Frame(window, padding=(self._px(12), 0, self._px(12), self._px(12)))
        footer.pack(fill=tk.X)
        close_button = ttk.Button(
            footer, text=self._tr("Close"), command=window.destroy
        )
        close_button.pack(side=tk.RIGHT)

        def close_on_outside_click(event):
            try:
                if not window.winfo_exists():
                    return
                widget = event.widget
                while widget is not None:
                    if widget == window:
                        return
                    widget = getattr(widget, "master", None)
                window.destroy()
            except tk.TclError:
                pass

        def remove_outside_binding(event):
            if event.widget == window:
                window.unbind_all("<ButtonPress-1>")

        window.bind_all("<ButtonPress-1>", close_on_outside_click, add="+")
        window.bind("<Destroy>", remove_outside_binding)
        window.bind("<Escape>", lambda event: window.destroy())
        window.lift()
        window.focus_force()
        text.focus_set()
        set_titlebar_color(window, self.palette["card"], dark=self.theme_name == "dark")

    def _show_app_info(self):
        window = tk.Toplevel(self)
        window.title(self._tr("Info"))
        window.transient(self)
        window.configure(bg=self.palette["bg"])
        window.minsize(self._px(380), self._px(320))
        window.geometry(f"{self._px(560)}x{self._px(660)}")

        frame = ttk.Frame(window, padding=self._px(12))
        frame.pack(fill=tk.BOTH, expand=True)
        text = tk.Text(
            frame, wrap=tk.WORD, relief="flat", bd=0,
            padx=self._px(10), pady=self._px(10), font=("Segoe UI", self._px(10)),
            bg=self.palette["input"], fg=self.palette["text"],
            selectbackground=self.palette["accent_soft2"],
            selectforeground=self.palette["text"], spacing1=self._px(2),
            spacing3=self._px(2), highlightthickness=1,
            highlightbackground=self.palette["border"], highlightcolor=self.palette["accent"],
        )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        sections = (
            ("About Text Scanner (https://github.com/valadyan/entextLocal)", "Text Scanner creates a frequency-sorted vocabulary from documents or pasted text. You can edit the source, track learned words, view translations, and import or export CSV tables."),
            ("How to use", "1. Open a document or paste text into the source editor.\n2. Press Rescan text or F5 after editing.\n3. Click a word to find its occurrences; click a translation for the full entry.\n4. Select words to mark them learned, return them to the learning list, or remove them."),
            ("Shortcuts", "Ctrl+O — open document\nCtrl+S — export CSV\nCtrl+N — new workspace\nCtrl+F — filter words\nF5 — rescan text\nCtrl+A — select all visible words\nDelete — remove selected words\nEscape — clear filter or selection\nCtrl + / - / 0 — zoom in, out, or reset"),
        )
        content = "\n\n".join(
            f"{self._tr(heading)}\n{self._tr(body)}" for heading, body in sections
        )
        text.insert("1.0", content)
        text.configure(state="disabled")

        footer = ttk.Frame(window, padding=(self._px(12), 0, self._px(12), self._px(12)))
        footer.pack(fill=tk.X)
        ttk.Button(
            footer, text=self._tr("Close"), command=window.destroy
        ).pack(side=tk.RIGHT)
        window.bind("<Escape>", lambda event: window.destroy())
        text.focus_set()
        set_titlebar_color(window, self.palette["card"], dark=self.theme_name == "dark")

    def _on_tree_motion(self, event):
        if event.state & 0x0100:
            result = self._on_tree_drag(event)
            if result:
                return result
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        is_clickable = bool(item) and column in ("#3", "#4")
        self.tree.configure(cursor="hand2" if is_clickable else "")
        hovered = (
            item if item and column == "#3"
            and self.tree.set(item, "translation") != "—" else None
        )
        self._update_translation_hover(hovered)

    def _update_translation_hover(self, item):
        if not item:
            self._hide_translation_hover()
            return
        bounds = self.tree.bbox(item, "#3")
        if not bounds:
            self._hide_translation_hover()
            return
        label = getattr(self, "_translation_hover_label", None)
        if label is None or not label.winfo_exists():
            label = tk.Label(self.tree, padx=0, pady=0, anchor="w", cursor="hand2")
            self._translation_hover_label = label
            bindings = (
                ("<ButtonPress-1>", self._on_tree_press),
                ("<ButtonRelease-1>", self._on_tree_release),
                ("<B1-Motion>", self._on_tree_motion),
                ("<Motion>", self._on_tree_motion),
            )
            for sequence, handler in bindings:
                label.bind(
                    sequence,
                    lambda event, callback=handler:
                        self._forward_translation_hover_event(event, callback),
                )
        tags = self.tree.item(item, "tags")
        if item in self.tree.selection():
            background = self.palette["selection"]
        else:
            background = self.palette["zebra"] if "odd" in tags else self.palette["row"]
        label.configure(
            text=self.tree.set(item, "translation"), background=background,
            foreground=self.palette["accent"],
            font=("Segoe UI", self._px(10), "underline"),
        )
        x, y, _width, height = bounds
        label.place(x=x + 4, y=y, height=height)
        self._hovered_translation = item

    def _hide_translation_hover(self):
        label = getattr(self, "_translation_hover_label", None)
        if label is not None:
            try:
                if label.winfo_exists():
                    label.place_forget()
                else:
                    self._translation_hover_label = None
            except tk.TclError:
                self._translation_hover_label = None
        self._hovered_translation = None

    def _forward_translation_hover_event(self, event, callback):
        label = self._translation_hover_label
        event.x += label.winfo_x()
        event.y += label.winfo_y()
        return callback(event)

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
            self.status_var.set(self._tr(
                "'{word}' is not present in the current source text.", word=word
            ))
            return
        for start, end in positions:
            self.text.tag_add("highlight", start, end)
        start, end = positions[occurrence % len(positions)]
        self.text.tag_add("current", start, end)
        self.text.see(start)
        self.status_var.set(self._tr(
            "'{word}': occurrence {occurrence} of {total}",
            word=word, occurrence=occurrence % len(positions) + 1, total=len(positions),
        ))

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
        self.status_var.set(self._tr(
            "Marked {count} words as learned.", count=len(words)
        ))

    def unlearn_selected(self):
        words = set(self.selected)
        self.library.mark_unlearned(words)
        self.selected.clear()
        self._refresh()
        self.status_var.set(self._tr(
            "Moved {count} words back to the learning list.", count=len(words)
        ))

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
            self._tr("Remove words"),
            self._tr("Remove {count} words from this workspace?", count=len(words)),
            parent=self,
        ):
            return "break"
        self.library.remove(words)
        self.selected.clear()
        self._refresh()
        self.status_var.set(self._tr("Removed {count} words.", count=len(words)))
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
            self._tr("Replace workspace"),
            self._tr(
                "Replace the current text and word counts? Your previous session is saved only when the app closes."
            ),
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
        self.status_var.set(self._tr("New workspace ready."))
            
    def open_document(self):
        if not self._confirm_discard():
            return
        
        file_types = [(self._tr(label), patterns) for label, patterns in FILE_TYPES]
        path = filedialog.askopenfilename(parent=self, filetypes=file_types)
        if not path:
            return

        # --- Loading window ---------------------------------------------------

        waiting = WaitingWindow(
            self,
            title="Processing",
            message=self._tr("Loading {name}...", name=os.path.basename(path)),
            # gif_path="anim2.gif"   # <-- path to your GIF 
        )

        result = {"text": None, "error": None}
        def worker():
            try:
                result["text"] = extract_text_from_file(path, self.language)
            except BaseException as exc:  # capture everything for the UI thread
                result["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        # Pump the event loop until the worker finishes so the loading window animates.
        while thread.is_alive():
            self.update()
            time.sleep(0.02)
        # ----------------------------------------------------------------------

        if result["error"] is not None:
            error = result["error"]
            if isinstance(error, (ValueError, OSError)):
                messagebox.showerror(self._tr("Open document"), str(error), parent=self)
            else:
                messagebox.showerror(
                    self._tr("Open document"),
                    self._tr("The document could not be parsed:\n{error}", error=error),
                    parent=self,
                )
            waiting.close()
            return

        waiting.update_message(self._tr("Preparing dictionary"))

        text = result["text"]
        if not text.strip():
            messagebox.showwarning(
                self._tr("Open document"),
                self._tr(
                    "No text could be extracted from {name}.\n\nIf this is a scanned PDF, OCR is required first.",
                    name=os.path.basename(path),
                ),
                parent=self,
            )
            waiting.close()
            return

        self.library.clear()
        unique_count = self.library.replace_text(text)
        if not unique_count:
            messagebox.showwarning(
                self._tr("Scan document"), self._tr("No words found in the text."), parent=self
            )
            waiting.close()
            return
        self.source_path = path
        self.current_tab = "all"
        self.selected.clear()
        self.query_var.set("")
        self._set_text(text)
        self._refresh()
        self.status_var.set(self._tr(
            "Loaded {name}: {unique} unique words, {occurrences} occurrences.",
            name=os.path.basename(path), unique=unique_count,
            occurrences=sum(self.library.counts.values()),
        ))
        waiting.close()

    def rescan_text(self):
        text = self.text.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo(
                self._tr("Rescan text"), self._tr("Paste or open some text first."), parent=self
            )
            return
        count = self.library.replace_text(text)
        if not count:
            messagebox.showwarning(
                self._tr("Rescan text"), self._tr("No words found in the text."), parent=self
            )
            return
        self.selected.clear()
        self._source_dirty = False
        self.text.edit_modified(False)
        self._update_source_stats()
        self._refresh()
        self.status_var.set(self._tr("Scan complete: {count} unique words.", count=count))

    def load_csv(self):
        file_types = [
            (self._tr("CSV files"), "*.csv"), (self._tr("All files"), "*.*")
        ]
        path = filedialog.askopenfilename(parent=self, filetypes=file_types)
        if not path:
            return
        try:
            counts = read_word_table(path)
        except (OSError, csv.Error) as error:
            messagebox.showerror(
                self._tr("Import CSV"),
                self._tr("Failed to load the CSV file:\n{error}", error=error),
                parent=self,
            )
            return
        self.library.merge_counts(counts, learned=self.current_tab == "learned")
        self._refresh()
        self.status_var.set(self._tr(
            "Imported {count} words into the active tab.", count=len(counts)
        ))

    def save_csv(self):
        entries = self.library.tab_entries(self.current_tab, self.translator.translations)
        if not entries:
            messagebox.showinfo(
                self._tr("Export CSV"),
                self._tr("The active tab has no words to export."),
                parent=self,
            )
            return
        file_types = [
            (self._tr("CSV files"), "*.csv"), (self._tr("All files"), "*.*")
        ]
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv",
            initialfile=f"{self.current_tab}_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv",
            filetypes=file_types,
        )
        if not path:
            return
        try:
            write_word_table(path, entries, self.translator.translations)
        except OSError as error:
            messagebox.showerror(
                self._tr("Export CSV"),
                self._tr("Failed to save the file:\n{error}", error=error),
                parent=self,
            )
            return
        self.status_var.set(self._tr(
            "Exported {count} words to {path}.", count=len(entries), path=path
        ))

    def toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.palette = DARK if self.theme_name == "dark" else LIGHT
        self._rebuild_ui()

    def _update_theme_button(self):
        self.theme_button.configure(text=self._tr(
            "Use light theme" if self.theme_name == "dark" else "Use dark theme"
        ))

    def toggle_language(self):
        self.language = "ru" if self.language == "en" else "en"
        self.dictionary_var.set(
            self._dictionary_label(self.translator.dictionary_name)
        )
        self.status_var.set(self._tr("Open a document or paste text to begin."))
        self._rebuild_ui()

    def _update_language_button(self):
        self.language_button.configure(text="EN" if self.language == "ru" else "RU")

    def _rebuild_ui(self):
        geometry = self.geometry()
        content = self.text.get("1.0", "end-1c")
        yview = self.text.yview()
        dirty = self._source_dirty
        for child in list(self.winfo_children()):
            child.destroy()
        self.title(self._tr("Text Scanner"))
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
        self.zoom_var.set(self._tr("Zoom {percent}%", percent=round(self.scale * 100)))

    def _on_ctrl_wheel(self, event):
        return self._zoom_by(1 if event.delta > 0 else -1)

    def _save_state(self):
        state = make_session_state(
            geometry=self.geometry(),
            text=self.text.get("1.0", "end-1c"),
            counts=self.library.counts,
            learned=self.library.learned,
            current_tab=self.current_tab,
            theme_name=self.theme_name,
            scale=self.scale,
            source_path=self.source_path,
            translation_dictionary=self.translator.dictionary_name,
            language=self.language,
        )
        try:
            save_state(state)
        except OSError as error:
            messagebox.showwarning(
                self._tr("Session"),
                self._tr("Failed to save \"{path}\":\n{error}", path=STATE_FILE, error=error),
                parent=self,
            )

    def _on_close(self):
        self._save_state()
        self.destroy()
