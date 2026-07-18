<!--
READY-TO-POST GitHub issue for LanternEQ/LanternExtractor.
Open a new issue at https://github.com/LanternEQ/LanternExtractor/issues/new
Title and body below. (Issue #32 is a different bug — illegal path chars — do not
comment there.)
-->

# TITLE
Character animations silently dropped for Kunark+ models with a variant letter in track names (Iksar, Vah Shir, etc.)

# BODY

## Summary

Character models whose animation track names contain a **variant letter** between
the animation code and the model base export to glTF with **zero animations** —
the model comes out frozen in its bind pose. Classic races (Human, Elf, Dwarf, …)
are unaffected and export their full clip set normally.

Confirmed on Iksar (`globalikm_chr`); by naming pattern this affects every
Kunark-and-later variant-letter model (Iksar male/female, Vah Shir, etc.).

## Reproduce

```
LanternExtractor.exe globalikm_chr
```

Result: `ikm.glb` is ~536 KB with **0 animations**. A classic race
(`LanternExtractor.exe global_chr` → `hum.glb`, `elm.glb`) exports 30+ animations.

## Root cause

EQ names animation tracks `[animation][model][bone]`:

- Classic: `C01ELMPE` = `C01` + `ELM` + `PE` — clean 3 + 3.
- Kunark+: `C01AIKMPEBIP01` = `C01` + **`A`** + `IKM` + `PEBIP01` — a variant letter
  sits between the 3-char animation code and the 3-char model base.

The track/skeleton matcher assumes the model base starts at character index 3, so
for a variant-letter model it reads the model as `"AIK"` instead of `"IKM"`. The
comparison `trackModelBase != skeleton.ModelBase` (`AIK` != `IKM`) fails in
`WldFileCharacters.FindAdditionalAnimationsAndMeshes`, and every animation track is
skipped. `SkeletonHierarchy.AddTrackData` makes the same 3+3 assumption.

Verified directly: `globalikm_chr.wld` contains **14,774 Track fragments**
(~141 animations × 105 bones) — the data is present, just never attached.

## Fix

Two small edits.

**1. `EQ/Wld/Fragments/SkeletonHierarchy.cs`, `AddTrackData` (the animation branch):**
after taking the 3-char animation code, if the remainder does not start with this
skeleton's `ModelBase` but `Substring(1)` does, fold the variant letter into the
animation name:

```csharp
animationName = cleanedName.Substring(0, 3);
cleanedName = cleanedName.Remove(0, 3);

// Kunark+ models (e.g. Iksar) insert a variant letter between the 3-char
// animation code and the model base: "C01" + "A" + "IKM" + bone.
if (cleanedName.Length > 3 && !cleanedName.StartsWith(ModelBase) &&
    cleanedName.Substring(1).StartsWith(ModelBase))
{
    animationName += cleanedName.Substring(0, 1);
    cleanedName = cleanedName.Remove(0, 1);
}

if (cleanedName.Length < 3) { return; }
modelName = cleanedName.Substring(0, 3);
cleanedName = cleanedName.Remove(0, 3);
pieceName = cleanedName;
```

**2. `EQ/Wld/WldFileCharacters.cs`, the track match loop in
`FindAdditionalAnimationsAndMeshes`:** `ParseTrackData` still mis-parses
`ModelName` as `"AIK"`, so the exact-match filter drops the track before it reaches
`AddTrackData`. Add a raw-name fallback that checks for the model base at offset 3
or 4:

```csharp
bool matches = trackModelBase == modelBase || alternateModel == trackModelBase;
if (!matches)
{
    string clean = FragmentNameCleaner.CleanName(track, true);
    if (clean.Length >= 6 && clean.Substring(3).StartsWith(modelBase)) matches = true;
    else if (clean.Length >= 7 && clean.Substring(4).StartsWith(modelBase)) matches = true;
}
if (!matches) { continue; }
skeleton.AddTrackData(track);
```

## Result

`globalikm_chr` → `ikm.glb`: **536 KB → 30.7 MB**, **0 → 141 animation clips**
(`p01` stand, `l01`–`l12` locomotion, `c*` combat, `s*` social, `d*` death). Classic
races are unaffected — they never enter the variant branch.

Happy to open a PR if useful.
