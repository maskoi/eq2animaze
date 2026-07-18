# LanternExtractor animation fix (Kunark+ variant-letter models)

**Symptom:** character models from Kunark and later — Iksar (`ikm`/`ikf`), Vah Shir
(`kem`/`kef`), and others — export to glTF with **zero animations**, while classic
races (Human, Elf, etc.) export with a full ~30–140 clip set. The model comes out a
frozen statue in its bind pose.

**Impact for us:** with no animations we had no real stand pose, so every foot/knee/
arm angle was hand-guessed — the source of ~55 versions of broken stances.

## Root cause

EQ names animation tracks `[animation][model][bone]`:

- Classic races: `C01ELMPE` = `C01` + `ELM` + `PE` — clean 3 + 3.
- Kunark+ races: `C01AIKMPEBIP01` = `C01` + **`A`** + `IKM` + `PEBIP01` — a **variant
  letter** sits between the 3-char animation code and the 3-char model base.

LanternExtractor hard-codes the model base to start at character index 3. For a
variant-letter model it reads the model as `"AIK"` instead of `"IKM"`, the match
`trackModelBase != skeleton.ModelBase` (`AIK != IKM`) fails, and **every animation
track is skipped**. Classic races have no variant letter, so nobody noticed.

Verified directly in the archive: `globalikm_chr.wld` contains **14,774 Track
fragments** (~141 animations × 105 bones). The data was always present.

## The fix (two edits)

### 1. `EQ/Wld/Fragments/SkeletonHierarchy.cs` — `AddTrackData`

After taking the 3-char animation code, if the remaining string does not start with
this skeleton's `ModelBase` but `Substring(1)` does, a variant letter is present —
fold it into the animation name and shift:

```csharp
animationName = cleanedName.Substring(0, 3);
cleanedName = cleanedName.Remove(0, 3);

if (cleanedName.Length > 3 && !cleanedName.StartsWith(ModelBase) &&
    cleanedName.Substring(1).StartsWith(ModelBase))
{
    animationName += cleanedName.Substring(0, 1);
    cleanedName = cleanedName.Remove(0, 1);
}
```

### 2. `EQ/Wld/WldFileCharacters.cs` — track/skeleton match loop

`ParseTrackData`'s fixed 3+3 split still misreads `ModelName` as `"AIK"`, so the
exact-string filter drops the track before it ever reaches `AddTrackData`. Add a
raw-name fallback that checks for the model base at offset 3 **or** 4:

```csharp
bool matches = trackModelBase == modelBase || alternateModel == trackModelBase;
if (!matches)
{
    string clean = FragmentNameCleaner.CleanName(track, true);
    if (clean.Length >= 6 && clean.Substring(3).StartsWith(modelBase)) matches = true;
    else if (clean.Length >= 7 && clean.Substring(4).StartsWith(modelBase)) matches = true;
}
if (!matches) continue;
```

## Result

`ikm.glb`: **536 KB → 30.7 MB**, **0 → 141 animation clips** (`p01` stand, `l01`–`l12`
locomotion, `c*` combat, `s*` social, `d*` death). Classic races unaffected (they never
enter the variant branch). The fix generalizes to every variant-letter race.

## Build

```
dotnet build LanternExtractor.sln -c Release
```
Requires .NET SDK (net6.0 target builds on the 8.0 SDK).
