import os, torch, argparse, re, csv
from PIL import Image
from pathlib import Path
from tqdm import tqdm
from Models import VisionModel
from torchvision.transforms import functional as TVF

def load_tags(p):
    with open(Path(p)/'top_tags.txt','r') as f: return [l.strip().lower() for l in f if l.strip()]

def load_bl(p):
    if not os.path.exists(p): return set()
    with open(p,'r', encoding='utf-8') as f: 
        return {t.strip().lower() for t in f.read().replace(',','\n').split() if t.strip()}

def load_master_csv_bl(p):
    bl_set = set()
    if not os.path.exists(p): 
        print(f"⚠️ Warning: Master taglist not found at {p}")
        return bl_set
    
    # Exclude: Artist(1), Copyright(3), Character(4), Meta(5)
    exclude_types = {'1', '2', '3', '4', '5'}
    
    with open(p, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                name = row[0].strip().lower().replace(" ", "_")
                t_type = row[1].strip()
                if t_type in exclude_types:
                    bl_set.add(name)
    return bl_set

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
    p.add_argument("--threshold", type=float, default=0.35)
    p.add_argument("--append", help="Extra tags string from batch file")
    p.add_argument("--blacklist")
    p.add_argument("--master_taglist")
    p.add_argument("--rules")
    
    a = p.parse_args()
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    mod = VisionModel.load_model('./models').to(dev).eval()
    
    top = load_tags('./models')
    rl = load_rl(a.rules)
    bl = load_bl(a.blacklist)
    
    if a.master_taglist:
        print(f"📂 Filtering Artist/Char/Meta using {a.master_taglist}...")
        bl.update(load_master_csv_bl(a.master_taglist))

    os.makedirs(a.output, exist_ok=True)
    imgs = [f for f in os.listdir(a.input) if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]
    
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
            
            # Append logic (handles the space-separated string from your .bat)
            if a.append:
                extra = a.append.strip('"').split()
                for ex in extra:
                    tag = ex.strip().lower().replace(',', '')
                    if tag not in cur: cur.append(tag)
            
            # Save logic: Space separated, no commas
            final = [t.replace(' ', '_').replace(',', '') for t in list(dict.fromkeys(cur))]
            out_p = os.path.join(a.output, Path(n).stem + ".txt")
            with open(out_p, 'w', encoding='utf-8') as f:
                f.write(" ".join(final))

        except Exception as e:
            print(f"⚠️ Error on {n}: {e}")

if __name__=="__main__": 
    main()
