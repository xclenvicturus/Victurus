from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict

CATEGORIES = ["all", "system", "dialogue", "combat", "trade", "loot", "faction"]

class LogPanel(ttk.Notebook):
    def __init__(self, parent):
        super().__init__(parent)
        self.text_widgets: Dict[str, tk.Text] = {}
        self._tab_label: Dict[str, str] = {}
        self._highlight_pref: Dict[str, bool] = {cat: True for cat in CATEGORIES}
        self._highlight_active: Dict[str, bool] = {cat: False for cat in CATEGORIES}

        for cat in CATEGORIES:
            frame = ttk.Frame(self)
            text = tk.Text(frame, wrap="word", state="disabled")
            text.pack(fill="both", expand=True)
            label = cat.capitalize()
            super().add(frame, text=label)
            self._tab_label[cat] = label
            self.text_widgets[cat] = text

        self.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.bind("<Button-3>", self._on_tab_right_click)

    def append(self, category: str, message: str):
        cat = category if category in self.text_widgets else "system"
        self._append_to("all", message)
        if cat != "all":
            self._append_to(cat, message)
        self._maybe_highlight(cat)
        if cat != "all":
            self._maybe_highlight("all")

    def copy_all(self) -> str:
        parts = []
        for cat, t in self.text_widgets.items():
            content = t.get("1.0", "end-1c").strip()
            if content:
                parts.append(f"[{cat}]\n{content}")
        return "\n\n".join(parts)

    def focus_tab(self, category: str):
        cat = category if category in self.text_widgets else "system"
        idx = CATEGORIES.index(cat)
        self.select(idx)

    # ---- internals ----
    def _append_to(self, cat: str, message: str):
        t = self.text_widgets[cat]
        t.config(state="normal")
        t.insert("end", message + "\n")
        t.see("end")
        t.config(state="disabled")

    def _on_tab_changed(self, _evt=None):
        current = CATEGORIES[self.index(self.select())]
        if self._highlight_active.get(current):
            self._highlight_active[current] = False
            self.tab(self.index(self.select()), text=self._tab_label[current])

    def _maybe_highlight(self, cat: str):
        if not self._highlight_pref.get(cat, True):
            return
        current = CATEGORIES[self.index(self.select())]
        if current == cat:
            return
        if not self._highlight_active.get(cat):
            self._highlight_active[cat] = True
            self._set_tab_label_marked(cat, True)

    def _set_tab_label_marked(self, cat: str, marked: bool):
        label = self._tab_label.get(cat, cat.capitalize())
        text = f"● {label}" if marked else label
        try:
            self.tab(CATEGORIES.index(cat), text=text)
        except Exception:
            pass

    def _on_tab_right_click(self, event):
        tab_id = self.index(f"@{event.x},{event.y}") if self.identify(event.x, event.y).startswith("label") else None
        if tab_id is None:
            return
        cat = CATEGORIES[tab_id]
        menu = tk.Menu(self, tearoff=0)
        current = self._highlight_pref.get(cat, True)
        dot = "🟢" if current else "🔴"  # (14) show state
        menu.add_command(
            label=f"{dot} Highlight new messages",
            command=lambda: self._toggle_highlight(cat)
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _toggle_highlight(self, cat: str):
        self._highlight_pref[cat] = not self._highlight_pref.get(cat, True)
        if not self._highlight_pref[cat] and self._highlight_active.get(cat):
            self._highlight_active[cat] = False
            self._set_tab_label_marked(cat, False)
