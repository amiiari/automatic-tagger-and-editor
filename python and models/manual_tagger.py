import os, tkinter as tk, csv, argparse
from PIL import Image, ImageTk
from tkinter import messagebox, Toplevel

# Booru Category Order & Colors
CAT_ORDER = ["3", "4", "1", "0", "5"]
TAG_COLORS = {
    "3": "#dd00dd", # Copyright
    "4": "#00aa00", # Character
    "1": "#ee8887", # Artist
    "0": "#00afff", # General
    "5": "#ff8800", # Meta
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

class App:
    def __init__(self, root, imgs, in_d, out_d, dic, preset_file):
        self.root, self.imgs, self.in_d, self.out_d, self.dic, self.idx = root, imgs, in_d, out_d, dic, 0
        self.preset_file = preset_file
        self.root.configure(bg='#0a0a0a')
        self.root.state('zoomed')
        
        self.tags_internal = []
        self.original_tags = [] 
        self.history = [] 
        self.presets = self.load_presets()
        
        # This keeps track of tags that were actually "finished" (not just being typed)
        self.stable_tags = set()

        self.main_f = tk.Frame(root, bg='#0a0a0a')
        self.main_f.pack(fill='both', expand=True, padx=10, pady=10)
        
        # --- SIDEBAR ---
        self.pre_col = tk.Frame(self.main_f, bg='#0a0a0a', width=260, highlightbackground="#333", highlightthickness=1)
        self.pre_col.pack(side='left', fill='y', padx=(0,10))
        self.pre_col.pack_propagate(False)
        
        tk.Label(self.pre_col, text="PRESETS", bg='#1a1a1a', fg='#fff', font=('Arial', 9, 'bold')).pack(fill='x')
        self.pre_container = tk.Frame(self.pre_col, bg='#0a0a0a')
        self.pre_container.pack(fill='both', expand=True)
        
        # --- EDITOR ---
        self.edit_col = tk.Frame(self.main_f, bg='#0a0a0a', width=500)
        self.edit_col.pack(side='left', fill='y')
        self.edit_col.pack_propagate(False)

        self.en = tk.Entry(self.edit_col, bg='#111', fg='#fff', insertbackground='#fff', font=('Consolas', 12))
        self.en.pack(fill='x', pady=(0, 5))
        self.en.bind('<KeyRelease>', self.kb)
        self.en.bind('<Return>', self.ok)
        self.en.bind('<Tab>', self.ok)
        self.en.bind('<Down>', self.move_sel)
        self.en.bind('<Up>', self.move_sel)

        self.lb = tk.Listbox(self.edit_col, height=6, bg='#111', borderwidth=0, font=('Consolas', 10), selectbackground='#444', exportselection=False)
        self.lb.pack(fill='x', pady=5)
        self.lb.bind('<Double-Button-1>', self.ok)

        tk.Label(self.edit_col, text="SESSION HISTORY", bg='#0a0a0a', fg='#888', font=('Arial', 8)).pack(anchor='w')
        self.hist_tx = tk.Text(self.edit_col, height=6, bg='#0a0a0a', font=('Consolas', 10), cursor="hand2", borderwidth=1, highlightbackground='#222', wrap='word', insertbackground='#fff')
        self.hist_tx.pack(fill='x', pady=5)
        self.hist_tx.tag_config("strike", overstrike=True, foreground="#ffffff")
        self.hist_tx.bind("<Button-1>", self.click_history)

        self.tx = tk.Text(self.edit_col, bg='#050505', fg='#ccc', font=('Consolas', 12), wrap='word', borderwidth=1, padx=10, pady=10, insertbackground='#fff')
        self.tx.pack(fill='both', expand=True)
        # We track KeyRelease to detect when the user presses 'Space' or 'Enter' inside the box
        self.tx.bind('<KeyRelease>', self.on_text_key)
        
        for code, color in TAG_COLORS.items():
            self.tx.tag_config(f"cat_{code}", foreground=color)
            self.hist_tx.tag_config(f"cat_{code}", foreground=color)
        
        self.tx.tag_config("new_tag", foreground="#ffffff")

        nav_f = tk.Frame(self.edit_col, bg='#0a0a0a')
        nav_f.pack(fill='x', pady=10)
        tk.Button(nav_f, text="< BACK", command=self.prev, bg='#222', fg='#fff', width=8).pack(side='left', padx=2)
        tk.Button(nav_f, text="SAVE & NEXT", command=self.sv, bg='#1a1a1a', fg='#00ff00', font=('Arial', 10, 'bold')).pack(side='left', expand=True, fill='x', padx=2)
        tk.Button(nav_f, text="NEXT (No Save) >", command=self.skip, bg='#222', fg='#fff', width=12).pack(side='left', padx=2)

        self.il = tk.Label(self.main_f, bg='#050505')
        self.il.pack(side='right', fill='both', expand=True, padx=(10,0))

        tk.Button(self.pre_col, text="+ CREATE NEW PRESET", command=self.add_preset_gui, bg='#222', fg='#00ff00', relief='flat').pack(fill='x', side='bottom', pady=5)
        
        self.ld()

    def load_presets(self):
        p = {}
        if os.path.exists(self.preset_file):
            with open(self.preset_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        p[k.strip()] = [t.strip().replace(" ", "_").lower() for t in v.split(",") if t.strip()]
        return p

    def save_presets_to_disk(self):
        with open(self.preset_file, 'w', encoding='utf-8') as f:
            for k, v in self.presets.items(): f.write(f"{k}: {', '.join(v)}\n")

    def rebuild_presets_ui(self):
        for widget in self.pre_container.winfo_children(): widget.destroy()
        for label, tags in self.presets.items():
            f = tk.Frame(self.pre_container, bg='#111', pady=2)
            f.pack(fill='x', pady=1)
            header = tk.Frame(f, bg='#111')
            header.pack(fill='x')
            btn_box = tk.Frame(header, bg='#111')
            btn_box.pack(side='right')
            is_active = all(t in self.tags_internal for t in tags)
            symbol, color, cmd = ("-", "#ff4444", lambda t=tags: self.remove_tags(t)) if is_active else ("+", "#00ff00", lambda t=tags: self.add_tags(t))
            tk.Button(btn_box, text=symbol, bg='#222', fg=color, relief='flat', font=('Arial', 10, 'bold'), width=2, command=cmd).pack(side='left', padx=1)
            tk.Button(btn_box, text="×", bg='#222', fg='#888', relief='flat', font=('Arial', 10, 'bold'), width=2, command=lambda l=label: self.delete_preset(l)).pack(side='left', padx=1)
            lbl = tk.Button(header, text=f"▼ {label}", bg='#111', fg='#ccc', relief='flat', anchor='w', command=lambda fr=f: self.toggle_preset(fr))
            lbl.pack(side='left', fill='x', expand=True)
            content = tk.Frame(f, bg='#050505')
            tk.Label(content, text=", ".join(tags), fg='#666', font=('Arial', 8), wraplength=220, bg='#050505', justify='left', anchor='w').pack(fill='x', padx=10, pady=5)
            f.content = content 

    def toggle_preset(self, frame):
        if frame.content.winfo_ismapped(): frame.content.pack_forget()
        else: frame.content.pack(fill='x')

    def add_preset_gui(self):
        dialog = Toplevel(self.root)
        dialog.title("New Preset")
        dialog.geometry("300x200")
        dialog.configure(bg='#1a1a1a')
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="Preset Name:", bg='#1a1a1a', fg='#fff').pack(pady=(10,0))
        name_en = tk.Entry(dialog, bg='#333', fg='#fff', insertbackground='#fff'); name_en.pack(padx=10, fill='x'); name_en.focus_set()
        tk.Label(dialog, text="Tags (comma separated):", bg='#1a1a1a', fg='#fff').pack(pady=(10,0))
        tags_en = tk.Entry(dialog, bg='#333', fg='#fff', insertbackground='#fff'); tags_en.pack(padx=10, fill='x')
        def save_new(event=None):
            n, t = name_en.get().strip(), tags_en.get().strip()
            if n and t:
                new_tags = [x.strip().replace(" ", "_").lower() for x in t.split(",") if x.strip()]
                self.presets[n] = new_tags
                self.save_presets_to_disk(); self.rebuild_presets_ui(); dialog.destroy()
        dialog.bind('<Return>', save_new)
        tk.Button(dialog, text="SAVE (Enter)", command=save_new, bg='#00aa00', fg='#fff').pack(pady=20)

    def add_tags(self, tags):
        for t in tags:
            if t not in self.tags_internal:
                self.tags_internal.append(t)
                self.stable_tags.add(t) # Explicitly added tags are always stable
                if t not in self.history: self.history.append(t)
        self.refresh_ui()

    def remove_tags(self, tags):
        for t in tags:
            if t in self.tags_internal: self.tags_internal.remove(t)
        self.refresh_ui()

    def on_text_key(self, event):
        # When user types space, enter, or clicks away, we "validate" the tags they just typed
        if event.keysym in ('space', 'Return', 'Tab'):
            words = self.tx.get("1.0", tk.END).split()
            for w in words: self.stable_tags.add(w)
        self.sync_from_text()

    def sync_from_text(self):
        current_raw = self.tx.get("1.0", tk.END).split()
        
        # 1. Update history: Only if a 'stable' tag was removed
        for old_tag in self.tags_internal:
            if old_tag not in current_raw:
                # Was it stable? (Original, Preset, SearchBox, or typed followed by Space)
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

    def refresh_ui(self):
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
        
        self.tags_internal = sorted_all; self.refresh_history_ui(); self.rebuild_presets_ui()

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
        if self.idx < 0: self.idx = 0
        if self.idx >= len(self.imgs): self.root.destroy(); return
        n = self.imgs[self.idx]; p = os.path.join(self.in_d, n)
        self.raw_img = Image.open(p)
        w, h = self.root.winfo_screenwidth()//2, self.root.winfo_screenheight()-250
        tmp = self.raw_img.copy(); tmp.thumbnail((w, h), Image.Resampling.LANCZOS)
        self.ph = ImageTk.PhotoImage(tmp); self.il.config(image=self.ph)
        tp = os.path.join(self.out_d, os.path.splitext(n)[0] + ".txt")
        self.tags_internal = []
        if os.path.exists(tp):
            with open(tp, 'r', encoding='utf-8') as f: self.tags_internal = f.read().replace(",", " ").split()
        
        self.original_tags = list(self.tags_internal)
        self.stable_tags = set(self.original_tags)
        self.history = [] 
        
        self.refresh_ui(); self.en.focus_set()

    def sv(self):
        p = os.path.join(self.out_d, os.path.splitext(self.imgs[self.idx])[0] + ".txt")
        clean_tags = " ".join(sorted([t for t in self.tags_internal if t.strip()]))
        with open(p, 'w', encoding='utf-8') as f: f.write(clean_tags)
        self.idx += 1; self.ld()

    def skip(self): self.idx += 1; self.ld()
    def prev(self): self.idx -= 1; self.ld()
    def delete_preset(self, l):
        if messagebox.askyesno("Delete", f"Remove '{l}'?"): del self.presets[l]; self.save_presets_to_disk(); self.rebuild_presets_ui()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True); p.add_argument("--output", required=True)
    p.add_argument("--dict", required=True); p.add_argument("--presets", default="presets.txt")
    a = p.parse_args()
    rt = tk.Tk(); rt.title("Manual Curator")
    li = [f for f in os.listdir(a.input) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    App(rt, li, a.input, a.output, load_dict(a.dict), a.presets)
    rt.mainloop()
