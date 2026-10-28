"""Build src/isnady/assets/scholars/huffaz.json from al-Dhahabi's Tadhkirat al-Huffaz (HFZ1, 2026-10-27).

Bayram (2026-10-27): "hadis alimleri az mi? … neden daha eskilerden (islamin 2-3 yuzyilinda ki) alimleri bu kadar az"
— the list of the imams and huffaz of hadith is al-Dhahabi's own (1,176 in 21 generations, from the Companions to his
teachers), not chosen by isnady.

    python tools/build_huffaz.py TADHKIRA.mARkdown ISNADY.db

TADHKIRA: the OpenITI text 0748Dhahabi.TadhkiratHuffaz.JK000532-ara1.mARkdown (OpenITI/0750AH). ISNADY.db: a database
with Ibn Hajar's Taqrib imported, to tie each hafiz to his Taqrib entry. What is kept is an index — the number, the
generation, the name as al-Dhahabi heads the entry, the sigla of the six books, the year of death read from the
entry, the Taqrib key — never the text (OpenITI gives no licence: the text is downloaded by the reader, on request).

A hafiz is tied to a Taqrib narrator only on evidence: his name and father (and grandfather) as the entry gives them,
the man of the entry (not one it mentions), the years of death within three years — or within fifteen with the
grandfather too —, no other candidate the entry names more fully, no other father or grandfather given; three
Companions by hand (Abu Dharr, 'A'isha, Abu Hurayra). Nothing else is guessed: the rest stay without a link.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from isnady.core.normalize import normalize
from isnady.core.rijal import parse_year_words
text=open(sys.argv[1],encoding="utf-8").read().split("#META#Header#End#",1)[-1]
MARK=re.compile(r"PageV\d+P\d+|ms\d+")
lines=text.split("\n")
tab=0; tabname=""; out=[]; cur=None
ORD=["الأولى","الثانية","الثالثة","الرابعة","خامسة","السادسة","السابعة","الثامنة","التاسعة","العاشرة","الحادية عشرة","الثانية عشرة","الثالثة عشرة","الرابعة عشرة","الخامسة عشرة","السادسة عشرة","السابعة عشرة","الثامنة عشرة","التاسعة عشرة","العشرون","الحادية والعشرون"]
seen_first=False
for ln in lines:
    if ln.startswith("### |"):
        h=MARK.sub("",ln[5:]).strip(" |()")
        if "شيوخ صاحب التذكرة" in h: tab=22; tabname=h; continue
        if "طبقة أخرى صغرى" in h: tabname=h; continue   # a smaller layer inside the 13th
        for i,o in sorted(enumerate(ORD), key=lambda x: -len(x[1])):
            if o in h and ("الطبقة" in h or "طبقة" in h):
                cand=i+1
                if cand==1 and seen_first: break
                if cand>=tab or tab==0: tab=cand; tabname=h
                seen_first = seen_first or cand==1
                break
        continue
    m=re.match(r"^### \$+ (\d+)\s*(.*)$", ln)
    if m:
        cur={"n":int(m.group(1)),"tabaqa":tab,"head":MARK.sub("",m.group(2)).strip(),"text":""}
        out.append(cur); continue
    if cur is not None:
        cur["text"]+=" "+MARK.sub("",re.sub(r"^~~|^# ","",ln))
raw=out

from isnady.core.normalize import normalize
from isnady.core.rijal import parse_year_words
RUMUZ_RE=re.compile(r"^((?:(?:ع|خ|م|د|ت|س|ق|4|خت|بخ|مد|تم|سي|كن|ص|عس|فق|ل|قد|ر|ي|مق|جز|ف|خد)\s+)+)")
UNITS={"اثنتي":2,"اثني":2,"اثنا":2,"ثنتي":2,"احدي":1,"احد":1,"واحد":1,"اثنتين":2,"اثنين":2,"ثنتين":2,"ثلاث":3,"اربع":4,"خمس":5,"ست":6,"سته":6,"ستة":6,"سبع":7,"ثمان":8,"ثماني":8,"ثمانيه":8,"تسع":9}
TENS={"عشر":10,"عشره":10,"عشرين":20,"ثلاثين":30,"اربعين":40,"خمسين":50,"ستين":60,"سبعين":70,"ثمانين":80,"تسعين":90}
HUND={"مايه":100,"ماييه":100,"مائه":100,"مايتين":200,"مائتين":200}
for k,v in list(UNITS.items()):
    if v>=3: HUND[k+"مايه"]=v*100; HUND[k+"مائه"]=v*100
def number_words(w):
    total=0; hundreds=False; unit_before_ten=0
    for tok in w.split():
        t=normalize(tok)
        t=t[1:] if t.startswith("و") and len(t)>3 and t[1:] in {**UNITS,**TENS,**HUND} else t
        if t in HUND: total+=HUND[t]; hundreds=True
        elif t in TENS:
            total+=TENS[t]
        elif t in UNITS: total+=UNITS[t]
        else: break
    return (total or None), hundreds
RANGE={1:(8,60),2:(25,110),3:(60,135),4:(95,165),5:(115,195),6:(140,225),7:(165,245),8:(185,275),9:(215,305),10:(245,335),11:(275,365),12:(305,405),13:(335,440),14:(370,490),15:(395,530),16:(440,565),17:(470,610),18:(510,660),19:(550,705),20:(590,745),21:(620,770)}
def year(text, tabaqa):
    lo,hi=RANGE.get(tabaqa,(1,800))
    for m in re.finditer(r"(?:مات|توفي|توفى|قتل|استشهد|وفاته|توفاه)[^.]{0,90}?سنة ([^.،؛:\(\)\d]{3,60})", text):
        w=re.sub(r"(ثلاث|أربع|اربع|خمس|ست|سبع|ثمان|تسع)\s+(مائة|مئة|ماية)", r"\1مائة", m.group(1))
        run=[]
        for tok in w.split():
            core=normalize(tok)
            core=core[1:] if core.startswith("و") and len(core)>3 else core
            if re.fullmatch(r"(?:احدي|احد|اثنتين|اثنين|ثنتين|ثلاث|اربع|خمس|ست|سبع|ثمان|ثماني|تسع|عشر|عشره|عشرين|ثلاثين|اربعين|خمسين|ستين|سبعين|ثمانين|تسعين|مايه|ماييه|مائه|مايتين|مائتين|ثلاثمايه|ثلاثمائه|اربعمايه|اربعمائه|خمسمايه|خمسمائه|ستمايه|ستمائه|سبعمايه|سبعمائه|ثمانمايه|ثمانمائه|تسعمايه|تسعمائه|ستة|سته|ثمانيه)", core):
                run.append(tok)
            else:
                break
        w=" ".join(run)
        if not w: continue
        n, hundreds = number_words(w)
        if n and (hundreds or (n < 100 and lo < 100)) and lo <= n <= hi:
            return n
    return None
STOP=set(normalize(w) for w in "الإمام الامام الحافظ الفقيه العلامة شيخ رضي المحدث الثقة صاحب قاضي عالم فقيه الزاهد العابد المقرئ المقرىء الحجة أمير امير مفتي المجود الكبير الحبر محدث مسند الأستاذ القدوة أحد احد الثبت المفيد العالم الرباني ثقة القاضي".split())
def known_name(head):
    toks=re.sub(r"^[\d\s]+","",head).split()
    out=[]
    for t in toks:
        if normalize(t) in STOP and out: break
        out.append(t)
        if len(out)>=6: break
    while len(out)>1 and normalize(out[-1]) in ("ابو","ابي","ابا","ام","بن","عبد","بنت","هو"):
        out.pop()                       # a name cut after six words must not end on "Abu" or "b."
    if out and out[0]=="بن":
        out[0]="ابن"                    # the text writes "بن مسعود" for Ibn Mas'ud at the head of a name
    return " ".join(out)
c=sqlite3.connect(sys.argv[2])
def glue(t):
    return re.sub(r"(?<!\S)(عبد|ابو|ابي|ابا|ام) (?!بن )", r"\1_", t)
persons=[(pid,key,glue(normalize(n or "")),d,g) for pid,key,n,d,g in c.execute("select id,key,name_ar,death_year_ah,generation from persons where key like 'taqrib:%'")]
by_pair={}
for p in persons:
    t=p[2].split()
    if len(t)>=3 and t[1]=="بن":
        by_pair.setdefault(" ".join(t[:3]),[]).append(p)
res=[]; matched=0
for e in raw:
    head=e["head"]; rm=RUMUZ_RE.match(head)
    rumuz=rm.group(1).split() if rm else []
    head2=head[rm.end():] if rm else head
    d=year(e["text"], e["tabaqa"])
    hay=glue(normalize(head2+" "+e["text"][:160])).split()
    cands=set()
    for i in range(len(hay)-2):
        if hay[i+1]=="بن":
            for p in by_pair.get(" ".join(hay[i:i+3]),[]): cands.add(p)
    joined=" "+" ".join(hay)+" "
    def depth(p):
        t=p[2].split(); k=1
        while k+2<=len(t) and t[k]=="بن" and (" "+" ".join(t[:k+2])+" ") in joined: k+=2
        return (k+1)//2          # 1: the name alone; 2: name and father; 3: and grandfather …
    headtoks=set(glue(normalize(head2)).split()[:12])
    cands={p for p in cands if p[2].split()[0] in headtoks}      # the man of the entry, not one it mentions
    def clash(p):
        """The entry goes on with another father or grandfather than the candidate's: another man."""
        if depth(p) >= 3:                              # name, father and grandfather agree: a longer line may skip a link
            return False
        t=p[2].split(); k=depth(p)*2-1                 # tokens matched: name (bin father)…
        if k+1 >= len(t) or t[k] != "بن":
            return False
        run=" ".join(t[:k])
        for i in range(len(hay)-k-1):
            if " ".join(hay[i:i+k])==run and hay[i+k]=="بن" and i+k+1 < len(hay):
                return hay[i+k+1] != t[k+1]
        return False
    cands={p for p in cands if not clash(p)}
    good=[p for p in cands if d and p[3] and abs(p[3]-d)<=3]
    lo,hi=RANGE.get(e["tabaqa"],(1,800))
    deep=[p for p in cands if depth(p)>=3 and (abs(p[3]-d)<=10 if d and p[3] else (p[3] is not None and lo-10<=p[3]<=hi+10))]
    if not good and deep:
        best=max(depth(p) for p in deep)
        top=[p for p in deep if depth(p)==best]
        if len(top)==1: good=top
    if not good and e["tabaqa"]==1:          # the Companions: the one Companion of that name and father
        good=[p for p in cands if (p[4] or "sahabi")=="sahabi"]
        if len(good)!=1: good=[]
    pick=None
    if len(good)==1: pick=good[0]
    elif len(good)>1:                       # the deeper name first (name, father, grandfather …), then the words shared
        key=lambda p:(depth(p), len(set(p[2].split())&set(hay)))
        sc=sorted(good,key=key,reverse=True)
        if key(sc[0])>key(sc[1]): pick=sc[0]
    # a candidate of no known year that the entry names more fully than the one chosen: not sure, no link
    if pick:
        ov=lambda p: len(set(p[2].split())&set(hay))
        better=[p for p in cands if p is not pick and p[3] is None and ov(p) > ov(pick)]
        if better:
            top=max(better,key=ov)
            pick = top if ov(top) >= ov(pick)+2 and depth(top) >= 2 else None
    if not pick and e["tabaqa"]==1:
        sah=[p for p in cands if (p[4] or "sahabi")=="sahabi" and depth(p)>=2]
        if sah:
            best=max(depth(p) for p in sah); top=[p for p in sah if depth(p)==best]
            if len(top)==1: pick=top[0]
        if not pick:
            from isnady.core import famous
            keys=famous.named(known_name(head2),"sunni")
            if len(keys)==1: pick=next((p for p in persons if p[1]==keys[0]),None)
    # three Companions the rules above cannot reach (no "X b. Y" in the heading), checked by hand: Abu Dharr al-Ghifari,
    # 'A'isha the Mother of the Believers, Abu Hurayra — the Taqrib entries of those very names
    hand={7:"taqrib:8087", 13:"taqrib:8633", 16:"taqrib:8426"}
    if not pick and e["n"] in hand:
        pick=next((p for p in persons if p[1]==hand[e["n"]]),None)
    if pick: matched+=1
    res.append({"n":e["n"],"tabaqa":e["tabaqa"],"name":known_name(head2),"head":head2[:160],"rumuz":rumuz,"death":d,
                "taqrib":pick[1] if pick else None})
print("entries",len(res),"with death",sum(1 for r in res if r["death"]),"matched",matched)
for t in range(1,22):
    rs=[r for r in res if r["tabaqa"]==t]
    ds=sorted(r["death"] for r in rs if r["death"])
    print(t,len(rs),"deaths",len(ds),"median",ds[len(ds)//2] if ds else None,"matched",sum(1 for r in rs if r["taqrib"]))
out_path = ROOT / "src" / "isnady" / "assets" / "scholars" / "huffaz.json"
# "head": al-Dhahabi's own heading, its first twelve words (the short "name" is sometimes only a laqab: al-'Aqadi, 'Arim)
keep = [{**{k: r[k] for k in ("n", "tabaqa", "name", "rumuz", "death", "taqrib")},
         "head": " ".join(re.sub(r"^[\d\s]+", "", r["head"]).split()[:12])} for r in res]
out_path.write_text(json.dumps({"work": "0748Dhahabi.TadhkiratHuffaz.JK000532-ara1", "huffaz": keep},
                               ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print("written", out_path)
