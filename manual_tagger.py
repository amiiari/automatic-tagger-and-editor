import os, tkinter as tk, csv, argparse
from PIL import Image, ImageTk

def load_dict(p):
    d = []
    if not os.path.exists(p): return d
    with open(p, 'r', encoding='utf-8') as f:
        r = csv.reader(f)
        for row in r:
            if len(row) >= 3: d.append((row[0].replace(" ", "_"), row[2]))
    return d

class App:
    def __init__(self, root, imgs, in_d, out_d, dic):
        self.root, self.imgs, self.in_d, self.out_d, self.dic, self.idx = root, imgs, in_d, out_d, dic, 0
        self.root.configure(bg='#0a0a0a')
        self.root.state('zoomed')
        
        self.autosort = tk.BooleanVar(value=False)
        self.initial_tags = []
        
        self.main_f = tk.Frame(root, bg='#0a0a0a')
        self.main_f.pack(fill='both', expand=True, padx=20, pady=10)
        
        self.l_col = tk.Frame(self.main_f, bg='#0a0a0a', width=450)
        self.l_col.pack(side='left', fill='y', padx=(0, 20))
        self.l_col.pack_propagate(False)

        self.r_col = tk.Frame(self.main_f, bg='#0a0a0a')
        self.r_col.pack(side='right', fill='both', expand=True)

        self.hdr = tk.Label(self.r_col, text="", bg='#0a0a0a', fg='#888', font=('Arial', 11, 'bold', 'underline'))
        self.hdr.pack(pady=(0, 5))

        self.il = tk.Label(self.r_col, bg='#050505', highlightbackground="#333", highlightthickness=1)
        self.il.pack(fill='both', expand=True)
        self.il.bind('<Configure>', self.on_resize)

        # Search
        tk.Label(self.l_col, text="TYPE TO SEARCH AND APPEND", bg='#0a0a0a', fg='#888', font=('Arial', 10, 'bold', 'underline')).pack(anchor='w')
        tk.Label(self.l_col, text="[UP/DOWN] to select, [TAB/ENTER] to append", bg='#0a0a0a', fg='#555', font=('Arial', 8, 'italic')).pack(anchor='w')
        
        self.en = tk.Entry(self.l_col, bg='#111', fg='#00ff00', insertbackground='#00ff00', font=('Consolas', 14), borderwidth=1, relief="solid", highlightbackground="#333", highlightthickness=1)
        self.en.pack(fill='x', pady=5)
        self.en.bind('<KeyRelease>', self.kb)
        self.en.bind('<Tab>', self.tab_fill)
        self.en.bind('<Return>', self.ok)
        self.en.bind('<Down>', self.focus_lb)

        self.lb = tk.Listbox(self.l_col, height=5, bg='#111', fg='#00afff', selectbackground='#004466', selectforeground='white', borderwidth=1, relief="solid", font=('Consolas', 10), highlightbackground="#333", highlightthickness=1)
        self.lb.pack(fill='x', pady=5)
        self.lb.bind('<Return>', self.ok)

        # Session Changes
        tk.Label(self.l_col, text="SESSION CHANGES (Added / ~~Removed~~)", bg='#0a0a0a', fg='#666', font=('Arial', 8, 'bold')).pack(anchor='w', pady=(10,0))
        self.chg_tx = tk.Text(self.l_col, height=4, bg='#050505', fg='#888', font=('Consolas', 9), borderwidth=1, relief="solid", highlightbackground="#222", state='disabled')
        self.chg_tx.pack(fill='x', pady=5)
        self.chg_tx.tag_config('del', overstrike=True, foreground='#ff4444')
        self.chg_tx.tag_config('add', foreground='#00ff00')

        # Editor
        edt_hdr = tk.Frame(self.l_col, bg='#0a0a0a')
        edt_hdr.pack(fill='x', pady=(10,0))
        tk.Label(edt_hdr, text="EDIT ALL TAGS", bg='#0a0a0a', fg='#666', font=('Arial', 9, 'bold')).pack(side='left')
        tk.Checkbutton(edt_hdr, text="AUTO-SORT A-Z", variable=self.autosort, command=self.do_sort, bg='#0a0a0a', fg='#888', selectcolor='#111', activebackground='#0a0a0a', activeforeground='#00ff00', font=('Arial', 8, 'bold')).pack(side='right')

        self.tx = tk.Text(self.l_col, bg='#111', fg='#bbb', insertbackground='#bbb', font=('Consolas', 11), wrap='word', borderwidth=1, relief="solid", highlightbackground="#333", highlightthickness=1)
        self.tx.pack(fill='both', expand=True, pady=5)
        self.tx.bind('<KeyRelease>', self.update_diff)

        self.btn_f = tk.Frame(self.l_col, bg='#0a0a0a')
        self.btn_f.pack(fill='x', pady=10)
        tk.Button(self.btn_f, text="SKIP", command=self.skip, bg='#1a1a1a', fg='#ff4444', width=10, height=2, borderwidth=1, relief="solid", highlightbackground="#333", font=('Arial', 9, 'bold')).pack(side='right', padx=2)
        tk.Button(self.btn_f, text="SAVE & NEXT", command=self.sv, bg='#1a1a1a', fg='#00ff00', width=15, height=2, borderwidth=1, relief="solid", highlightbackground="#333", font=('Arial', 9, 'bold')).pack(side='right', padx=2)
        
        self.raw_img = None
        self.ld()

    def ld(self):
        if self.idx >= len(self.imgs): self.root.destroy(); return
        n = self.imgs[self.idx]; p = os.path.join(self.in_d, n)
        self.hdr.config(text=f"PREVIEW: {n}")
        self.raw_img = Image.open(p)
        self.update_img()
        tp = os.path.join(self.out_d, os.path.splitext(n)[0] + ".txt")
        cnt = ""
        if os.path.exists(tp):
            with open(tp, 'r', encoding='utf-8') as f: cnt = f.read()
        self.initial_tags = cnt.split()
        self.tx.delete("1.0", tk.END); self.tx.insert(tk.END, cnt)
        self.update_diff()
        if self.autosort.get(): self.do_sort()
        self.en.delete(0, tk.END); self.en.focus_set()

    def update_diff(self, e=None):
        current = self.tx.get("1.0", tk.END).split()
        added = [t for t in current if t not in self.initial_tags]
        removed = [t for t in self.initial_tags if t not in current]
        self.chg_tx.config(state='normal')
        self.chg_tx.delete("1.0", tk.END)
        for t in added: self.chg_tx.insert(tk.END, t + " ", 'add')
        for t in removed: self.chg_tx.insert(tk.END, t + " ", 'del')
        self.chg_tx.config(state='disabled')

    def update_img(self, event=None):
        if self.raw_img is None: return
        
        # Get the actual pixel size of the container
        w = self.il.winfo_width()
        h = self.il.winfo_height()
        
        # If the window just opened, it might report size 1
        if w <= 1 or h <= 1: 
            self.root.after(100, self.update_img)
            return

        # Create the thumbnail without changing the label's required size
        tmp = self.raw_img.copy()
        tmp.thumbnail((w - 4, h - 4), Image.Resampling.LANCZOS)
        
        new_ph = ImageTk.PhotoImage(tmp)
        self.il.config(image=new_ph)
        self.ph = new_ph # Keep reference so it isn't garbage collected

    def on_resize(self, event):
        # Only trigger if the width or height actually changed significantly
        # This prevents the "pixel-creep" loop
        if hasattr(self, '_last_size'):
            if abs(self._last_size[0] - event.width) < 3 and abs(self._last_size[1] - event.height) < 3:
                return
        
        self._last_size = (event.width, event.height)
        
        # Use 'after_cancel' to wait for the user to STOP dragging before redrawing
        if hasattr(self, '_resize_timer'):
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(100, self.update_img)

    def kb(self, e):
        if e.keysym in ('Tab', 'Return', 'Up', 'Down'): return
        q = self.en.get().strip().lower()
        if not q: self.lb.delete(0, tk.END); return
        m = sorted([f"{t[0]} ({t[1]})" for t in self.dic if t[0].startswith(q)])[:20]
        self.lb.delete(0, tk.END)
        for i in m: self.lb.insert(tk.END, i)
        if self.lb.size(): self.lb.selection_set(0)

    def focus_lb(self, e): self.lb.focus_set()
    
    def tab_fill(self, e): 
        self.ok()
        return 'break'

    def ok(self, e=None):
        # Get tag from listbox if something is selected, else use entry text
        sel = self.lb.curselection()
        if sel:
            t = self.lb.get(sel[0]).split()[0]
        else:
            t = self.en.get().strip()
            
        if t: 
            # Force tag into text box with a leading space
            self.tx.insert(tk.END, " " + t.replace(" ","_"))
            self.update_diff()
            if self.autosort.get(): self.do_sort()
            self.en.delete(0, tk.END)
            self.lb.delete(0, tk.END)
            self.en.focus_set()
        return 'break'

    def do_sort(self):
        tags = self.tx.get("1.0", tk.END).split()
        sorted_tags = sorted(list(dict.fromkeys(tags)))
        self.tx.delete("1.0", tk.END)
        self.tx.insert(tk.END, " ".join(sorted_tags))

    def sv(self):
        p = os.path.join(self.out_d, os.path.splitext(self.imgs[self.idx])[0] + ".txt")
        if self.autosort.get(): self.do_sort()
        with open(p, 'w', encoding='utf-8') as f: f.write(" ".join(self.tx.get("1.0", tk.END).split()))
        self.idx += 1; self.ld()

    def skip(self): self.idx += 1; self.ld()

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--input"); p.add_argument("--output"); p.add_argument("--dict")
    a = p.parse_args(); rt = tk.Tk(); rt.title("Manual Curator Pro")
    li = [f for f in os.listdir(a.input) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    App(rt, li, a.input, a.output, load_dict(a.dict)); rt.mainloop()
