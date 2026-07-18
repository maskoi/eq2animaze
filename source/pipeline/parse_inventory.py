"""
parse_inventory.py  -  neoweo.com input layer

Turns an EverQuest `/outputfile inventory` dump into a structured build spec the
eq2animaze factory can consume. This is what a player uploads to neoweo.com: it
carries their exact equipped gear (item IDs), which the factory then resolves to
armor appearance via the item database.

Inventory file format (tab-separated, one header line):
    Location \t Name \t ID \t Count \t Slots
    Head \t Cohort's Legionnaire Helm \t 148004 \t 1 \t 6
    Head-Slot1 \t <augment> \t ...        <- augment slots, ignored for appearance

Filename convention: <Character>_<server>-Inventory.txt

Usage:
    python parse_inventory.py "Ironscales_tunare-Inventory.txt" [out.json]
    from parse_inventory import parse_inventory
    spec = parse_inventory(path)   # -> dict
"""
import sys
import os
import json
import re

# The equipment slots that determine visible appearance (what the avatar wears).
# Order roughly head-to-toe; the armor factory cares about the armor ones.
VISIBLE_SLOTS = [
    "Head", "Face", "Neck", "Shoulders", "Arms", "Back", "Wrist",
    "Range", "Hands", "Primary", "Secondary", "Chest", "Legs", "Feet", "Waist", "Ear",
]
# Slots that map to the body-armor texture regions the factory swaps.
ARMOR_SLOTS = {"Head", "Chest", "Arms", "Wrist", "Hands", "Legs", "Feet", "Shoulders"}


def _char_server_from_name(path):
    base = os.path.basename(path)
    m = re.match(r"(?P<char>[A-Za-z]+)_(?P<server>[A-Za-z0-9]+)-Inventory\.txt$", base, re.I)
    if m:
        return m.group("char"), m.group("server")
    return os.path.splitext(base)[0], None


def parse_inventory(path):
    """Return a build spec: character, server, and the visible equipped items."""
    character, server = _char_server_from_name(path)
    equipment = {}      # slot -> {"name", "id"}  (primary worn item only)
    all_items = []      # every non-empty item (for the full item-DB seed)

    with open(path, encoding="utf-8", errors="replace") as fh:
        header = fh.readline()  # Location / Name / ID / Count / Slots
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            loc, name, iid = parts[0], parts[1], parts[2]
            if not iid.isdigit():   # skip repeated header rows ("ID") and junk
                continue
            if not name or name == "Empty" or iid == "0":
                continue
            # skip augment sub-slots like "Head-Slot1" - they don't change the look
            if "-Slot" in loc:
                # still record for the item DB, but not as worn appearance
                all_items.append({"slot": loc, "name": name, "id": int(iid)})
                continue
            all_items.append({"slot": loc, "name": name, "id": int(iid)})
            # a base slot name (strip any trailing index EQ sometimes appends)
            base_slot = loc.strip()
            if base_slot in VISIBLE_SLOTS:
                # Ear/Wrist/Fingers appear twice; keep the first, note duplicates
                if base_slot not in equipment:
                    equipment[base_slot] = {"name": name, "id": int(iid)}

    armor = {s: equipment[s] for s in ARMOR_SLOTS if s in equipment}
    return {
        "character": character,
        "server": server,
        "source_file": os.path.basename(path),
        "equipment": equipment,           # all visible worn slots
        "armor": armor,                   # just the body-armor slots the factory swaps
        "all_item_ids": sorted({it["id"] for it in all_items}),
        "item_count": len(all_items),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: parse_inventory.py <inventory.txt> [out.json]")
        sys.exit(1)
    spec = parse_inventory(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else None
    if out:
        json.dump(spec, open(out, "w"), indent=2)
        print("wrote", out)
    print(f"\n{spec['character']} on {spec['server']} - {len(spec['equipment'])} visible pieces:")
    for slot, it in spec["equipment"].items():
        tag = " [ARMOR]" if slot in ARMOR_SLOTS else ""
        print(f"  {slot:11s} {it['name']:42s} #{it['id']}{tag}")
