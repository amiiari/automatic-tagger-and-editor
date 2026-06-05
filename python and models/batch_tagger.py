import os, torch, argparse, re, csv, warnings, configparser
from PIL import Image
from pathlib import Path
from tqdm import tqdm
from Models import VisionModel
from torchvision.transforms import functional as TVF

warnings.filterwarnings("ignore", category=FutureWarning)

Image.MAX_IMAGE_PIXELS = 300000000
CONFIG_DIR = Path(__file__).resolve().parent
CONFIG_FILE = CONFIG_DIR / "config.ini"

def load_suffix_ignore():
    """Load filename suffixes to ignore from config.ini [suffix_ignore]."""
    try:
        cp = configparser.ConfigParser()
        cp.read(CONFIG_FILE, encoding="utf-8")
        text = cp.get("suffix_ignore", "tags", fallback="").strip()
        # Support both comma-separated and newline-separated formats
        if "," in text:
            return [s.strip().lower() for s in text.split(",") if s.strip()]
        return [s.strip().lower() for s in text.splitlines() if s.strip()]
    except Exception:
        return []

# Alias for compatibility
load_filename_filters = load_suffix_ignore


def load_tags(p):
    with open(Path(p)/'top_tags.txt','r') as f: return [l.strip().lower() for l in f if l.strip()]

def load_bl(p):
    if not os.path.exists(p): return set()
    with open(p,'r', encoding='utf-8') as f: 
        return {t.strip().lower() for t in f.read().replace(',','\n').split() if t.strip()}

def load_master_csv_bl(p):
    bl_set = set()
    if not os.path.exists(p): 
        print(f"[WARN] Master taglist not found at {p}")
        return bl_set
    
    # Exclude: Artist(1), Copyright(3), Character(4), Meta(5)
    exclude_types = {'1', '3', '4', '5'}
    
    with open(p, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                name = row[0].strip().lower().replace(" ", "_")
                t_type = row[1].strip()
                if t_type in exclude_types:
                    bl_set.add(name)
    return bl_set

def load_discovery_whitelist_bl(p):
    """Load discovery whitelist as blacklist (general tags we don't want in auto output)."""
    if not os.path.exists(p): return set()
    with open(p, 'r', encoding='utf-8') as f:
        return {t.strip().lower() for t in f.read().splitlines() if t.strip()}

def load_rl(p):
    rs = []
    if not os.path.exists(p): return rs
    rp = re.compile(r"IF \((.*)\) REPLACE \((.*)\) WITH \((.*)\)", re.IGNORECASE)
    dm = re.compile(r"IF \((.*)\) DELETE \((.*)\)", re.IGNORECASE)
    with open(p,'r') as f:
        for l in f:
            l = l.strip(); m1 = rp.match(l); m2 = dm.match(l)
            if m1: rs.append({'t':'r','c':[x.strip().lower() for x in m1.group(1).split(',')], 'tg':m1.group(2).strip().lower(), 'n':m1.group(3).strip().lower()})
            elif m2: rs.append({'t':'d','c':[x.strip().lower() for x in m2.group(1).split(',')], 'tg':m2.group(2).strip().lower()})
    return rs

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--threshold", type=float)
    p.add_argument("--append", help="Extra tags string from batch file")
    p.add_argument("--blacklist")
    p.add_argument("--master_taglist")
    p.add_argument("--rules")
    p.add_argument("--config", default=None)
    
    a = p.parse_args()
    
    # Load config if not overridden by args
    if a.threshold is None:
        try:
            cp = configparser.ConfigParser()
            cp.read(CONFIG_FILE, encoding="utf-8")
            a.threshold = float(cp.get("batch", "threshold", fallback="0.35"))
        except Exception:
            a.threshold = 0.35
    
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    mod = VisionModel.load_model('./models').to(dev).eval()
    
    top = load_tags('./models')
    rl = load_rl(a.rules)
    bl = load_bl(a.blacklist)
    
    if a.master_taglist:
        print(f"[INFO] Filtering Artist/Char/Meta using {a.master_taglist}...")
        bl.update(load_master_csv_bl(a.master_taglist))

    # Also filter out discovery whitelist general tags
    wl_path = Path(__file__).resolve().parent / "models" / "discovery_whitelist.txt"
    wl_bl = load_discovery_whitelist_bl(wl_path)
    bl.update(wl_bl)
    print(f"[INFO] Also filtering {len(wl_bl)} discovery whitelist general tags...")

    os.makedirs(a.output, exist_ok=True)
    
    # Load suffix ignore list
    suffix_ignore = load_suffix_ignore()
    
    # Get default image extensions
    default_suffixes = ('.png','.jpg','.jpeg','.webp')
    
    # Filter images
    imgs = []
    for f in os.listdir(a.input):
        ext = Path(f).suffix.lower()
        if ext not in default_suffixes:
            continue
        
        # Check suffix ignore list (match against stem, not full filename)
        stem = os.path.splitext(f)[0].lower()
        skip = False
        for suffix in suffix_ignore:
            if stem.endswith(suffix):
                skip = True
                break
        if skip:
            continue
            
        imgs.append(f)
    
    for n in tqdm(imgs):
        try:
            raw = Image.open(os.path.join(a.input,n)).convert('RGB')
            sz = mod.image_size; mx = max(raw.size); pad = Image.new('RGB',(mx,mx),(255,255,255))
            pad.paste(raw,((mx-raw.size[0])//2,(mx-raw.size[1])//2))
            img = pad.resize((sz,sz),Image.BICUBIC)
            tns = TVF.normalize(TVF.to_tensor(img),[0.481,0.457,0.408],[0.268,0.261,0.275]).unsqueeze(0).to(dev)
            
            with torch.no_grad(): 
                pr = torch.sigmoid(mod({'image':tns})['tags'])[0]
            
            cur = [top[i] for i,v in enumerate(pr) if v > a.threshold]
            cur = [t for t in cur if t not in bl]
            
            # Rules logic
            for r in rl:
                if all(c in cur for c in r['c']):
                    if r['t']=='r' and r['tg'] in cur: cur = [r['n'] if x==r['tg'] else x for x in cur]
                    elif r['t']=='d' and r['tg'] in cur: cur = [x for x in cur if x!=r['tg']]
            
            # Append logic: read from config.ini
            extra = []
            try:
                cp = configparser.ConfigParser()
                cp.read(CONFIG_FILE, encoding="utf-8")
                tags_str = cp.get("extra_tags", "tags", fallback="")
                extra = [t.strip() for t in tags_str.split() if t.strip()]
            except Exception:
                pass
            
            for ex in extra:
                tag = ex.strip().lower().replace(',', '')
                if tag not in cur: cur.append(tag)
            
            # Save logic: Space separated, no commas
            final = [t.replace(' ', '_').replace(',', '') for t in list(dict.fromkeys(cur))]
            out_p = os.path.join(a.output, Path(n).stem + ".txt")
            with open(out_p, 'w', encoding='utf-8') as f:
                f.write(" ".join(final))

        except Exception as e:
            print(f"[ERR] Error on {n}: {e}")

if __name__=="__main__": 
    main()
