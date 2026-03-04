import os, torch, argparse, re
from PIL import Image
from pathlib import Path
from tqdm import tqdm
from Models import VisionModel
from torchvision.transforms import functional as TVF

def load_tags(p):
    with open(Path(p)/'top_tags.txt','r') as f: return [l.strip().lower() for l in f if l.strip()]
def load_bl(p):
    if not os.path.exists(p): return []
    with open(p,'r') as f: return [t.strip().lower() for t in f.read().replace(',','\n').split('\n') if t.strip()]
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
    p = argparse.ArgumentParser(); p.add_argument("--input"); p.add_argument("--output"); p.add_argument("--threshold",type=float); p.add_argument("--append"); p.add_argument("--blacklist"); p.add_argument("--rules")
    a = p.parse_args(); dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    mod = VisionModel.load_model('./models').to(dev).eval()
    top, bl, rl = load_tags('./models'), load_bl(a.blacklist), load_rl(a.rules)
    os.makedirs(a.output, exist_ok=True)
    imgs = [f for f in os.listdir(a.input) if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]
    for n in tqdm(imgs):
        raw = Image.open(os.path.join(a.input,n)).convert('RGB')
        sz = mod.image_size; mx = max(raw.size); pad = Image.new('RGB',(mx,mx),(255,255,255))
        pad.paste(raw,((mx-raw.size[0])//2,(mx-raw.size[1])//2))
        img = pad.resize((sz,sz),Image.BICUBIC)
        tns = TVF.normalize(TVF.to_tensor(img),[0.481,0.457,0.408],[0.268,0.261,0.275]).unsqueeze(0).to(dev)
        with torch.no_grad(): pr = torch.sigmoid(mod({'image':tns})['tags'])[0]
        cur = [top[i] for i,v in enumerate(pr) if v > a.threshold]
        cur = [t for t in cur if t not in bl]
        for r in rl:
            if all(c in cur for c in r['c']):
                if r['t']=='r' and r['tg'] in cur: cur = [r['n'] if x==r['tg'] else x for x in cur]
                elif r['t']=='d' and r['tg'] in cur: cur = [x for x in cur if x!=r['tg']]
        if a.append: cur.extend([x.strip().lower() for x in a.append.split(',')])
        with open(os.path.join(a.output,Path(n).with_suffix('.txt')),'w') as f: f.write(" ".join(list(dict.fromkeys(cur))))

if __name__=="__main__": main()
