import os, torch, argparse, re, csv, warnings, configparser
from collections import Counter
from PIL import Image
from pathlib import Path
from tqdm import tqdm

warnings.filterwarnings("ignore", category=FutureWarning)

Image.MAX_IMAGE_PIXELS = 300000000
CONFIG_DIR = Path(__file__).resolve().parent
CONFIG_FILE = CONFIG_DIR / "config.ini"

WD_REPO = "SmilingWolf/wd-eva02-large-tagger-v3"


def cfg_get(section, key, fallback=""):
    try:
        cp = configparser.ConfigParser()
        cp.read(CONFIG_FILE, encoding="utf-8")
        return cp.get(section, key, fallback=fallback)
    except Exception:
        return fallback


def load_suffix_ignore():
    """Load filename suffixes to ignore from config.ini [suffix_ignore]."""
    text = cfg_get("suffix_ignore", "tags").strip()
    if "," in text:
        return [s.strip().lower() for s in text.split(",") if s.strip()]
    return [s.strip().lower() for s in text.splitlines() if s.strip()]


def load_bl(p):
    if not p or not os.path.exists(p): return set()
    with open(p, 'r', encoding='utf-8') as f:
        return {t.strip().lower() for t in f.read().replace(',', '\n').split() if t.strip()}


def load_master_csv_bl(p):
    """Artist(1)/Copyright(3)/Character(4)/Meta(5) names -> blacklist."""
    bl_set = set()
    exclude_types = {'1', '3', '4', '5'}
    with open(p, 'r', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[1].strip() in exclude_types:
                bl_set.add(row[0].strip().lower().replace(" ", "_"))
    return bl_set


def load_r34_general(p):
    """The user's R34 database: general (type 0) tag -> post count. This is the
    ONLY vocabulary that may appear in the auto output - anything the model
    says that has no R34 spelling gets dropped, so posts never carry tags
    that don't exist on the site."""
    vocab = {}
    with open(p, 'r', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) >= 3 and row[1].strip() == '0':
                name = row[0].strip().lower().replace(" ", "_")
                try:
                    vocab[name] = int(row[2])
                except ValueError:
                    vocab[name] = 0
    return vocab


def load_r34_full(p):
    """name -> [type, count] for every row - needed to tell 'meta on r34'
    apart from 'not on r34 at all'."""
    full = {}
    with open(p, 'r', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) >= 3:
                try:
                    full[row[0].strip().lower()] = [int(row[1]), int(row[2])]
                except ValueError:
                    continue
    return full


class TagLearner:
    """Self-healing vocabulary: the seed scrape missed real tags (flaccid has
    153k posts and wasn't in the DB). An unknown prediction gets ONE live API
    lookup; if R34 confirms it, it's appended to master_taglist.csv for good."""

    def __init__(self, csv_path, creds, vocab, full):
        self.csv_path, self.creds = csv_path, creds
        self.vocab, self.full = vocab, full
        self.cache, self.added = {}, []

    def lookup(self, tag):
        if tag in self.cache:
            return self.cache[tag]
        import time
        import urllib.parse
        import urllib.request
        info = None
        url = ("https://api.rule34.xxx/index.php?page=dapi&s=tag&q=index"
               f"&name={urllib.parse.quote(tag)}&limit=1{self.creds}")
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                xml = r.read().decode("utf-8", "replace")
            m = re.search(r'type="(\d+)"\s+count="(\d+)"\s+name="' + re.escape(tag) + '"', xml)
            if m:
                info = [int(m.group(1)), int(m.group(2))]
        except Exception:
            self.cache[tag] = None
            return None   # network hiccup: drop this run, retry next run
        time.sleep(0.5)   # gentle pacing - never risk the key's rate limit
        self.cache[tag] = info
        if info:
            self.full[tag] = info
            if info[0] == 0:
                self.vocab[tag] = info[1]
            try:
                with open(self.csv_path, "a", encoding="utf-8", newline="") as f:
                    csv.writer(f).writerow([tag, info[0], info[1]])
                self.added.append(tag)
            except OSError:
                pass
        return info


def r34_variants(tag):
    """Mechanical spelling variants between danbooru and R34 conventions:
    plural toggle (1girl/1girls) and big/large swap (large_breasts/big_breasts).
    The R34 post counts decide which variant wins."""
    out = {tag}
    for t in list(out):
        out.add(t + "s")
        if t.endswith("s"):
            out.add(t[:-1])
    for t in list(out):
        if "large" in t:
            out.add(t.replace("large", "big"))
        if "big" in t:
            out.add(t.replace("big", "large"))
    return out


def canonicalize(tags, vocab, dropped, full=None, keep_meta=(), learner=None):
    """Map each predicted tag onto the highest-count R34 spelling. Unknown tags
    get a live API lookup (learner) before being dropped; meta-typed tags pass
    only if allow-listed in keep_meta (e.g. uncensored)."""
    final = []
    for t in tags:
        cands = [(vocab[v], v) for v in r34_variants(t) if v in vocab]
        if not cands:
            info = (full or {}).get(t)
            if info is None and learner is not None:
                info = learner.lookup(t)   # may add it to vocab/full for good
                if info and info[0] == 0:
                    cands = [(info[1], t)]
            if not cands:
                if info and info[0] == 5 and t in keep_meta:
                    cands = [(info[1], t)]
                else:
                    dropped[t] += 1
                    continue
        best = max(cands)[1]
        if best not in final:
            final.append(best)
    return final


def load_discovery_whitelist_bl(p):
    """Discovery whitelist doubles as a blacklist for the AUTO output (these
    generals belong to the manual preset flow, not automatic tagging)."""
    if not os.path.exists(p): return set()
    with open(p, 'r', encoding='utf-8') as f:
        return {t.strip().lower() for t in f.read().splitlines() if t.strip()}


def load_rl(p):
    rs = []
    if not p or not os.path.exists(p): return rs
    rp = re.compile(r"IF \((.*)\) REPLACE \((.*)\) WITH \((.*)\)", re.IGNORECASE)
    dm = re.compile(r"IF \((.*)\) DELETE \((.*)\)", re.IGNORECASE)
    with open(p, 'r') as f:
        for l in f:
            l = l.strip(); m1 = rp.match(l); m2 = dm.match(l)
            if m1: rs.append({'t': 'r', 'c': [x.strip().lower() for x in m1.group(1).split(',')], 'tg': m1.group(2).strip().lower(), 'n': m1.group(3).strip().lower()})
            elif m2: rs.append({'t': 'd', 'c': [x.strip().lower() for x in m2.group(1).split(',')], 'tg': m2.group(2).strip().lower()})
    return rs


def pad_square(img, fill=(255, 255, 255)):
    mx = max(img.size)
    pad = Image.new('RGB', (mx, mx), fill)
    pad.paste(img, ((mx - img.size[0]) // 2, (mx - img.size[1]) // 2))
    return pad


class WDTagger:
    """SmilingWolf/wd-eva02-large-tagger-v3 via timm (danbooru-2024, 10861
    tags). Only its GENERAL predictions are used - characters stay the manual
    preset flow's job, ratings are irrelevant here."""

    def __init__(self, device):
        import timm
        from timm.data import create_transform, resolve_data_config
        from huggingface_hub import hf_hub_download
        print(f"[INFO] Loading {WD_REPO} (first run downloads ~1.2GB)...")
        self.model = timm.create_model("hf-hub:" + WD_REPO, pretrained=True).to(device).eval()
        self.transform = create_transform(**resolve_data_config(self.model.pretrained_cfg, model=self.model))
        self.device = device
        self.names, self.general_idx = [], []
        with open(hf_hub_download(WD_REPO, "selected_tags.csv"), encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                self.names.append(row["name"].strip().lower())
                if row["category"].strip() == "0":
                    self.general_idx.append(i)

    def tag(self, raw, threshold):
        x = self.transform(pad_square(raw)).unsqueeze(0)
        x = x[:, [2, 1, 0]]   # RGB -> BGR: WD models are BGR-trained
        with torch.no_grad():
            probs = torch.sigmoid(self.model(x.to(self.device)))[0].cpu()
        return [self.names[i] for i in self.general_idx if probs[i] > threshold]


def main():
    p = argparse.ArgumentParser()
    # --input/--output/--append-map are REPEATABLE: pass one triple per set and
    # the model loads once for the whole batch instead of paying a cold CUDA
    # start per folder. A single pair behaves exactly as it always did.
    p.add_argument("--input", required=True, action="append")
    p.add_argument("--output", required=True, action="append")
    p.add_argument("--threshold", type=float)
    p.add_argument("--append", help="Extra tags string from batch file")
    p.add_argument("--append-map", action="append",
                   help="JSON file {image stem: 'tags'} - per-IMAGE tags "
                   "(characters) appended only to that image's txt. Repeat it "
                   "alongside --input; '' means this set has none. Stems repeat "
                   "across sets (every set has a 1r1), so the maps must stay "
                   "per-set - one merged map would cross-contaminate them.")
    p.add_argument("--blacklist")
    p.add_argument("--master_taglist")
    p.add_argument("--rules")
    p.add_argument("--config", default=None)
    a = p.parse_args()

    if a.threshold is None:
        try:
            a.threshold = float(cfg_get("batch", "wd_threshold", "0.35"))
        except ValueError:
            a.threshold = 0.35

    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"[INFO] wd-eva02-large-v3  threshold={a.threshold}  device={dev}")
    tagger = WDTagger(dev)

    rl = load_rl(a.rules)
    bl = load_bl(a.blacklist)

    vocab, full, learner = {}, {}, None
    keep_meta = {t.strip().lower() for t in
                 re.split(r"[,\s]+", cfg_get("batch", "keep_meta", "uncensored")) if t.strip()}
    if a.master_taglist and os.path.exists(a.master_taglist):
        vocab = load_r34_general(a.master_taglist)
        full = load_r34_full(a.master_taglist)
        bl.update(load_master_csv_bl(a.master_taglist))
        print(f"[INFO] R34 vocabulary: {len(vocab)} general tags - output is filtered to these")
        # keep_meta must beat the meta blacklist too, or uncensored survives
        # canonicalize only to die one stage later
        bl.difference_update(keep_meta)
        creds = cfg_get("api", "api_key", "").strip()
        if creds:
            learner = TagLearner(a.master_taglist, creds, vocab, full)
            print(f"[INFO] Unknown tags get a live R34 lookup and are learned into the DB")
    else:
        print("[WARN] No master taglist - output will NOT be R34-filtered!")

    if vocab:
        # The tag stream is canonicalized to R34 spellings BEFORE the blacklist
        # and rules run - so translate those too, or a rule written as
        # "IF (1girl, ...)" would silently never fire again once the stream
        # says 1girls. Both spellings stay active.
        def canon_one(t):
            cands = [(vocab[v], v) for v in r34_variants(t) if v in vocab]
            return max(cands)[1] if cands else t
        bl |= {canon_one(t) for t in bl}
        for r in rl:
            r['c'] = [canon_one(x) for x in r['c']]
            r['tg'] = canon_one(r['tg'])
            if r['t'] == 'r':
                r['n'] = canon_one(r['n'])

    wl_bl = load_discovery_whitelist_bl(Path(__file__).resolve().parent / "models" / "discovery_whitelist.txt")
    bl.update(wl_bl)
    print(f"[INFO] Also filtering {len(wl_bl)} discovery whitelist general tags...")

    suffix_ignore = load_suffix_ignore()

    extra = [t.strip().lower().replace(',', '') for t in cfg_get("extra_tags", "tags").split() if t.strip()]
    # --append = per-SET tags (character/copyright...) handed in by the caller;
    # baked into every txt so a re-run never loses them
    extra += [t.strip().lower().replace(',', '') for t in (a.append or "").split() if t.strip()]
    dropped = Counter()

    # one (input, output, append-map) triple per set; the model above is already
    # loaded and is reused across every one of them
    maps = list(a.append_map or [])
    maps += [None] * (len(a.input) - len(maps))
    sets = list(zip(a.input, a.output, maps))
    for si, (in_dir, out_dir, map_path) in enumerate(sets, 1):
        os.makedirs(out_dir, exist_ok=True)

        imgs = []
        for f in os.listdir(in_dir):
            if Path(f).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
                continue
            stem = os.path.splitext(f)[0].lower()
            if any(stem.endswith(suffix) for suffix in suffix_ignore):
                continue
            imgs.append(f)
        if len(sets) > 1:
            print(f"[SET {si}/{len(sets)}] {os.path.basename(in_dir.rstrip(chr(92) + '/'))} "
                  f"- {len(imgs)} image(s)", flush=True)

        # --append-map = per-IMAGE tags (a set can hold multiple characters, so
        # character tags belong to specific images, not the whole set)
        amap = {}
        if map_path and os.path.exists(map_path):
            import json
            try:
                with open(map_path, encoding="utf-8") as f:
                    amap = {str(k).lower(): [t.strip().lower().replace(',', '') for t in str(v).split() if t.strip()]
                            for k, v in json.load(f).items()}
                print(f"[INFO] Per-image tags for {len(amap)} image(s) ride along this set")
            except Exception as e:
                print(f"[WARN] Could not read --append-map: {e}")

        for n in tqdm(imgs, ascii=True):
            try:
                raw = Image.open(os.path.join(in_dir, n)).convert('RGB')
                cur = tagger.tag(raw, a.threshold)

                # 1. R34 spelling: highest-count variant wins (1girl -> 1girls,
                #    large_breasts -> big_breasts); unknown tags get a live lookup
                #    and are learned; only genuinely-not-on-R34 tags are dropped
                if vocab:
                    cur = canonicalize(cur, vocab, dropped, full, keep_meta, learner)
                # 2. blacklists (user's + artist/char/copyright/meta + whitelist)
                cur = [t for t in cur if t not in bl]
                # 3. conditional rules
                for r in rl:
                    if all(c in cur for c in r['c']):
                        if r['t'] == 'r' and r['tg'] in cur: cur = [r['n'] if x == r['tg'] else x for x in cur]
                        elif r['t'] == 'd' and r['tg'] in cur: cur = [x for x in cur if x != r['tg']]
                # 4. extra tags (never filtered - they're deliberate); per-image
                #    tags from --append-map land last, after the set-wide ones
                for ex in extra + amap.get(Path(n).stem.lower(), []):
                    if ex not in cur: cur.append(ex)

                final = [t.replace(' ', '_').replace(',', '') for t in dict.fromkeys(cur)]
                with open(os.path.join(out_dir, Path(n).stem + ".txt"), 'w', encoding='utf-8') as f:
                    f.write(" ".join(final))
            except Exception as e:
                print(f"[ERR] Error on {n}: {e}")

    if learner and learner.added:
        print(f"[INFO] Learned {len(learner.added)} new tag(s) from R34 into the master taglist: "
              + ", ".join(learner.added))
    if dropped:
        top = ", ".join(f"{t}×{c}" for t, c in dropped.most_common(15))
        print(f"[INFO] {sum(dropped.values())} tag hits dropped (confirmed not usable on R34). Most common: {top}")


if __name__ == "__main__":
    main()
