# -*- coding: utf-8 -*-
"""解析指定 docx 的完整排版参数（只读分析，不改动文件）

用法：python docx-style-extract.py <要分析的.docx>
"""
import zipfile, re, sys

# 强制 UTF-8 输出，避免 Windows 控制台默认 GBK 造成中文乱码/UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from xml.etree import ElementTree as ET

if len(sys.argv) < 2:
    sys.exit("用法：python docx-style-extract.py <要分析的.docx>")
DOCX = sys.argv[1]

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
def w(tag): return f"{{{W}}}{tag}"
def a(tag): return f"{{{A}}}{tag}"

z = zipfile.ZipFile(DOCX)
print("="*70)
print("[0] 包结构")
for n in z.namelist():
    if n.startswith("word/") or "media" in n or "embed" in n:
        info = z.getinfo(n)
        print(f"  {n}\t{info.file_size} bytes")

# 样式表里默认字体设置
print("="*70)
print("[1] styles.xml 关键默认样式")
try:
    styles = ET.fromstring(z.read("word/styles.xml"))
    for st in styles.findall(w("style")):
        sid = st.get(w("styleId"))
        if sid in ("Normal", "Heading1", "Heading2", "Heading3", "Title", "Subtitle", "DefaultParagraphFont"):
            rpr = st.find(w("rPr"))
            ppr = st.find(w("pPr"))
            sz = rpr.find(w("sz")) if rpr is not None else None
            szCs = rpr.find(w("szCs")) if rpr is not None else None
            fonts = rpr.find(w("rFonts")) if rpr is not None else None
            col = rpr.find(w("color")) if rpr is not None else None
            b = rpr.find(w("b")) if rpr is not None else None
            spacing = ppr.find(w("spacing")) if ppr is not None else None
            jc = ppr.find(w("jc")) if ppr is not None else None
            def gx(e, attr): return e.get(w(attr)) if e is not None else None
            print(f"  [{sid}] sz={gx(sz,'val')} szCs={gx(szCs,'val')} b={gx(b,'val')} "
                  f"font_ascii={gx(fonts,'ascii')} font_eastAsia={gx(fonts,'eastAsia')} "
                  f"font_hAnsi={gx(fonts,'hAnsi')} color={gx(col,'val')} "
                  f"jc={gx(jc,'val')} spacing={ {k:spacing.get(w(k)) for k in ('before','after','line','lineRule') if spacing is not None} }")
except KeyError:
    print("  (无 styles.xml)")

# 文档主题字体
print("="*70)
print("[2] 主题字体 theme1")
try:
    theme = ET.fromstring(z.read("word/theme/theme1.xml"))
    ns = {"a":"http://schemas.openxmlformats.org/drawingml/2006/main"}
    for tag in ("majorFont","minorFont"):
        el = theme.find(f".//a:{tag}", ns)
        if el is not None:
            la = el.find("a:latin", ns); ea = el.find("a:ea", ns)
            print(f"  {tag}: latin={la.get('typeface') if la is not None else None}, ea={ea.get('typeface') if ea is not None else None}")
except KeyError:
    print("  (无 theme)")

# 正文段落
print("="*70)
print("[3] document.xml 正文段落/表格/分节")
doc = ET.fromstring(z.read("word/document.xml"))
body = doc.find(w("body"))

def get_text(p):
    return "".join(t.text or "" for t in p.iter(w("t")))

def pt2cm(v): return round(int(v)/567*2.54, 2)
def pt2inch(v): return round(int(v)/567, 2)

pn = 0
tables = 0
for el in body:
    tag = el.tag
    if tag == w("p"):
        pn += 1
        txt = get_text(el)
        ppr = el.find(w("pPr"))
        style = ppr.find(w("pStyle")) if ppr is not None else None
        style_id = style.get(w("val")) if style is not None else "(默认)"
        jc = ppr.find(w("jc")) if ppr is not None else None
        spacing = ppr.find(w("spacing")) if ppr is not None else None
        ind = ppr.find(w("ind")) if ppr is not None else None
        # 取首段内首个 run 的格式
        rpr = None
        for r in el.findall(w("r")):
            rp = r.find(w("rPr"))
            if rp is not None:
                rpr = rp; break
        if rpr is not None:
            sz = rpr.find(w("sz")); col = rpr.find(w("color")); fonts = rpr.find(w("rFonts")); b = rpr.find(w("b"))
            szv = sz.get(w("val")) if sz is not None else None
            colv = col.get(w("val")) if col is not None else None
            big = szv and int(szv)>=20
        else:
            szv=colv=None; fonts=None; b=None; big=False
        sp = {}
        if spacing is not None:
            for k in ("before","after","line","lineRule"):
                v = spacing.get(w(k))
                if v is not None: sp[k]=v
        indv = {k: ind.get(w(k)) for k in ("left","firstLine","hanging")} if ind is not None else {}
        fa = fonts.get(w("ascii")) if fonts is not None else None
        fe = fonts.get(w("eastAsia")) if fonts is not None else None
        fh = fonts.get(w("hAnsi")) if fonts is not None else None
        bv = b.get(w("val")) if b is not None else None
        mark = "★" if big else ""
        print(f"  P{pn:02d}{mark}[{style_id}] sz={szv} b={bv} fontEA={fe} fontLatin={fa or fh} "
              f"color={colv} jc={jc.get(w('val')) if jc is not None else None} "
              f"spacing={sp if sp else None} ind={indv if any(indv.values()) else None}")
        if txt.strip():
            print(f"       文本: {txt[:60]}")
    elif tag == w("tbl"):
        tables += 1
        print(f"  >>> 发现表格 <w:tbl> 数量+1 (当前 {tables})")

print(f"\n总段落(含空段): {pn}, 表格数: {tables}")

# 分节属性
print("="*70)
print("[4] sectPr 页边距/纸张")
sect = body.find(w("sectPr"))
if sect is not None:
    pgmar = sect.find(w("pgMar"));
    pgsz = sect.find(w("pgSz"))
    def gm(e,k): return e.get(w(k)) if e is not None else None
    if pgmar is not None:
        for k in ("top","right","bottom","left","header","footer","gutter"):
            v = gm(pgmar,k)
            print(f"  pgMar.{k} = {v} twips = {round(int(v)/567*2.54,2)}cm" if v else f"  pgMar.{k} = -")
    if pgsz is not None:
        print(f"  pgSz.w={gm(pgsz,'w')} h={gm(pgsz,'h')} ({round(int(gm(pgsz,'w'))/567*2.54,2)}x{round(int(gm(pgsz,'h'))/567*2.54,2)}cm)")

# 页眉页脚
print("="*70)
print("[5] 页眉页脚")
for part in ("word/header1.xml","word/header2.xml","word/header3.xml",
             "word/footer1.xml","word/footer2.xml","word/footer3.xml"):
    try:
        hf = ET.fromstring(z.read(part))
        txt = "".join(t.text or "" for t in hf.iter(w("t")))
        imgs = [x.get(f"{{{A}}}embed") for x in hf.iter(f"{{{A}}}blip")]
        # 检查 svg
        svgs = [x.get(f"{{{W}}}val") for x in hf.iter(w("pict"))]
        print(f"  {part}: 文本='{txt[:80]}' 图片blips={imgs} 后续SVG检查见media")
    except KeyError:
        pass

print("="*70)
print("[6] media 图片属性（证件照/装饰）")
for n in z.namelist():
    if n.startswith("word/media/"):
        d = z.read(n)
        # 尝试解析 PNG/JPEG 尺寸
        wdt=hgt=None
        if n.endswith(".png"):
            if d[:8]==b'\x89PNG\r\n\x1a\n' and len(d)>24:
                wdt,hgt = int.from_bytes(d[16:20],'big'), int.from_bytes(d[20:24],'big')
        elif n.endswith(".jpg") or n.endswith(".jpeg"):
            # 简单找 SOF 段
            i=2
            while i < len(d)-9:
                if d[i]!=0xFF: i+=1; continue
                m=d[i+1]
                if m in (0xC0,0xC1,0xC2,0xC3):
                    hgt=int.from_bytes(d[i+5:i+7],'big'); wdt=int.from_bytes(d[i+7:i+9],'big'); break
                i+=1
        elif n.endswith(".svg"):
            try:
                sv=txt=d.decode('utf-8','ignore')
                wdt = re.search(r'width="([\d.]+)"', sv)
                hgt = re.search(r'height="([\d.]+)"', sv)
                wdt = "svg:"+wdt.group(1) if wdt else "?"
                hgt = "svg:"+hgt.group(1) if hgt else "?"
            except Exception: pass
        print(f"  {n}: {len(d)} bytes, {wdt}x{hgt}")