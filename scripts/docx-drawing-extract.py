# -*- coding: utf-8 -*-
"""补查：drawing 图片定位/尺寸 + header 图标结构 + 纸张单位换算修正

用法：python docx-drawing-extract.py <要分析的.docx>
"""
import zipfile, sys

# 强制 UTF-8 输出，避免 Windows 控制台默认 GBK 造成中文乱码/UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from xml.etree import ElementTree as ET

if len(sys.argv) < 2:
    sys.exit("用法：python docx-drawing-extract.py <要分析的.docx>")
DOCX = sys.argv[1]
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
def w(t): return f"{{{W}}}{t}"
def wp(t): return f"{{{WP}}}{t}"
def a(t): return f"{{{A}}}{t}"
def r(t): return f"{{{R}}}{t}"

z = zipfile.ZipFile(DOCX)

# 1) document.xml 中所有 drawing 的定位与尺寸
print("="*70)
print("[A] document.xml 内 drawing（图片）定位")
doc = ET.fromstring(z.read("word/document.xml"))
rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
rid2target = {}
for rel in rels:
    rid2target[rel.get(r("Id"))] = rel.get(r("Target"))

def emu2cm(v): return round(int(v)/914400*2.54, 2)

for i, dr in enumerate(doc.iter(w("drawing"))):
    info = {"idx": i}
    inline = dr.find(wp("inline")); anchor = dr.find(wp("anchor"))
    kind = "inline" if inline is not None else ("anchor(浮动)" if anchor is not None else "?")
    node = inline if inline is not None else anchor
    info["kind"] = kind
    if node is not None:
        ext = node.find(wp("extent"))
        if ext is not None:
            info["extent"] = f"{emu2cm(ext.get('cx'))}x{emu2cm(ext.get('cy'))}cm"
        if anchor is not None:
            # 浮动锚点：定位相对段落/页面、偏移
            posH = anchor.find(wp("positionH")); posV = anchor.find(wp("positionV"))
            def posinfo(p):
                if p is None: return None
                off = p.find(wp("posOffset"))
                return f"{p.get('relativeFrom')}:{off.text if off is not None else '?'}"
            info["posH"] = posinfo(posH); info["posV"] = posinfo(posV)
            info["anchor_ppt"] = anchor.get('distT')
        blip = node.find(f".//{a('blip')}")
        if blip is not None:
            info["rid"] = blip.get(r("embed"))
            info["media"] = rid2target.get(info["rid"])
        # 图形文字（可能是描边装饰）
        txs = [t.text for t in node.iter(w("t"))]
        if txs: info["draw_text"] = txs[:3]
    print(" ", info)

# 2) header 结构（可能无 header 部件，需容错）
print("="*70)
print("[B] header 结构（图标用途）")
header_parts = [n for n in z.namelist() if n.startswith("word/header")]
if not header_parts:
    print("  (无 header 部件)")
for part in header_parts:
    print(f"  -- {part} --")
    h1 = ET.fromstring(z.read(part))
    rels_name = "word/_rels/" + part.rsplit("/", 1)[-1] + ".rels"
    try:
        hrels = ET.fromstring(z.read(rels_name))
        hrid2target = {rel.get(r("Id")): rel.get(r("Target")) for rel in hrels}
    except KeyError:
        hrid2target = {}
    seg_cnt = 0
    for seg in h1.findall(w("p")):
        txt = "".join(t.text or "" for t in seg.iter(w("t")))
        blips = [hrid2target.get(b.get(r("embed"))) for b in seg.iter(f"{A}blip")]
        seg_cnt += 1
        print(f"  段落{seg_cnt}: 文本='{txt[:40]}' 图片={blips}")

# 3) 纸张/边距单位修正
print("="*70)
print("[C] 单位修正（twips→cm: /567; EMU→cm: /914400*2.54）")
sect = doc.find(w("body")).find(w("sectPr"))
if sect is None:
    print("  (无 sectPr，跳过纸张/页边距)")
else:
    pgmar = sect.find(w("pgMar")); pgsz = sect.find(w("pgSz"))
    if pgsz is not None:
        print(f"  A4: {round(int(pgsz.get(w('w')))/567,2)}x{round(int(pgsz.get(w('h')))/567,2)}cm")
    if pgmar is not None:
        print(f"  页边距: 上{round(int(pgmar.get(w('top')))/567,2)}  下{round(int(pgmar.get(w('bottom')))/567,2)}  左{round(int(pgmar.get(w('left')))/567,2)}  右{round(int(pgmar.get(w('right')))/567,2)} cm")
        print(f"  header={pgmar.get(w('header'))} footer={pgmar.get(w('footer'))} (twips)")

# 4) media 图片真实尺寸/宽高比（真实读取 word/media/*，不再写死假数据）
print("="*70)
print("[D] word/media 图片真实尺寸与宽高比")


def _img_size(data):
    """返回 (w, h)；无法解析返回 (None, None)。支持 PNG / JPEG。"""
    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) > 24:
        return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
    if data[:2] == b'\xff\xd8':  # JPEG SOI
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3):  # SOF0-3
                h = int.from_bytes(data[i + 5:i + 7], 'big')
                w = int.from_bytes(data[i + 7:i + 9], 'big')
                return w, h
            i += 1
    return None, None


media = [n for n in z.namelist() if n.startswith('word/media/')]
if not media:
    print("  (无 word/media 图片)")
for n in media:
    data = z.read(n)
    wdt, hgt = _img_size(data)
    if wdt and hgt:
        print(f"  {n}: {len(data)} bytes, {wdt}x{hgt}, 宽高比={wdt/hgt:.3f}")
    else:
        print(f"  {n}: {len(data)} bytes, 尺寸无法解析或非位图")