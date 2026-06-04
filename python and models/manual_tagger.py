import os, tkinter as tk, csv, argparse, re, threading, configparser
from pathlib import Path
from PIL import Image, ImageTk
from tkinter import messagebox, Toplevel, simpledialog
import requests
from xml.etree import ElementTree as ET
import urllib
from urllib.parse import quote
import urllib.parse

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR  # python and models/

Image.MAX_IMAGE_PIXELS = 300000000

# Booru Category Order & Colors
CAT_ORDER = ["3", "4", "1", "0", "5"]
TAG_COLORS = {
    "0": "#00afff", # General
    "1": "#ee8887", # Character
    "3": "#dd00dd", # Metadata
    "4": "#00aa00", # Copyright
    "5": "#ff8800", # Artist
}

def load_dict(p):
    d = {}
    if not os.path.exists(p): return d
    with open(p, 'r', encoding='utf-8') as f:
        r = csv.reader(f)
        for row in r:
            if len(row) >= 2:
                name = row[0].replace(" ", "_").lower()
                d[name] = {"type": row[1].strip(), "count": row[2].strip() if len(row)>2 else "0"}
    return d


def add_placeholder(entry, placeholder_text):
    """Add a dim placeholder/watermark to an Entry widget."""
    entry._placeholder = placeholder_text
    entry._has_placeholder = True
    entry.insert(0, placeholder_text)
    entry.config(foreground='#555')

    def _on_focusin(e):
        if entry._has_placeholder:
            entry.delete(0, 'end')
            entry.config(foreground='#fff')
            entry._has_placeholder = False

    def _on_focusout(e):
        if not entry.get() and not entry._has_placeholder:
            entry.insert(0, placeholder_text)
            entry.config(foreground='#555')
            entry._has_placeholder = True

    entry.bind('<FocusIn>', _on_focusin)
    entry.bind('<FocusOut>', _on_focusout)

class App:
    def __init__(self, root, imgs, in_d, out_d, dic, preset_file, lora_mode=False):
        # ALL assignments must happen before you try to use self.root
        self.root = root
        self.imgs = imgs
        self.in_d = in_d
        self.out_d = out_d
        self.dic = dic
        self.preset_file = preset_file
        self.lora_mode = lora_mode
        self.idx = 0
        self.lora_mode = lora_mode # Store this
        # ... rest of your init remains the same

        self.preset_file = preset_file
        self.root.configure(bg='#0a0a0a')
        self.root.state('zoomed')
        
        self.tags_internal = []
        self.original_tags = [] 
        self.history = [] 
        self.stable_tags = set()
        self.sidebar_items = self.load_presets()

        self.main_f = tk.Frame(root, bg='#0a0a0a')
        self.main_f.pack(fill='both', expand=True, padx=10, pady=10)
        
        # --- SIDEBAR ---
        self.pre_col = tk.Frame(self.main_f, bg='#0a0a0a', width=280, highlightbackground="#333", highlightthickness=1)
        self.pre_col.pack(side='left', fill='y', padx=(0,10))
        self.pre_col.pack_propagate(False)
        
        tk.Label(self.pre_col, text="PRESETS", bg='#1a1a1a', fg='#fff', font=('Arial', 9, 'bold')).pack(fill='x')
        
        btn_frame = tk.Frame(self.pre_col, bg='#0a0a0a')
        btn_frame.pack(fill='x', pady=(5, 2))
        tk.Button(btn_frame, text="+ HEADER", command=self.add_header_gui, bg='#222', fg='#ffcc00', relief='flat', bd=0, font=('Arial', 8, 'bold')).pack(side='left', fill='x', expand=True, padx=(0, 1))
        tk.Button(btn_frame, text="+ PRESET", command=self.add_preset_gui, bg='#222', fg='#00ff00', relief='flat', bd=0, font=('Arial', 8, 'bold')).pack(side='left', fill='x', expand=True, padx=(1, 0))
        
        # Search box
        self.pre_search_var = tk.StringVar()
        self.pre_search_var.trace_add("write", self._on_presets_search)
        search_frame = tk.Frame(self.pre_col, bg='#0a0a0a')
        search_frame.pack(fill='x', pady=(5, 2))
        self.pre_search_entry = tk.Entry(search_frame, textvariable=self.pre_search_var, bg='#111', fg='#fff', font=('Consolas', 9), insertbackground='#fff', borderwidth=1, highlightbackground='#333', highlightthickness=1)
        self.pre_search_entry.pack(fill='x', padx=2)
        add_placeholder(self.pre_search_entry, "Search presets...")
        # Bind arrow keys to search entry so they work without clicking the results box
        self.pre_search_entry.bind('<Down>', self._on_results_down)
        self.pre_search_entry.bind('<Up>', self._on_results_up)
        self.pre_search_entry.bind('<Return>', self._on_results_enter)
        self.pre_search_entry.bind('<Escape>', lambda e: self.pre_search_var.set('') or self._on_presets_search())
        
        # Results box - Listbox for keyboard selection
        self.pre_results = tk.Listbox(self.pre_col, bg='#111', fg='#ffffff', selectbackground='#444400', selectforeground='#ffffff', font=('Consolas', 8), height=3, width=30, borderwidth=1, highlightbackground='#333', highlightthickness=1, exportselection=False)
        self.pre_results.pack(fill='x', padx=2, pady=(0, 5))
        self.pre_results.bind('<Button-1>', self._on_results_click)
        self._result_items = []  # store item data for click handler
        self._result_selection = -1  # currently selected line (-1 = none)
        self.pre_results.bind('<Escape>', lambda e: self.pre_search_var.set('') or self._on_presets_search())
        
        self.frame_to_item_idx = {}  # maps frame widget -> item index for search
        
        self.pre_canvas = tk.Canvas(self.pre_col, bg='#0a0a0a', highlightthickness=0)
        self.pre_scrollbar = tk.Scrollbar(self.pre_col, orient="vertical", command=self.pre_canvas.yview)
        self.pre_container = tk.Frame(self.pre_canvas, bg='#0a0a0a')
        
        self.pre_canvas.configure(yscrollcommand=self.pre_scrollbar.set)
        self.pre_scrollbar.pack(side="right", fill="y")
        self.pre_canvas.pack(side="left", fill="both", expand=True)
        self.pre_window = self.pre_canvas.create_window((0, 0), window=self.pre_container, anchor="nw")

        self.pre_container.bind("<Configure>", lambda e: self.pre_canvas.configure(scrollregion=self.pre_canvas.bbox("all")))
        self.pre_canvas.bind("<Configure>", lambda e: self.pre_canvas.itemconfig(self.pre_window, width=e.width))

        def _on_mousewheel(event):
            self.pre_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.pre_canvas.bind("<Enter>", lambda e: self.root.bind_all("<MouseWheel>", _on_mousewheel))
        self.pre_canvas.bind("<Leave>", lambda e: self.root.unbind_all("<MouseWheel>"))

        # --- EDITOR ---
        self.edit_col = tk.Frame(self.main_f, bg='#0a0a0a', width=500)
        self.edit_col.pack(side='left', fill='y')
        self.edit_col.pack_propagate(False)

        self.en = tk.Entry(self.edit_col, bg='#111', fg='#fff', insertbackground='#fff', font=('Consolas', 12))
        self.en.pack(fill='x', pady=(0, 5))
        add_placeholder(self.en, "Type a tag to search...")
        self.en.bind('<KeyRelease>', self.kb)
        self.en.bind('<Return>', self.ok)
        self.en.bind('<Tab>', self.ok)
        self.en.bind('<Down>', self.move_sel)
        self.en.bind('<Up>', self.move_sel)

        self.lb = tk.Listbox(self.edit_col, height=6, bg='#111', borderwidth=0, font=('Consolas', 10), selectbackground='#444', exportselection=False)
        self.lb.pack(fill='x', pady=5)
        self.lb.bind('<Double-Button-1>', self.ok)

        tk.Label(self.edit_col, text="SESSION HISTORY", bg='#0a0a0a', fg='#888', font=('Arial', 8)).pack(anchor='w')
        self.hist_tx = tk.Text(self.edit_col, height=4, bg='#0a0a0a', font=('Consolas', 10), cursor="hand2", borderwidth=1, highlightbackground='#222', wrap='word', insertbackground='#fff')
        self.hist_tx.pack(fill='x', pady=5)
        self.hist_tx.tag_config("strike", overstrike=True, foreground="#ffffff")
        self.hist_tx.bind("<Button-1>", self.click_history)

        self.tx = tk.Text(self.edit_col, bg='#050505', fg='#ccc', font=('Consolas', 12), wrap='word', borderwidth=1, padx=10, pady=10, insertbackground='#fff')
        self.tx.pack(fill='both', expand=True)
        self.tx.bind('<KeyRelease>', self.on_text_key)
        
        for code, color in TAG_COLORS.items():
            self.tx.tag_config(f"cat_{code}", foreground=color)
            self.hist_tx.tag_config(f"cat_{code}", foreground=color)
        
        self.tx.tag_config("new_tag", foreground="#ffffff")

        # Blacklist quick-add
        self.bl_frame = tk.Frame(self.edit_col, bg='#0a0a0a')
        self.bl_frame.pack(fill='x', pady=(5, 0))
        
        tk.Frame(self.bl_frame, bg='#0a0a0a').pack(side='left', expand=True)
        
        tk.Label(self.bl_frame, text="BLACKLIST:", bg='#0a0a0a', fg='#ff4444', font=('Arial', 8, 'bold')).pack(side='left', padx=(5, 3))
        self.bl_entry = tk.Entry(self.bl_frame, bg='#111', fg='#fff', font=('Consolas', 9), insertbackground='#fff', borderwidth=1, highlightbackground='#333', highlightthickness=1, width=18)
        self.bl_entry.pack(side='left', fill='x', expand=True, padx=(0, 3))
        self.bl_entry.bind('<Return>', self._add_to_blacklist)
        tk.Button(self.bl_frame, text="+", bg='#331111', fg='#ff4444', font=('Arial', 10, 'bold'), width=2, bd=0, relief='flat', command=self._add_to_blacklist).pack(side='left')
        self.bl_status = tk.Label(self.bl_frame, bg='#0a0a0a', fg='#888', font=('Consolas', 8), anchor='w')
        self.bl_status.pack(side='right', fill='x', expand=True, padx=(3, 5))
        
        tk.Frame(self.bl_frame, bg='#0a0a0a').pack(side='left', expand=True)

        nav_f = tk.Frame(self.edit_col, bg='#0a0a0a')
        nav_f.pack(fill='x', pady=10)
        
        tk.Button(nav_f, text="< BACK", command=self.prev, bg='#222', fg='#fff', width=8).pack(side='left', padx=2)
        tk.Button(nav_f, text="SAVE & NEXT", command=self.sv, bg='#1a1a1a', fg='#00ff00', font=('Arial', 9, 'bold')).pack(side='left', expand=True, fill='x', padx=2)
        tk.Button(nav_f, text="NEXT >", command=self.skip, bg='#222', fg='#fff', width=8).pack(side='left', padx=2)
        tk.Button(nav_f, text="SAVE & COPY", command=self.save_and_copy, bg='#1a1a1a', fg='#00ffff', font=('Arial', 9, 'bold'), width=14).pack(side='left', padx=2)

        self.il = tk.Label(self.main_f, bg='#050505')
        self.il.pack(side='right', fill='both', expand=True, padx=(10,0))
        
        self.ld()

    def load_presets(self):
        items = []
        if os.path.exists(self.preset_file):
            with open(self.preset_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if line.startswith("[HEADER]"):
                        # HEADER is TRUE (expanded)
                        items.append({"type": "header", "name": line[8:], "open": True})
                    elif ":" in line:
                        k, v = line.split(":", 1)
                        tags = [t.strip().replace(" ", "_").lower() for t in v.split(",") if t.strip()]
                        # PRESET is FALSE (collapsed)
                        items.append({"type": "preset", "name": k.strip(), "tags": tags, "open": False})
                        
        if items and items[0]["type"] == "preset":
            # SAFETY NET HEADER is TRUE (expanded)
            items.insert(0, {"type": "header", "name": "General", "open": True})
            
        return items

    def _on_presets_search(self, *args):
        # Guard: widgets may not exist yet during init
        if not hasattr(self, 'pre_results') or not hasattr(self, 'pre_container'):
            return
        query = self.pre_search_var.get().strip().lower()
        self.pre_results.delete(0, tk.END)
        self._result_items = []
        self._result_selection = -1
        if not query:
            return
        for frame in self.pre_container.winfo_children():
            frame.config(bg='#0a0a0a')
        for frame in self.pre_container.winfo_children():
            idx = self.frame_to_item_idx.get(frame)
            if idx is None:
                continue
            item = self.sidebar_items[idx]
            if item.get("type") != "preset":
                continue
            name = item.get("name", "")
            if query in name.lower():
                self._result_items.append(item)
                self.pre_results.insert(tk.END, name)
        if self._result_items:
            self._result_selection = 0
            self.pre_results.selection_clear(0, tk.END)
            self.pre_results.selection_set(0)
        else:
            self.pre_results.insert(0, 'No matches')
            self.pre_results.config(state='disabled')

    def _on_results_down(self, event):
        if not self._result_items:
            return 'break'
        self._result_selection = min(self._result_selection + 1, len(self._result_items) - 1)
        self.pre_results.selection_clear(0, tk.END)
        self.pre_results.selection_set(self._result_selection)
        self.pre_results.see(self._result_selection)
        return 'break'

    def _on_results_up(self, event):
        if not self._result_items:
            return 'break'
        self._result_selection = max(self._result_selection - 1, 0)
        self.pre_results.selection_clear(0, tk.END)
        self.pre_results.selection_set(self._result_selection)
        self.pre_results.see(self._result_selection)
        return 'break'

    def _on_results_enter(self, event):
        if 0 <= self._result_selection < len(self._result_items):
            item = self._result_items[self._result_selection]
            tags = item.get("tags", [])
            is_active = all(t in self.tags_internal for t in tags)
            if is_active:
                self.remove_tags(tags)
            else:
                self.add_tags(tags)
            self.pre_search_var.set('')
            self._on_presets_search()
        return 'break'

    def _on_results_click(self, event):
        # Get clicked index from active selection
        idx = self.pre_results.curselection()
        if idx:
            idx = idx[0]
            self._result_selection = idx
            item = self._result_items[idx]
            tags = item.get("tags", [])
            is_active = all(t in self.tags_internal for t in tags)
            if is_active:
                self.remove_tags(tags)
            else:
                self.add_tags(tags)
            self.pre_search_var.set('')
            self._on_presets_search()
        return 'break'

    def _on_results_click(self, event):
        """Apply preset when a search result is clicked."""
        if not self._result_items:
            return
        # Get the line and character position of the click
        line = int(self.pre_results.index('insert').split('.')[0])
        if 1 <= line <= len(self._result_items):
            item = self._result_items[line - 1]
            tags = item.get("tags", [])
            is_active = all(t in self.tags_internal for t in tags)
            if is_active:
                self.remove_tags(tags)
            else:
                self.add_tags(tags)
            self.pre_search_var.set('')  # Clear search
            self._on_presets_search()  # Refresh

    def save_presets_to_disk(self):
        if self.sidebar_items and self.sidebar_items[0]["type"] == "preset":
            self.sidebar_items.insert(0, {"type": "header", "name": "General", "open": True})
            
        with open(self.preset_file, 'w', encoding='utf-8') as f:
            for item in self.sidebar_items:
                if item["type"] == "header":
                    f.write(f"[HEADER]{item['name']}\n")
                else:
                    f.write(f"{item['name']}:{','.join(item['tags'])}\n")

    def rebuild_presets_ui(self):
        for widget in self.pre_container.winfo_children(): widget.destroy()
        
        current_header_open = True
        
        for idx, item in enumerate(self.sidebar_items):
            if item["type"] == "header":
                current_header_open = item.get("open", True)
                
                f = tk.Frame(self.pre_container, bg='#1a1a1a', pady=4)
                f.pack(fill='x', pady=(4, 2))
                
                symbol = "▼" if current_header_open else "▶"
                tk.Button(f, text=f"{symbol} {item['name']}", bg='#1a1a1a', fg='#fff', font=('Arial', 10, 'bold'), relief='flat', bd=0, highlightthickness=0, activebackground='#1a1a1a', activeforeground='#00ffff', anchor='w', command=lambda i=idx: self.toggle_header(i)).pack(side='left', fill='x', expand=True, padx=(5,0))
                
                right_btns = tk.Frame(f, bg='#1a1a1a')
                right_btns.pack(side='right')
                tk.Button(right_btns, text="↑", bg='#1a1a1a', fg='#888', relief='flat', bd=0, activebackground='#1a1a1a', activeforeground='#fff', font=('Arial', 10), width=2, command=lambda i=idx: self.move_item(i, -1)).pack(side='left')
                tk.Button(right_btns, text="↓", bg='#1a1a1a', fg='#888', relief='flat', bd=0, activebackground='#1a1a1a', activeforeground='#fff', font=('Arial', 10), width=2, command=lambda i=idx: self.move_item(i, 1)).pack(side='left')
                tk.Button(right_btns, text="×", bg='#1a1a1a', fg='#666', relief='flat', bd=0, activebackground='#1a1a1a', activeforeground='#ff4444', font=('Arial', 10, 'bold'), width=2, command=lambda i=idx: self.delete_item(i)).pack(side='left')

            elif item["type"] == "preset":
                if not current_header_open:
                    continue 
                
                f = tk.Frame(self.pre_container, bg='#111', pady=2)
                f.pack(fill='x', pady=1, padx=(10, 0))
                self.frame_to_item_idx[f] = idx  # Store mapping for search
                
                header = tk.Frame(f, bg='#111')
                header.pack(fill='x')
                
                tags = item["tags"]
                label = item["name"]
                is_active = all(t in self.tags_internal for t in tags)
                symbol, color, cmd = ("-", "#ff4444", lambda t=tags: self.remove_tags(t)) if is_active else ("+", "#00ff00", lambda t=tags: self.add_tags(t))
                
                tk.Button(header, text=symbol, bg='#1a1a1a', fg=color, relief='solid', bd=1, highlightthickness=0, activebackground='#222', activeforeground=color, font=('Arial', 10, 'bold'), width=2, command=cmd).pack(side='left', padx=(0, 5))
                
                is_open = item.get("open", False)
                lbl_symbol = "▼" if is_open else "▶"
                lbl = tk.Button(header, text=f"{lbl_symbol} {label}", bg='#111', fg='#ccc', relief='flat', bd=0, highlightthickness=0, activebackground='#111', activeforeground='#fff', anchor='w')
                lbl.pack(side='left', fill='x', expand=True)
                
                right_btns = tk.Frame(header, bg='#111')
                right_btns.pack(side='right')
                tk.Button(right_btns, text="↑", bg='#111', fg='#888', relief='flat', bd=0, highlightthickness=0, activebackground='#111', activeforeground='#fff', font=('Arial', 10), width=2, command=lambda i=idx: self.move_item(i, -1)).pack(side='left')
                tk.Button(right_btns, text="↓", bg='#111', fg='#888', relief='flat', bd=0, highlightthickness=0, activebackground='#111', activeforeground='#fff', font=('Arial', 10), width=2, command=lambda i=idx: self.move_item(i, 1)).pack(side='left')
                tk.Button(right_btns, text="×", bg='#111', fg='#666', relief='flat', bd=0, highlightthickness=0, activebackground='#111', activeforeground='#ff4444', font=('Arial', 10, 'bold'), width=2, command=lambda i=idx: self.delete_item(i)).pack(side='left')
                
                content = tk.Frame(f, bg='#050505')
                tk.Label(content, text=", ".join(tags), fg='#666', font=('Arial', 8), wraplength=230, bg='#050505', justify='left', anchor='w').pack(fill='x', padx=10, pady=5)
                
                f.content = content
                lbl.config(command=lambda fr=f, b=lbl, l_txt=label, i=idx: self.toggle_preset(fr, b, l_txt, i))
                
                if is_open:
                    content.pack(fill='x')

    def toggle_header(self, idx):
        item = self.sidebar_items[idx]
        item["open"] = not item.get("open", True)
        self.rebuild_presets_ui()

    def toggle_preset(self, frame, btn, label_text, idx):
        item = self.sidebar_items[idx]
        is_open = item.get("open", False)
        item["open"] = not is_open
        if item["open"]:
            frame.content.pack(fill='x')
            btn.config(text=f"▼ {label_text}")
        else:
            frame.content.pack_forget()
            btn.config(text=f"▶ {label_text}")

    def move_item(self, idx, direction):
        item = self.sidebar_items[idx]
        
        if item["type"] == "header":
            start_1 = idx
            end_1 = idx + 1
            while end_1 < len(self.sidebar_items) and self.sidebar_items[end_1]["type"] != "header":
                end_1 += 1
                
            if direction == -1: # Move UP
                if start_1 == 0: return 
                
                prev_header_idx = -1
                for i in range(start_1 - 1, -1, -1):
                    if self.sidebar_items[i]["type"] == "header":
                        prev_header_idx = i
                        break
                
                if prev_header_idx == -1: return 
                
                start_2 = prev_header_idx
                end_2 = start_1
                
                self.sidebar_items = (self.sidebar_items[:start_2] + 
                                      self.sidebar_items[start_1:end_1] + 
                                      self.sidebar_items[start_2:end_2] + 
                                      self.sidebar_items[end_1:])
                                      
            elif direction == 1: # Move DOWN
                if end_1 == len(self.sidebar_items): return 
                
                start_2 = end_1
                end_2 = start_2 + 1
                while end_2 < len(self.sidebar_items) and self.sidebar_items[end_2]["type"] != "header":
                    end_2 += 1
                    
                self.sidebar_items = (self.sidebar_items[:start_1] + 
                                      self.sidebar_items[start_2:end_2] + 
                                      self.sidebar_items[start_1:end_1] + 
                                      self.sidebar_items[end_2:])
        else:
            new_idx = idx + direction
            if 0 <= new_idx < len(self.sidebar_items):
                self.sidebar_items[idx], self.sidebar_items[new_idx] = self.sidebar_items[new_idx], self.sidebar_items[idx]
                
        self.save_presets_to_disk()
        self.rebuild_presets_ui()

    def delete_item(self, idx):
        item = self.sidebar_items[idx]
        t = "Header" if item["type"] == "header" else "Preset"
        if messagebox.askyesno("Delete", f"Remove {t} '{item['name']}'?"):
            self.sidebar_items.pop(idx)
            self.save_presets_to_disk()
            self.rebuild_presets_ui()

    def add_header_gui(self):
        name = simpledialog.askstring("New Header", "Enter header name:", parent=self.root)
        if name and name.strip():
            # NEW HEADERS default TRUE
            self.sidebar_items.append({"type": "header", "name": name.strip(), "open": True})
            self.save_presets_to_disk()
            self.rebuild_presets_ui()

    def add_preset_gui(self):
        dialog = Toplevel(self.root)
        dialog.title("New Preset Editor")
        dialog.geometry("500x600")
        dialog.configure(bg='#1a1a1a')
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Preset Header Name:", bg='#1a1a1a', fg='#fff').pack(pady=(10,0))
        name_en = tk.Entry(dialog, bg='#333', fg='#fff', insertbackground='#fff', font=('Arial', 12))
        name_en.pack(padx=10, fill='x')
        add_placeholder(name_en, "Preset name...")
        name_en.focus_set()

        tk.Label(dialog, text="Tags Editor (Autocomplete & Free Type):", bg='#1a1a1a', fg='#fff').pack(pady=(10,0))

        mini_en = tk.Entry(dialog, bg='#111', fg='#fff', insertbackground='#fff', font=('Consolas', 12))
        mini_en.pack(fill='x', padx=10, pady=(0, 5))
        add_placeholder(mini_en, "Type a tag to search...")

        # --- Auto Discovery + Whitelist (all on one line, centered) ---
        booru_var = tk.BooleanVar(value=False)
        
        booru_frame = tk.Frame(dialog, bg='#1a1a1a')
        booru_frame.pack(fill='x', padx=10, pady=(5, 3))
        
        tk.Frame(booru_frame, bg='#1a1a1a').pack(side='left', expand=True)
        
        tk.Checkbutton(booru_frame, text="🔍 Auto", variable=booru_var, bg='#1a1a1a', fg='#00aaff', selectcolor='#222', font=('Arial', 9), command=lambda: self._toggle_booru(booru_var, mini_en, mini_lb)).pack(side='left')
        
        tk.Label(booru_frame, text="Posts:", bg='#1a1a1a', fg='#888', font=('Arial', 9)).pack(side='left', padx=(10, 2))
        posts_var = tk.StringVar(value="100")
        tk.Entry(booru_frame, textvariable=posts_var, bg='#333', fg='#fff', insertbackground='#fff', font=('Consolas', 9), width=5).pack(side='left')
        
        tk.Label(booru_frame, text="Min %:", bg='#1a1a1a', fg='#888', font=('Arial', 9)).pack(side='left', padx=(10, 2))
        min_occ_var = tk.StringVar(value="35")
        tk.Entry(booru_frame, textvariable=min_occ_var, bg='#333', fg='#fff', insertbackground='#fff', font=('Consolas', 9), width=5).pack(side='left')
        
        _posts_var = posts_var
        _min_occ_var = min_occ_var

        tk.Label(booru_frame, text="  Add:", bg='#1a1a1a', fg='#888', font=('Arial', 9)).pack(side='left')
        wl_add_entry = tk.Entry(booru_frame, bg='#333', fg='#fff', insertbackground='#fff', font=('Consolas', 9), width=12)
        wl_add_entry.pack(side='left', padx=(3, 3))
        
        _temp_whitelist = set()
        wl_path = Path(__file__).resolve().parent / "models" / "discovery_whitelist.txt"

        wl_btn = tk.Button(booru_frame, text="+", bg='#113311', fg='#44ff44', font=('Arial', 12, 'bold'), width=2, bd=0, relief='flat')
        wl_btn.pack(side='left')
        
        tk.Frame(booru_frame, bg='#1a1a1a').pack(side='left', expand=True)

        mini_lb = tk.Listbox(dialog, height=5, bg='#111', borderwidth=0, font=('Consolas', 10), selectbackground='#444', exportselection=False)
        mini_lb.pack(fill='x', padx=10, pady=5)

        def _add_to_whitelist():
            tag = wl_add_entry.get().strip().lower().replace(" ", "_")
            if tag and tag not in _temp_whitelist:
                _temp_whitelist.add(tag)
                wl_add_entry.delete(0, tk.END)
                _update_btn()

        def _remove_from_whitelist():
            tag = wl_add_entry.get().strip().lower().replace(" ", "_")
            if tag and tag in _temp_whitelist:
                _temp_whitelist.discard(tag)
                wl_add_entry.delete(0, tk.END)
                _update_btn()

        def _update_btn():
            tag = wl_add_entry.get().strip().lower().replace(" ", "_")
            if tag and tag in _temp_whitelist:
                wl_btn.config(text="−", bg='#331111', fg='#ff4444', command=_remove_from_whitelist)
            else:
                wl_btn.config(text="+", bg='#113311', fg='#44ff44', command=_add_to_whitelist)

        wl_add_entry.bind('<Return>', lambda e: wl_btn.invoke())
        wl_add_entry.bind('<KeyRelease>', lambda e: _update_btn())

        # Whitelist note
        tk.Label(dialog, text="Whitelist for general tags — edit discovery_whitelist.txt in python and models/models/", bg='#1a1a1a', fg='#555', font=('Arial', 8, 'italic')).pack(padx=(20, 10), pady=(0, 5))

        mini_tx = tk.Text(dialog, bg='#050505', fg='#ccc', font=('Consolas', 12), wrap='word', borderwidth=1, padx=10, pady=10, height=4, insertbackground='#fff')
        mini_tx.pack(fill='both', expand=True, padx=10)

        for code, color in TAG_COLORS.items():
            mini_tx.tag_config(f"cat_{code}", foreground=color)

        def re_color_mini(e=None):
            if e and e.keysym not in ('space', 'Return', 'Tab'): return
            content = mini_tx.get("1.0", "end-1c").split()
            mini_tx.delete("1.0", tk.END)
            for w in content:
                t_type = self.dic.get(w, {}).get("type", "0")
                start = mini_tx.index(tk.INSERT)
                mini_tx.insert(tk.END, w + " ")
                mini_tx.tag_add(f"cat_{t_type}", start, mini_tx.index(tk.INSERT))

        def mini_kb(e):
            if e.keysym in ("Return", "Tab", "Up", "Down"): return
            q = mini_en.get().strip().lower()
            mini_lb.delete(0, tk.END)
            if not q: return
            matches = sorted([n for n in self.dic if n.startswith(q)], key=lambda x: int(self.dic[x]['count']), reverse=True)[:20]
            for m in matches:
                color = TAG_COLORS.get(self.dic[m]['type'], "#fff")
                mini_lb.insert(tk.END, f"{m} ({self.dic[m]['count']})")
                mini_lb.itemconfig(tk.END, fg=color, selectforeground=color)
            if mini_lb.size() > 0: mini_lb.selection_set(0); mini_lb.activate(0)

        def mini_ok(e=None):
            # If booru mode is active, trigger discovery with inline config
            if booru_var.get():
                # Check autocomplete selection first
                sel = mini_lb.curselection()
                active = mini_lb.index(tk.ACTIVE) if not sel else sel[0]
                tag = mini_lb.get(active).split(" (")[0] if mini_lb.size() > 0 else mini_en.get().strip()
                tag = tag.lower().replace(" ", "_")
                if tag:
                    try:
                        posts = int(_posts_var.get())
                        min_occ = int(_min_occ_var.get())
                        if posts <= 0 or min_occ <= 0:
                            messagebox.showwarning("Invalid", "Both values must be positive.")
                            return 'break'
                    except ValueError:
                        messagebox.showwarning("Invalid", "Please enter valid numbers.")
                        return 'break'
                    mini_en.config(state='disabled')
                    mini_lb.config(state='disabled')
                    self._run_discover(tag, name_en, mini_tx, mini_en, mini_lb, posts, min_occ, _temp_whitelist, wl_path)
                return 'break'
            
            sel = mini_lb.curselection()
            active = mini_lb.index(tk.ACTIVE) if not sel else sel[0]
            tag = mini_lb.get(active).split(" (")[0] if mini_lb.size() > 0 else mini_en.get().strip()
            
            if tag:
                current_text = mini_tx.get("1.0", "end-1c")
                if len(current_text) > 0 and not current_text.endswith(" "):
                    mini_tx.insert("end-1c", " ")
                
                start = mini_tx.index("end-1c")
                mini_tx.insert("end-1c", tag + " ")
                t_type = self.dic.get(tag, {}).get("type", "0")
                mini_tx.tag_add(f"cat_{t_type}", start, mini_tx.index("end-1c"))
                
                mini_tx.mark_set(tk.INSERT, "end-1c")
                mini_tx.see(tk.INSERT)

            mini_en.delete(0, tk.END); mini_lb.delete(0, tk.END)
            return 'break'

        def mini_move_sel(e):
            curr = mini_lb.curselection(); idx = (curr[0] + (1 if e.keysym == 'Down' else -1)) if curr else 0
            idx = max(0, min(idx, mini_lb.size()-1))
            mini_lb.selection_clear(0, tk.END); mini_lb.selection_set(idx); mini_lb.activate(idx); mini_lb.see(idx)
            return 'break'

        mini_en.bind('<KeyRelease>', mini_kb)
        mini_en.bind('<Return>', mini_ok)
        mini_en.bind('<Tab>', mini_ok)
        mini_en.bind('<Down>', mini_move_sel)
        mini_en.bind('<Up>', mini_move_sel)
        mini_lb.bind('<Double-Button-1>', mini_ok)
        mini_tx.bind('<KeyRelease>', re_color_mini)

        def save_new(event=None):
            n = name_en.get().strip()
            t_list = mini_tx.get("1.0", tk.END).split()
            if n and t_list:
                tags = [x.strip().replace(" ", "_").lower() for x in t_list if x.strip()]
                # NEW PRESETS default FALSE
                self.sidebar_items.append({"type": "preset", "name": n, "tags": tags, "open": False})
                self.save_presets_to_disk()
                self.rebuild_presets_ui()
                dialog.destroy()

        tk.Button(dialog, text="SAVE PRESET", command=save_new, bg='#00aa00', fg='#fff', font=('Arial', 10, 'bold')).pack(pady=10)

    def _toggle_booru(self, booru_var, mini_en, mini_lb):
        """Toggle booru mode."""
        if booru_var.get():
            mini_en.config(bg='#222', fg='#00aaff')
            mini_lb.config(bg='#111', fg='#444')
            for i in range(mini_lb.size()):
                mini_lb.itemconfig(i, fg='#444')
        else:
            mini_en.config(bg='#111', fg='#fff')
            mini_lb.config(bg='#111', fg='#fff')

    def _run_discover(self, tag, name_en, mini_tx, mini_en, mini_lb, posts=100, min_occurrences=25, temp_whitelist=None, wl_path=None):
        """Run the actual booru discovery."""
        # Read API credentials from config.ini
        api_user_id = ""
        api_key = ""
        try:
            cp = configparser.ConfigParser()
            cp.read(CONFIG_DIR / "config.ini", encoding="utf-8")
            api_user_id = cp.get("api", "user_id", fallback="").strip()
            api_key = cp.get("api", "api_key", fallback="").strip()
        except Exception:
            pass
        
        # Use env vars if set
        final_api_user_id = os.environ.get("API_USER_ID", api_user_id)
        final_api_key = os.environ.get("API_KEY", api_key)
        
        if not final_api_key:
            messagebox.showwarning("No API Key", "API credentials not found.\nSet API_USER_ID and API_KEY in the Settings GUI (customize.bat), or export them as environment variables.")
            return
        
        # Check if API_KEY is the full query string (from R34 API response)
        # or just the raw key value
        if "api_key=" in final_api_key and "user_id=" in final_api_key:
            # It's the full query string from R34 — use it directly
            auth_suffix = final_api_key
        else:
            # It's just the raw key — build the query string
            auth_suffix = f"api_key={final_api_key}&user_id={final_api_user_id}"
        
        # Show progress dialog
        progress = Toplevel(self.root)
        progress.title("Discovering...")
        progress.geometry("300x150")
        progress.configure(bg='#1a1a1a')
        progress.transient(self.root)
        progress.grab_set()
        
        tk.Label(progress, text=f"Analyzing '{tag}'...", bg='#1a1a1a', fg='#fff').pack(pady=10)
        tk.Label(progress, text=f"Fetching {posts} images (min {min_occurrences}% threshold)...", bg='#1a1a1a', fg='#888').pack()
        progress.update()
        
        try:
            # Fetch images
            if auth_suffix.startswith("&"):
                url = f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&limit={posts}&pid=0&tags={quote(tag)}{auth_suffix}"
            else:
                url = f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&limit={posts}&pid=0&tags={quote(tag)}&{auth_suffix}"
            response = requests.get(url, headers={"User-Agent": "r34-tag-updater/1.0"})
            
            if response.status_code != 200:
                progress.destroy()
                messagebox.showerror("Error", f"Failed to fetch images. Status: {response.status_code}")
                mini_en.config(state='normal')
                mini_lb.config(state='normal')
                return
            
            # Parse XML using the same approach as refresh_tags.py
            # The R34 API returns tags as a space-separated string in the 'tags' attribute
            root = ET.fromstring(response.text)
            posts = root.findall(".//post")
            
            if not posts:
                progress.destroy()
                messagebox.showinfo("Info", "No images found for this tag.")
                mini_en.config(state='normal')
                mini_lb.config(state='normal')
                return
            
            # Analyze tags — mirror refresh_tags.py logic
            tracked_tags = {}
            for post in posts:
                raw_tags = post.get("tags", "")
                for tag_name in raw_tags.split():
                    tag_name = tag_name.lower().replace(" ", "_")
                    if tag_name not in tracked_tags:
                        # Look up the tag type from the master taglist only
                        t_type = self.dic.get(tag_name, {}).get("type", "0")
                        tracked_tags[tag_name] = {"count": 0, "type": t_type}
                    tracked_tags[tag_name]["count"] += 1
            
            # Filter to minimum percentage threshold
            min_count = int(len(posts) * min_occurrences / 100)
            discovered = {name: data for name, data in tracked_tags.items() if data["count"] >= min_count}
            
            # Exclude metadata (3) and artist (5) tags
            # Character (1), copyright (4), and general (0) tags all pass through
            discovered = {name: data for name, data in discovered.items() if data["type"] in ["0", "1", "4"]}
            
            # Apply whitelist filter for general tags
            loaded_whitelist = set()
            try:
                wl_path = Path(__file__).resolve().parent / "models" / "discovery_whitelist.txt"
                if wl_path.exists():
                    loaded_whitelist = set(wl_path.read_text(encoding="utf-8").splitlines())
            except Exception:
                pass
            
            # Merge with temporary whitelist (user-added tags)
            if temp_whitelist:
                loaded_whitelist = loaded_whitelist | temp_whitelist
            
            filtered = {}
            for name, data in discovered.items():
                t = data["type"]
                if t == "1" or t == "4":  # character or copyright - always add
                    filtered[name] = data
                elif t == "0" and name in loaded_whitelist:  # general - whitelist only
                    filtered[name] = data
            discovered = filtered
            
            # Save any new whitelist additions back to file
            if temp_whitelist and wl_path:
                try:
                    all_tags = loaded_whitelist | temp_whitelist
                    wl_path.write_text('\n'.join(sorted(all_tags)), encoding='utf-8')
                except Exception:
                    pass
            
            # Sort by count
            discovered = dict(sorted(discovered.items(), key=lambda x: x[1]["count"], reverse=True))
            
            # Print summary of all assessed tags with >= half the threshold
            half_threshold = int(len(posts) * min_occurrences / 200)
            assessed = {name: data for name, data in tracked_tags.items() if data["count"] >= half_threshold}
            assessed = dict(sorted(assessed.items(), key=lambda x: x[1]["count"], reverse=True))
            if assessed:
                print(f"\n--- Discovered tags for '{tag}' (>= {min_occurrences / 2:.1f}% confidence) ---")
                for name, data in assessed.items():
                    type_names = {"0": "general", "1": "character", "3": "metadata", "4": "copyright", "5": "artist"}
                    tname = type_names.get(data["type"], "unknown")
                    pct = data["count"] / len(posts) * 100
                    print(f"  {name}: {pct:.0f}% ({tname})")
                print(f"--- {len(assessed)} tags assessed ---\n")
            
            progress.destroy()
            
            # Clear existing content and pre-fill with discovered tags
            mini_tx.delete("1.0", tk.END)
            for tag_name in discovered:
                t_type = self.dic.get(tag_name, {}).get("type", "0")
                start = mini_tx.index(tk.INSERT)
                mini_tx.insert(tk.END, tag_name + " ")
                end = mini_tx.index(tk.INSERT)
                mini_tx.tag_add(f"cat_{t_type}", start, end)
            
            # Auto-fill name with the search tag
            name_en.delete(0, tk.END)
            name_en.insert(0, tag)
            
            # Re-enable the input box
            mini_en.config(state='normal', bg='#111', fg='#fff')
            mini_lb.config(state='normal', bg='#111', fg='#fff')
            mini_lb.delete(0, tk.END)
            
            messagebox.showinfo("Discovered", f"Found {len(discovered)} tags with at least {min_occurrences}% confidence.\nCheck the tags editor below.")
            
        except Exception as e:
            progress.destroy()
            messagebox.showerror("Error", f"Error discovering character: {str(e)}")
            mini_en.config(state='normal')
            mini_lb.config(state='normal')

    def add_tags(self, tags):
        for t in tags:
            if t not in self.tags_internal:
                self.tags_internal.append(t)
                self.stable_tags.add(t) 
                if t not in self.history: self.history.append(t)
        self.refresh_ui()

    def remove_tags(self, tags):
        for t in tags:
            if t in self.tags_internal: self.tags_internal.remove(t)
        self.refresh_ui()

    def on_text_key(self, event):
        if event.keysym in ('space', 'Return', 'Tab'):
            words = self.tx.get("1.0", tk.END).split()
            for w in words: self.stable_tags.add(w)
        self.sync_from_text()

    def sync_from_text(self):
        current_raw = self.tx.get("1.0", tk.END).split()
        for old_tag in self.tags_internal:
            if old_tag not in current_raw:
                if old_tag in self.stable_tags and old_tag not in self.history:
                    self.history.append(old_tag)

        self.tags_internal = list(set(current_raw))
        self.refresh_history_ui(); self.rebuild_presets_ui()

    def refresh_history_ui(self):
        self.hist_tx.config(state='normal'); self.hist_tx.delete("1.0", tk.END)
        for tag in self.history:
            t_type = self.dic.get(tag, {}).get("type", "0")
            start = self.hist_tx.index(tk.INSERT)
            self.hist_tx.insert(tk.END, tag)
            end = self.hist_tx.index(tk.INSERT)
            self.hist_tx.tag_add(f"cat_{t_type}", start, end)
            if tag not in self.tags_internal: self.hist_tx.tag_add("strike", start, end)
            self.hist_tx.insert(tk.END, "  ")
        self.hist_tx.config(state='disabled')

    def click_history(self, event):
        idx = self.hist_tx.index(f"@{event.x},{event.y}")
        line_start = self.hist_tx.index(f"{idx} linestart")
        line_end = self.hist_tx.index(f"{idx} lineend")
        line_content = self.hist_tx.get(line_start, line_end)
        char_offset = int(idx.split('.')[1])
        words = line_content.split('  ')
        current_len = 0
        clicked_tag = None
        for word in words:
            if current_len <= char_offset < current_len + len(word) + 2:
                clicked_tag = word.strip(); break
            current_len += len(word) + 2
        if clicked_tag in self.history:
            if clicked_tag in self.tags_internal: self.tags_internal.remove(clicked_tag)
            else: 
                self.tags_internal.append(clicked_tag)
                self.stable_tags.add(clicked_tag)
            self.refresh_ui()

    def _add_to_blacklist(self, event=None):
        tag = self.bl_entry.get().strip().lower().replace(" ", "_")
        if not tag:
            return
        # Add to blacklist file
        blacklist_path = CONFIG_DIR / "blacklist.txt"
        if not blacklist_path.exists():
            blacklist_path.write_text("", encoding="utf-8")
        with open(blacklist_path, 'r', encoding='utf-8') as f:
            existing = [l.strip().lower() for l in f if l.strip() and not l.startswith('#')]
        if tag in existing:
            self.bl_status.config(text="already there", foreground="#ffaa00")
        else:
            with open(blacklist_path, 'a', encoding='utf-8') as f:
                f.write(f"{tag}\n")
            self.bl_status.config(text=f"✓ {tag}", foreground="#00ff00")
        self.bl_entry.delete(0, tk.END)
        # Remove from all tracking lists
        if tag in self.tags_internal:
            self.tags_internal.remove(tag)
        if tag in self.original_tags:
            self.original_tags.remove(tag)
        if tag in self.stable_tags:
            self.stable_tags.discard(tag)
        self.refresh_ui()

    def refresh_ui(self):
        # ONLY rebuild the UI from tags_internal if NOT in lora_mode
        if not getattr(self, 'lora_mode', False):
            self.tx.delete("1.0", tk.END)
            sorted_all = sorted(list(set(self.tags_internal)))
            buckets = {code: [] for code in CAT_ORDER}
            for t in sorted_all:
                t_type = self.dic.get(t, {}).get("type", "0")
                buckets[t_type if t_type in buckets else "0"].append(t)
            
            for code in CAT_ORDER:
                tags_in_bucket = buckets[code]
                if tags_in_bucket:
                    for i, tag in enumerate(tags_in_bucket):
                        start = self.tx.index(tk.INSERT)
                        self.tx.insert(tk.END, tag)
                        end = self.tx.index(tk.INSERT)
                        if tag not in self.original_tags: self.tx.tag_add("new_tag", start, end)
                        else: self.tx.tag_add(f"cat_{code}", start, end)
                        self.tx.insert(tk.END, " " if i < len(tags_in_bucket)-1 else "")
                    self.tx.insert(tk.END, "\n")
            
            self.tags_internal = sorted_all
        
        # Always run these, regardless of mode
        self.refresh_history_ui()
        self.rebuild_presets_ui()

    def kb(self, e):
        if e.keysym in ("Return", "Tab", "Up", "Down"): return
        q = self.en.get().strip().lower()
        self.lb.delete(0, tk.END)
        if not q: return
        matches = sorted([n for n in self.dic if n.startswith(q)], key=lambda x: int(self.dic[x]['count']), reverse=True)[:20]
        for m in matches:
            color = TAG_COLORS.get(self.dic[m]['type'], "#fff")
            self.lb.insert(tk.END, f"{m} ({self.dic[m]['count']})")
            self.lb.itemconfig(tk.END, fg=color, selectforeground=color)
        if self.lb.size() > 0: self.lb.selection_set(0); self.lb.activate(0)

    def ok(self, e=None):
        sel = self.lb.curselection()
        active = self.lb.index(tk.ACTIVE) if not sel else sel[0]
        tag = self.lb.get(active).split(" (")[0] if self.lb.size() > 0 else self.en.get().strip()
        if tag:
            self.add_tags([tag]); self.en.delete(0, tk.END); self.lb.delete(0, tk.END)
        return 'break'

    def move_sel(self, e):
        curr = self.lb.curselection(); idx = (curr[0] + (1 if e.keysym == 'Down' else -1)) if curr else 0
        idx = max(0, min(idx, self.lb.size()-1))
        self.lb.selection_clear(0, tk.END); self.lb.selection_set(idx); self.lb.activate(idx); self.lb.see(idx)
        return 'break'

    def ld(self):
        if self.idx < 0: self.idx = len(self.imgs) - 1
        if self.idx >= len(self.imgs): self.idx = 0
            
        n = self.imgs[self.idx]; p = os.path.join(self.in_d, n)
        self.raw_img = Image.open(p)
        w, h = self.root.winfo_screenwidth()//2, self.root.winfo_screenheight()-250
        tmp = self.raw_img.copy(); tmp.thumbnail((w, h), Image.Resampling.LANCZOS)
        self.ph = ImageTk.PhotoImage(tmp); self.il.config(image=self.ph)

        name = os.path.splitext(n)[0]
        tp = os.path.join(self.out_d, name + ".txt")
        
        # If the -tag.txt file is missing, check for the original image's .txt file
        if not os.path.exists(tp) and "-tag" in name:
            fallback_tp = os.path.join(self.out_d, name.replace("-tag", "") + ".txt")
            if os.path.exists(fallback_tp):
                tp = fallback_tp
    
        self.tags_internal = []

        print(f"DEBUG: Looking for text file at: {tp}")
        if os.path.exists(tp):
            if getattr(self, 'lora_mode', False):
                with open(tp, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # FIX: Use '0' and 'end' for Entry widgets
                    self.tx.delete("1.0", 'end')
                    self.tx.insert("1.0", content)
            else:
                # Normal mode
                with open(tp, 'r', encoding='utf-8') as f: 
                    self.tags_internal = f.read().replace(",", " ").split()
        
        # Only perform the original setup if NOT in LoRA mode
        if not getattr(self, 'lora_mode', False):
            self.original_tags = list(self.tags_internal)
            self.stable_tags = set(self.original_tags)
            self.history = [] 
        
        self.refresh_ui(); self.en.focus_set()

    def sv(self):
        p = os.path.join(self.out_d, os.path.splitext(self.imgs[self.idx])[0] + ".txt")
        if self.lora_mode:
            # FIX: Use "1.0" and "end-1c" to get all text from the Text widget
            raw_text = self.tx.get("1.0", "end-1c")
            with open(p, 'w', encoding='utf-8') as f:
                f.write(raw_text)
        else:
            # Normal mode
            clean_tags = " ".join(sorted([t for t in self.tags_internal if t.strip()]))
            with open(p, 'w', encoding='utf-8') as f: f.write(clean_tags)
        self.idx += 1; self.ld()

    def save_and_copy(self):
        p = os.path.join(self.out_d, os.path.splitext(self.imgs[self.idx])[0] + ".txt")
        if self.lora_mode:
            clean_tags = self.tx.get("1.0", "end-1c").replace("\n", " ").strip()
        else:
            clean_tags = " ".join(sorted([t for t in self.tags_internal if t.strip()]))
            
        with open(p, 'w', encoding='utf-8') as f: f.write(clean_tags)
        self.root.clipboard_clear()
        self.root.clipboard_append(clean_tags)
        self.idx += 1; self.ld()

    def skip(self): self.idx += 1; self.ld()
    def prev(self): self.idx -= 1; self.ld()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True); p.add_argument("--output", required=True)
    p.add_argument("--dict", required=True); p.add_argument("--presets", default="presets.txt")
    p.add_argument("--lora-mode", action="store_true")
    a = p.parse_args()
    rt = tk.Tk(); rt.title("Manual Curator")
    
    # 1. Get all valid images
    print(f"Looking for images in: {a.input}")
    all_files = [f for f in os.listdir(a.input) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    print(f"Found {len(all_files)} total files.")
    
    # 2. Filter logic: keep tagged files, or originals that have no tagged counterpart
    li = []
    for f in all_files:
        name, ext = os.path.splitext(f)
        # Skip the censored images since you DONT NEED THEM !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        if "-pixiv" in f.lower():
            continue
        
        # If file ends in -tag, always keep it
        if f.endswith("-tag" + ext):
            li.append(f)
        # If file is an original, only keep if the -tag version is NOT found
        elif (name + "-tag" + ext) not in all_files:
            li.append(f)
            
    if not li:
        print("ERROR: No valid images found after filtering. Check your --input path and filter logic.")
        exit()
            
    # 3. Sort and Launch
    li.sort(key=lambda var: [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', var)])    
    App(rt, li, a.input, a.output, load_dict(a.dict), a.presets, lora_mode=a.lora_mode)
    rt.mainloop()
