import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import threading
import configparser
from pathlib import Path

# Config paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_DIR = SCRIPT_DIR  # python and models/
CONFIG_FILE = CONFIG_DIR / "config.ini"

class CustomizeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("R34 Tagger Settings")
        self.root.geometry("950x800")
        self.root.resizable(True, True)

        # Config file paths
        self.rules_path = CONFIG_DIR / "rules.txt"
        self.blacklist_path = CONFIG_DIR / "blacklist.txt"
        self.presets_path = CONFIG_DIR / "presets.txt"

        # Current settings
        self.threshold_var = tk.StringVar()
        self.extra_tags_var = tk.StringVar()
        self.filename_filters_var = tk.StringVar()
        self.api_user_id_var = tk.StringVar()
        self.api_key_var = tk.StringVar()
        self.max_posts_var = tk.StringVar()
        self.target_tag_var = tk.StringVar()

        # Load current values
        self.load_all()

        # Build UI
        self.build_ui()

    def load_all(self):
        """Load all config values, migrating from old locations if needed."""
        batch_path = PROJECT_DIR / "1. r34 tag.bat"

        # Threshold
        self.threshold_var.set(self._get_ini("batch", "threshold", "0.25"))
        if not self._get_ini_raw("batch", "threshold"):
            val = self._get_batch_val(batch_path, "THRESHOLD")
            if val: self.threshold_var.set(val)

        # Extra tags
        self.extra_tags_var.set(self._get_ini("extra_tags", "tags", "ai_generated joytag amiiari absurdres"))
        if not self._get_ini_raw("extra_tags", "tags"):
            val = self._get_batch_val(batch_path, "EXTRA_TAGS")
            if val: self.extra_tags_var.set(val)

        # Max posts
        self.max_posts_var.set(self._get_ini("batch", "max_posts", "2000"))
        if not self._get_ini_raw("batch", "max_posts"):
            val = self._get_batch_val(batch_path, "MAX_POSTS")
            if val: self.max_posts_var.set(val)

        # API credentials
        self.api_user_id_var.set(self._get_ini("api", "user_id", ""))
        self.api_key_var.set(self._get_ini("api", "api_key", ""))
        if not self._get_ini_raw("api", "user_id"):
            val = self._get_batch_val(batch_path, "API_USER_ID")
            if val: self.api_user_id_var.set(val)
        if not self._get_ini_raw("api", "api_key"):
            val = self._get_batch_val(batch_path, "API_KEY")
            if val: self.api_key_var.set(val)

        # Target tag
        target_path = CONFIG_DIR / "target_tag.txt"
        if target_path.exists():
            self.target_tag_var.set(target_path.read_text(encoding="utf-8").strip())
        else:
            self.target_tag_var.set(self._get_ini("target_tag", "tag", ""))

        # Filename filters
        filter_path = CONFIG_DIR / "filename_filters.txt"
        if filter_path.exists():
            self.filename_filters_var.set(filter_path.read_text(encoding="utf-8").strip())
        else:
            self.filename_filters_var.set(self._get_ini("filename_filters", "filters", ""))

    def _get_ini(self, section, key, default):
        try:
            cp = configparser.ConfigParser()
            cp.read(CONFIG_FILE, encoding="utf-8")
            return cp.get(section, key, fallback=default).strip()
        except Exception:
            return default

    def _get_ini_raw(self, section, key):
        """Check if a key exists in config.ini (not default)."""
        try:
            cp = configparser.ConfigParser()
            cp.read(CONFIG_FILE, encoding="utf-8")
            return cp.has_option(section, key)
        except Exception:
            return False

    def _get_batch_val(self, batch_path, var_name):
        """Read a variable from the batch file."""
        if not batch_path.exists():
            return ""
        for line in batch_path.read_text().splitlines():
            if line.strip().startswith(f"set {var_name}="):
                return line.split("=", 1)[1].strip().strip('"')
        return ""

    def save_api_credentials(self):
        """Save all settings to config.ini."""
        cp = configparser.ConfigParser()
        cp.read(CONFIG_FILE, encoding="utf-8")

        cp.set("batch", "threshold", self.threshold_var.get())
        cp.set("batch", "max_posts", self.max_posts_var.get())
        cp.set("api", "user_id", self.api_user_id_var.get())
        cp.set("api", "api_key", self.api_key_var.get())
        cp.set("extra_tags", "tags", self.extra_tags_var.get())
        cp.set("target_tag", "tag", self.target_tag_var.get())

        # Filename filters
        filters_text = self.filename_filters_var.get().strip()
        cp.set("filename_filters", "filters", filters_text)
        cp.write(open(CONFIG_FILE, 'w', encoding='utf-8'))

    def build_ui(self):
        # Main frame
        main_f = tk.Frame(self.root, bg="#1e1e1e")
        main_f.pack(fill="both", expand=True)

        # Top row: title + buttons
        top_row = tk.Frame(main_f, bg="#1e1e1e")
        top_row.pack(fill="x", padx=10, pady=5)

        title = tk.Label(top_row, text="R34 Tagger — Customize", font=("Segoe UI", 13, "bold"), bg="#1e1e1e", fg="#4ec9b0")
        title.pack(side="left")

        btn_frame = tk.Frame(top_row, bg="#1e1e1e")
        btn_frame.pack(side="right")
        ttk.Button(btn_frame, text="Save All", command=self.save_all).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Reset Threshold", command=self.reset_threshold).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Close", command=self.root.destroy).pack(side="right", padx=5)

        # Notebook area
        self.notebook = ttk.Notebook(main_f)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # --- Tab 1: General ---
        tab1 = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab1, text="General")

        ttk.Label(tab1, text="joytag accuracy or whatever", font=("Arial", 10, "bold")).pack(anchor="w")
        ttk.Label(tab1, text="this is for tag confidence, anything lower than it gets removed. i find 0.25 to be peak, you can experiment!").pack(anchor="w", pady=(0, 5))

        thresh_frame = ttk.Frame(tab1)
        thresh_frame.pack(fill="x", pady=5)

        ttk.Entry(thresh_frame, textvariable=self.threshold_var, width=10, font=("Consolas", 12)).pack(side="left", padx=(0, 10))
        ttk.Label(thresh_frame, text="0.01 to 1.0").pack(side="left")

        # API credentials
        ttk.Label(tab1, text="r34 api stuff yes", font=("Arial", 10, "bold")).pack(anchor="w", pady=(15, 5))
        ttk.Label(tab1, text="dont want to have these hardcoded so i dont leak my api key LMAO, i highly suggest adding yours for all features!").pack(anchor="w", pady=(0, 5))

        cred_frame = ttk.Frame(tab1)
        cred_frame.pack(fill="x", pady=(0, 5))

        uid_frame = ttk.Frame(cred_frame)
        uid_frame.pack(fill="x", pady=(0, 5))
        ttk.Label(uid_frame, text="Username:").pack(side="left", padx=(0, 5))
        ttk.Entry(uid_frame, textvariable=self.api_user_id_var, width=30, font=("Consolas", 10)).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(uid_frame, text="Clear", width=6, command=lambda: self.api_user_id_var.set("")).pack(side="left", padx=(0, 5))

        key_frame = ttk.Frame(cred_frame)
        key_frame.pack(fill="x")
        ttk.Label(key_frame, text="API Key:").pack(side="left", padx=(0, 5))
        ttk.Entry(key_frame, textvariable=self.api_key_var, width=30, font=("Consolas", 10), show="*").pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(key_frame, text="Clear", width=6, command=lambda: self.api_key_var.set("")).pack(side="left", padx=(0, 5))

        # Filename filters
        ttk.Label(tab1, text="suffix filter", font=("Arial", 10, "bold")).pack(anchor="w", pady=(15, 5))
        ttk.Label(tab1, text="one per line! say your watermarked image is -tag, it ignores images with that suffix wow. leave empty to process all images.").pack(anchor="w", pady=(0, 5))

        self.filter_text = tk.Text(tab1, font=("Consolas", 11), height=4, wrap="word", padx=8, pady=8)
        self.filter_text.pack(fill="x", pady=(0, 10))
        self.filter_text.insert("1.0", self.filename_filters_var.get())

        # Max posts setting
        max_posts_top = ttk.Frame(tab1)
        max_posts_top.pack(fill="x", pady=(15, 5))
        ttk.Label(max_posts_top, text="post search limit", font=("Arial", 10, "bold")).pack(side="left", anchor="w")
        ttk.Label(max_posts_top, text="i think about 7,000 new posts per day! wow! takes ~98 seconds to refresh with a day's data. ~114 minutes for a week's worth.", foreground="#888").pack(side="left", padx=(10, 0))

        max_posts_frame = ttk.Frame(tab1)
        max_posts_frame.pack(fill="x", pady=(0, 10))
        ttk.Entry(max_posts_frame, textvariable=self.max_posts_var, width=10, font=("Consolas", 12)).pack(side="left", padx=(0, 10))
        ttk.Label(max_posts_frame, text="posts").pack(side="left")

        # Constant tags
        extra_top = ttk.Frame(tab1)
        extra_top.pack(fill="x", pady=(15, 5))
        ttk.Label(extra_top, text="these tags are appended to every image!", font=("Arial", 10, "bold")).pack(side="left", anchor="w")
        ttk.Label(extra_top, text="space-separated, e.g. amiiari ai_generated absurdres <-- thats what i do yeah", foreground="#888").pack(side="left", padx=(10, 0))

        extra_frame = ttk.Frame(tab1)
        extra_frame.pack(fill="x", pady=(0, 10))
        ttk.Entry(extra_frame, textvariable=self.extra_tags_var, width=50, font=("Consolas", 11)).pack(fill="x", padx=(0, 5))

        # Update Tags button
        update_top = ttk.Frame(tab1)
        update_top.pack(fill="x", pady=(10, 0))
        ttk.Label(update_top, text="update the master r34 tag list, its way over there so yeah ->", font=("Arial", 10, "bold")).pack(side="left", anchor="w")
        ttk.Button(update_top, text="run tag update", command=self.run_update).pack(side="right", padx=(0, 10))

        # Target tag/franchise
        target_top = ttk.Frame(tab1)
        target_top.pack(fill="x", pady=(10, 5))
        ttk.Label(target_top, text="target tag refresh", font=("Arial", 10, "bold")).pack(side="left", anchor="w")
        ttk.Label(target_top, text="instead of scanning all! you can say only scan posts from wuthering_waves, or yourself! it'll get all the characters that way! ").pack(side="left", padx=(10, 0))

        target_frame = ttk.Frame(tab1)
        target_frame.pack(fill="x", pady=(0, 10))
        self.target_tag_var = tk.StringVar()
        ttk.Entry(target_frame, textvariable=self.target_tag_var, width=30, font=("Consolas", 10)).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Label(target_frame, text="aah omg you must click save after typing GULP").pack(side="left")

        # --- Tab 2: Rules ---
        tab2 = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab2, text="Rules")

        ttk.Label(tab2, text="Conditional Tag Rules", font=("Arial", 10, "bold")).pack(anchor="w")
        ttk.Label(tab2, text="format: IF (conditions) REPLACE (old) WITH (new) or IF (conditions) DELETE (tag). Use # for section headers.", foreground="#888").pack(anchor="w", pady=(0, 10))

        self.rules_text = tk.Text(tab2, font=("Consolas", 11), height=18, wrap="word", padx=8, pady=8)
        self.rules_text.pack(fill="both", expand=True)
        self.load_rules_to_text()

        # --- Tab 3: Blacklist ---
        tab3 = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab3, text="Blacklist")

        ttk.Label(tab3, text="Tags to Exclude", font=("Arial", 10, "bold")).pack(anchor="w")
        ttk.Label(tab3, text="One tag per line. Use # for comments, dont use spaces, i think bad.").pack(anchor="w", pady=(0, 5))

        self.bl_text = tk.Text(tab3, font=("Consolas", 11), height=18, wrap="word", padx=8, pady=8)
        self.bl_text.pack(fill="both", expand=True)
        self.load_blacklist_to_text()

        # --- Tab 4: Presets ---
        tab4 = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab4, text="Presets")

        ttk.Label(tab4, text="Tag Presets", font=("Arial", 10, "bold")).pack(anchor="w")
        ttk.Label(tab4, text="LMFAO I WONT LIE this is REALLY UGLY BUT yeah...", foreground="#888").pack(anchor="w", pady=(0, 10))

        self.presets_text = tk.Text(tab4, font=("Consolas", 11), height=18, wrap="word", padx=8, pady=8)
        self.presets_text.pack(fill="both", expand=True)
        self.load_presets_to_text()

    def load_rules_to_text(self):
        if self.rules_path.exists():
            self.rules_text.delete("1.0", tk.END)
            self.rules_text.insert("1.0", self.rules_path.read_text(encoding="utf-8"))

    def load_blacklist_to_text(self):
        if self.blacklist_path.exists():
            self.bl_text.delete("1.0", tk.END)
            self.bl_text.insert("1.0", self.blacklist_path.read_text(encoding="utf-8"))

    def load_presets_to_text(self):
        if self.presets_path.exists():
            self.presets_text.delete("1.0", tk.END)
            self.presets_text.insert("1.0", self.presets_path.read_text(encoding="utf-8"))

    def load_filename_filters_to_text(self):
        filter_path = CONFIG_DIR / "filename_filters.txt"
        if filter_path.exists():
            self.filter_text.delete("1.0", tk.END)
            self.filter_text.insert("1.0", filter_path.read_text(encoding="utf-8"))

    def save_all(self):
        # Save rules
        self.rules_path.write_text(self.rules_text.get("1.0", tk.END).strip() + "\n", encoding="utf-8")

        # Save blacklist
        self.blacklist_path.write_text(self.bl_text.get("1.0", tk.END).strip() + "\n", encoding="utf-8")

        # Save presets
        self.presets_path.write_text(self.presets_text.get("1.0", tk.END).strip() + "\n", encoding="utf-8")

        # Save main config (threshold, max_posts, api, extra_tags, target_tag, filters)
        self.save_api_credentials()

        # Update filename filters from text widget
        self.filename_filters_var.set(self.filter_text.get("1.0", tk.END).strip())

        messagebox.showinfo("Saved", "All settings saved to config.ini!", parent=self.root)

    def reset_threshold(self):
        self.threshold_var.set("0.25")

    def run_update(self):
        # Save target tag to config
        cp = configparser.ConfigParser()
        cp.read(CONFIG_FILE, encoding="utf-8")
        cp.set("target_tag", "tag", self.target_tag_var.get().strip())
        cp.write(open(CONFIG_FILE, 'w', encoding='utf-8'))

        import subprocess
        update_script = CONFIG_DIR / "models" / "refresh_tags.bat"
        if update_script.exists():
            subprocess.Popen([str(update_script)], shell=True)
        else:
            messagebox.showerror("Error", "refresh_tags.bat not found!", parent=self.root)


if __name__ == "__main__":
    root = tk.Tk()
    app = CustomizeApp(root)
    root.mainloop()
