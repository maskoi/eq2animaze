"""Post-build texture pass (run with system Python + Pillow, NOT Blender).

Blender's image save paths (save() = raw linear dump, save_render() = view-
transform contaminated) proved unreliable for shipping color-accurate PNGs.
This script rewrites the build's Textures/ folder with byte-exact content:
  - authentic Lantern-extracted PNGs for every skin/eye texture (bit-perfect);
  - the Velious plate dyed to the teal sampled from the in-game Ironscales
    reference screenshot, computed in proper sRGB math;
  - the helm plates dyed to match, with alpha-masked texels filled solid
    (Animaze ignores the mask and would render them black);
  - solid-color utility textures regenerated at their intended sRGB colors.

Usage: python postprocess_textures.py <path-to-IMPORT-ONLY-MASKOI-Vxx>
"""
import sys
from pathlib import Path
from PIL import Image

HANDOFF = Path(__file__).resolve().parents[2]
LANTERN = Path(r"C:/Users/Raphael/Documents/Codex/2026-07-14/LanternExtractor-0.1.7.win-x64/Exports")
AUTHENTIC_DIRS = [
    LANTERN / "globalikm" / "Characters" / "Textures",
    LANTERN / "global4" / "Characters" / "Textures",
]
PLATE_DDS = HANDOFF / "source" / "assets" / "velious-plate" / "velious_plate_ikm_c.dds"
SET04_DIR = HANDOFF / "source" / "assets" / "plate-set04"

PLATE_TARGET = (12, 134, 100)   # armor teal sampled from the reference screenshot
HELM_TINT = (0, 150, 110)       # slightly deeper teal for the helm plates
HELM_MIX = 0.60

def srgb_decode(b):
    v = b / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

def srgb_encode(v):
    v = max(0.0, min(1.0, v))
    e = 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055
    return round(e * 255.0)

DEC = [srgb_decode(i) for i in range(256)]

def solve_plate_multipliers(lin_channels, target):
    mults = []
    for c in range(3):
        data = lin_channels[c]
        lo, hi = 0.0, 60.0
        for _ in range(48):
            mid = (lo + hi) / 2
            mean = sum(srgb_encode(v * mid) for v in data) / len(data)
            if mean < target[c]:
                lo = mid
            else:
                hi = mid
        mults.append((lo + hi) / 2)
    return mults

def dye_plate(out_path, teal=False):
    """Velious plate atlas for the greave meshes. Alpha flattened (EQ shine mask)."""
    src = Image.open(PLATE_DDS).convert("RGBA")
    src.putalpha(255)
    if teal:
        out = Image.new("RGBA", src.size)
        out.putdata(_colorize(list(src.getdata())))
        src = out
    src.save(out_path)
    return ("teal" if teal else "authentic",)

def dye_helm(src_path, out_path):
    src = Image.open(src_path).convert("RGBA")
    px = list(src.getdata())
    tint_lin = [DEC[c] for c in HELM_TINT]
    dyed = []
    opaque_acc = [0, 0, 0]; opaque_n = 0
    for (r, g, b, a) in px:
        nr = srgb_encode(DEC[r] * (1 - HELM_MIX) + tint_lin[0] * HELM_MIX)
        ng = srgb_encode(DEC[g] * (1 - HELM_MIX) + tint_lin[1] * HELM_MIX)
        nb = srgb_encode(DEC[b] * (1 - HELM_MIX) + tint_lin[2] * HELM_MIX)
        dyed.append((nr, ng, nb, a))
        if a >= 128:
            opaque_acc[0] += nr; opaque_acc[1] += ng; opaque_acc[2] += nb; opaque_n += 1
    mean = tuple(int(c / max(opaque_n, 1)) for c in opaque_acc)
    final = [(p if p[3] >= 128 else (mean[0], mean[1], mean[2], 255)) for p in dyed]
    final = [(r, g, b, 255) for (r, g, b, a) in final]
    img = Image.new("RGBA", src.size)
    img.putdata(final)
    img.save(out_path)

def solid(out_path, size, rgb):
    Image.new("RGBA", size, (*rgb, 255)).save(out_path)


_SET04_MULT = None

def set04_multiplier():
    """Solve one shared multiplier over all set-04 tiles so every armor piece
    lands on the same teal."""
    global _SET04_MULT
    if _SET04_MULT is not None:
        return _SET04_MULT
    lin = [[], [], []]
    for png in sorted(SET04_DIR.glob("ikm??04*.png")):
        src = Image.open(png).convert("RGB")
        for (r, g, b) in list(src.getdata())[::5]:
            if r + g + b > 8:
                lin[0].append(DEC[r]); lin[1].append(DEC[g]); lin[2].append(DEC[b])
    _SET04_MULT = solve_plate_multipliers(lin, PLATE_TARGET)
    return _SET04_MULT

# Cohort's Legionnaire teal — RECALIBRATED against the real in-game Cohort's
# screenshots (bright shiny cyan-teal with a metallic near-white sheen), NOT the
# older dull-emerald reference. Key differences from the old ramp: much brighter
# and more saturated cyan-teal mids, and highlights that push toward metallic
# near-white (the wet-plate shine). Mids stay LOW-red (saturated, no plastic
# pastel — the "Micronauts" trap); only the specular highlight goes bright/white.
EMERALD_RAMP = ((0, 65, 58), (15, 200, 185), (175, 252, 248))
DYE_EXP = 0.32  # lift midtones brighter so more of the plate reads vivid teal

def _colorize(px):
    """Marble-preserving emerald: tile luminance carries ALL the detail and
    drives a two-segment color ramp matched to the in-game Ironscales look."""
    out = []
    for (r, g, b, a) in px:
        L = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        Lb = L ** DYE_EXP if L > 0 else 0.0
        if Lb < 0.5:
            t, c0, c1 = Lb / 0.5, EMERALD_RAMP[0], EMERALD_RAMP[1]
        else:
            t, c0, c1 = (Lb - 0.5) / 0.5, EMERALD_RAMP[1], EMERALD_RAMP[2]
        # EQ stores an env-shine mask in alpha; armor is opaque, so flatten it.
        out.append((int(c0[0] + (c1[0] - c0[0]) * t), int(c0[1] + (c1[1] - c0[1]) * t),
                    int(c0[2] + (c1[2] - c0[2]) * t), 255))
    return out

def dye_set04(name, out_path):
    """Luminance colorize: the authentic tile's detail becomes shading over a
    uniformly bright teal, matching how the in-game reference reads."""
    src = Image.open(SET04_DIR / name).convert("RGBA")
    img = Image.new("RGBA", src.size)
    img.putdata(_colorize(list(src.getdata())))
    img.save(out_path)


def compose_atlas(build_dir, tex_dir):
    """Compose the shipped body atlas from the manifest: authentic tiles for
    skin, colorized teal for set-04 armor. Overwrites the stub the build wrote."""
    import json, re as _re
    mpath = Path(build_dir) / "atlas_manifest.json"
    if not mpath.exists():
        return None
    man = json.loads(mpath.read_text())
    cell, cols, rows = man["cell"], man["cols"], man["rows"]
    # Config-driven: which armor tile set (00 cloth, 04 plate, ...) and dir this
    # build used. Falls back to the plate defaults for older manifests.
    tiles_dir = (HANDOFF / man["tiles_dir"]) if man.get("tiles_dir") else SET04_DIR
    armor_set = man.get("armor_set", "04")
    race = man.get("race_token", "ikm")
    atlas = Image.new("RGBA", (cols * cell, rows * cell), (128, 128, 128, 255))
    for e in man["entries"]:
        src_name = e["source"]
        if not src_name:
            continue
        tile = None
        # fa + he were missing from this alternation: any forearm/head tile in the
        # project tiles_dir silently fell through to the Lantern-authentic fallback
        # and, if absent there, shipped as flat 128-grey canvas (the V3 grey-forearm bug).
        if _re.match(race + r"(ch|lg|ft|hn|ua|ta|fa|he)\d\d\d\d\.png", src_name):
            src = tiles_dir / src_name
            if src.exists():
                tile = Image.open(src).convert("RGBA")
                tile.putalpha(255)  # authentic pixels, opaque
                # EQ's flat 8x8 tiles are white TINT CANVASES (the game always
                # multiplies an item tint over them). Untinted they render as
                # white patches (neck/shoulders); fill them with the average
                # tone of the part's detailed tile instead — the DYED average
                # in teal mode, or the canvas blows out white / goes raw grey.
                if tile.size[0] <= 16:
                    part = src_name[3:5]
                    _bigs = sorted(tiles_dir.glob(f"{race}{part}{armor_set}*.png"),
                                 key=lambda q: Image.open(q).size[0] * Image.open(q).size[1])
                    if not _bigs:
                        continue
                    big = _bigs[-1]
                    bigimg = Image.open(big).convert("RGBA")
                    if man.get("dye") == "teal":
                        b2 = Image.new("RGBA", bigimg.size)
                        b2.putdata(_colorize(list(bigimg.getdata())))
                        bigimg = b2
                    bp = [px for px in bigimg.getdata() if px[3] >= 128 and sum(px[:3]) > 24]
                    if bp:
                        mean = tuple(int(sum(c[i] for c in bp) / len(bp)) for i in range(3))
                        tile = Image.new("RGBA", tile.size, (*mean, 255))
                elif man.get("dye") == "teal":
                    t2 = Image.new("RGBA", tile.size)
                    t2.putdata(_colorize(list(tile.getdata())))
                    tile = t2
        else:
            src = find_authentic(src_name)
            if src:
                tile = Image.open(src).convert("RGBA")
                # flatten EQ mask alpha; atlas material is opaque
                tile.putalpha(255)
        if tile is None:
            continue
        # 16px edge-replicated gutter per cell so mipmapping never bleeds
        # neighboring cells into this tile (fixes flickering black patches).
        G = 16
        inner = cell - 2 * G
        t = tile.resize((inner, inner), Image.LANCZOS)
        x0, y0 = e["cell"][0] * cell, e["cell"][1] * cell
        atlas.paste(t.resize((cell, cell), Image.LANCZOS), (x0, y0))  # base fill
        atlas.paste(t, (x0 + G, y0 + G))
        atlas.paste(t.crop((0, 0, inner, 1)).resize((inner, G)), (x0 + G, y0))
        atlas.paste(t.crop((0, inner - 1, inner, inner)).resize((inner, G)), (x0 + G, y0 + cell - G))
        atlas.paste(t.crop((0, 0, 1, inner)).resize((G, inner)), (x0, y0 + G))
        atlas.paste(t.crop((inner - 1, 0, inner, inner)).resize((G, inner)), (x0 + cell - G, y0 + G))
    out = Path(tex_dir) / man["atlas"]
    atlas.save(out)
    return man["atlas"]

def find_authentic(name):
    for d in AUTHENTIC_DIRS:
        p = d / name
        if p.exists():
            return p
    return None

def main(build_dir):
    tex = Path(build_dir) / "Textures"
    assert tex.is_dir(), f"no Textures dir in {build_dir}"
    report = []
    atlas_name = compose_atlas(build_dir, tex)
    atlas_dye = "authentic"
    try:
        import json as _json
        atlas_dye = _json.loads((Path(build_dir) / "atlas_manifest.json").read_text()).get("dye", "authentic")
    except Exception:
        pass
    if atlas_name:
        report.append(f"{atlas_name}: composed body atlas from manifest")
    for f in sorted(tex.iterdir()):
        n = f.name
        if n == "Maskoi_Velious_Plate_Emerald.png":
            dye_plate(f, teal=(atlas_dye == "teal"))
            report.append(f"{n}: dyed plate (colorize)")
        elif n.startswith("Maskoi_tm_ikmhe") and n.endswith("_Emerald.png"):
            base = n.replace("Maskoi_tm_", "").replace("_Emerald.png", ".png")
            src = find_authentic(base)
            if src:
                dye_helm(src, f)
                report.append(f"{n}: dyed helm from authentic {base}")
            else:
                report.append(f"{n}: !! authentic {base} NOT FOUND, left as built")
        elif __import__("re").match(r"ikm(ch|lg|ft|hn|ua|ta)04\d\d\.png", n):
            dye_set04(n, f)
            report.append(f"{n}: set-04 plate dyed teal")
        elif n == "Maskoi_Forehead_Gem_Texture.png":
            solid(f, (8, 8), (110, 35, 240))
            report.append(f"{n}: solid gem purple")
        elif atlas_name and n == atlas_name:
            pass  # already composed above
        elif n.endswith(".png"):
            src = find_authentic(n)
            if src:
                data = src.read_bytes()
                f.write_bytes(data)
                report.append(f"{n}: replaced with authentic original")
            else:
                report.append(f"{n}: no authentic source, left as built")
    for line in report:
        print(line)

if __name__ == "__main__":
    main(sys.argv[1])
