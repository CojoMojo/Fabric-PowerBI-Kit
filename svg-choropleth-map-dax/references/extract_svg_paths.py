"""
SVG → CSV extractor for Power BI choropleth maps.

Usage:
    python extract_svg_paths.py input.svg output.csv

Emits a CSV with columns: Code, Name, Group, MinX, MinY, MaxX, MaxY, Path

The Group column is left blank by default. Edit classify() below to assign
each shape to a region/zone/continent based on its Code.

Requirements: Python 3.8+. Only uses the standard library.
"""
from __future__ import annotations
import csv, re, sys, xml.etree.ElementTree as ET
from pathlib import Path

# ═════════════════════════════════════════════════════════════════════════
# CUSTOMIZE: classify each shape into a group. Return "" if no grouping.
# ═════════════════════════════════════════════════════════════════════════
def classify(code: str, name: str) -> str:
    """Return a grouping string for this shape, or '' for no group."""
    # Example for US states — uncomment and adapt:
    # NORTHEAST = {"ME","NH","VT","MA","RI","CT","NY","NJ","PA"}
    # SOUTH     = {"DE","MD","DC","VA","WV","NC","SC","GA","FL","KY","TN",
    #              "AL","MS","AR","LA","OK","TX"}
    # MIDWEST   = {"OH","IN","IL","MI","WI","MN","IA","MO","ND","SD","NE","KS"}
    # WEST      = {"MT","ID","WY","CO","NM","AZ","UT","NV","CA","OR","WA","AK","HI"}
    # if code in NORTHEAST: return "Northeast"
    # if code in SOUTH: return "South"
    # if code in MIDWEST: return "Midwest"
    # if code in WEST: return "West"
    # return "Outside US"
    return ""

# ═════════════════════════════════════════════════════════════════════════
# Path bounding box — tokenizes the d= string and tracks min/max coords.
# Handles absolute & relative commands: M/m L/l H/h V/v C/c S/s Q/q T/t A/a Z/z
# ═════════════════════════════════════════════════════════════════════════
_CMD = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]")
_NUM = re.compile(r"-?\d*\.?\d+(?:[eE][+-]?\d+)?")

def path_bbox(d: str) -> tuple[float, float, float, float]:
    tokens: list[tuple[str, list[float]]] = []
    i = 0
    while i < len(d):
        m = _CMD.search(d, i)
        if not m:
            break
        cmd = m.group(0)
        nxt = _CMD.search(d, m.end())
        segment = d[m.end(): nxt.start() if nxt else len(d)]
        nums = [float(x) for x in _NUM.findall(segment)]
        tokens.append((cmd, nums))
        i = nxt.start() if nxt else len(d)

    x = y = sx = sy = 0.0
    mnx = mny = float("inf")
    mxx = mxy = float("-inf")

    def upd(px: float, py: float) -> None:
        nonlocal mnx, mny, mxx, mxy
        if px < mnx: mnx = px
        if py < mny: mny = py
        if px > mxx: mxx = px
        if py > mxy: mxy = py

    for cmd, nums in tokens:
        rel = cmd.islower()
        c = cmd.upper()
        k = 0
        first = True
        while k < len(nums) or c == "Z":
            if c == "M":
                nx, ny = nums[k], nums[k+1]
                x, y = (x+nx, y+ny) if rel else (nx, ny)
                if first: sx, sy = x, y; first = False
                upd(x, y); k += 2
                c = "L"  # subsequent pairs after M are implicit L
            elif c == "L":
                nx, ny = nums[k], nums[k+1]
                x, y = (x+nx, y+ny) if rel else (nx, ny)
                upd(x, y); k += 2
            elif c == "H":
                nx = nums[k]
                x = x+nx if rel else nx
                upd(x, y); k += 1
            elif c == "V":
                ny = nums[k]
                y = y+ny if rel else ny
                upd(x, y); k += 1
            elif c in ("C", "S", "Q", "T"):
                count = {"C": 6, "S": 4, "Q": 4, "T": 2}[c]
                pts = nums[k:k+count]
                for j in range(0, count, 2):
                    px, py = pts[j], pts[j+1]
                    px, py = (x+px, y+py) if rel else (px, py)
                    upd(px, py)
                x, y = ( (x + pts[-2], y + pts[-1]) if rel else (pts[-2], pts[-1]) )
                k += count
            elif c == "A":
                # rx ry x-axis-rot large-arc sweep x y — only endpoint matters for bbox approx
                nx, ny = nums[k+5], nums[k+6]
                x, y = (x+nx, y+ny) if rel else (nx, ny)
                upd(x, y); k += 7
            elif c == "Z":
                x, y = sx, sy
                break
            else:
                k += 1
    return mnx, mny, mxx, mxy


# ═════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════
def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python extract_svg_paths.py input.svg output.csv")
        return 1

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    tree = ET.parse(src)
    root = tree.getroot()
    ns = {"s": "http://www.w3.org/2000/svg"}

    paths = root.findall(".//s:path", ns) or root.findall(".//path")

    rows = []
    for p in paths:
        d = p.get("d")
        if not d:
            continue
        code = p.get("id") or p.get("data-id") or ""
        name = (
            p.get("name")
            or p.get("data-name")
            or (p.find("s:title", ns).text if p.find("s:title", ns) is not None else "")
            or code
        )
        if not code and not name:
            continue  # skip anonymous

        mnx, mny, mxx, mxy = path_bbox(d)
        rows.append(dict(
            Code=code or name,
            Name=name or code,
            Group=classify(code, name),
            MinX=round(mnx, 2),
            MinY=round(mny, 2),
            MaxX=round(mxx, 2),
            MaxY=round(mxy, 2),
            Path=d.strip(),
        ))

    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Code","Name","Group","MinX","MinY","MaxX","MaxY","Path"],
                           quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {dst} — {len(rows)} shapes")
    groups = sorted({r['Group'] for r in rows if r['Group']})
    if groups:
        print("Groups:", ", ".join(groups))
    else:
        print("(No groups assigned — edit classify() in the script to enable regional drill.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
