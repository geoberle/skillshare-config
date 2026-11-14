# Shared helper commands

Run with the workbench's existing Python environment, from any working directory. Use absolute project paths. The examples below use shell variables; substitute actual part names, paths and requirements.

```sh
WORKBENCH=/Users/goberlec/personal/3dprinting
PROJECT=/absolute/path/to/project/cad
```

## Native construction and print checks

For a b123d-print workspace (not arbitrary CadQuery/Blender scripts):

```sh
"$WORKBENCH/.venv/bin/b123d-print" --root "$PROJECT" build part_name --formats step,stl,png
"$WORKBENCH/.venv/bin/b123d-print" --root "$PROJECT" check part_name --json
"$WORKBENCH/.venv/bin/b123d-print" --root "$PROJECT" orient part_name --json
"$WORKBENCH/.venv/bin/b123d-print" --root "$PROJECT" fit part_name
```

Inspect `--help` for variant/piece selection, measurements, template coupons, mesh imports and reference comparison. Reuse native tools for those jobs. `orient` ranks candidates; the agent still chooses an orientation against load, functional-surface and support requirements. Keep generic wall/overhang thresholds distinct from calibrated material/process limits. Native checks are geometric/discretized evidence, not physical qualification.

## Verify exported STEP

```sh
"$WORKBENCH/.venv/bin/python" "$WORKBENCH/tools/verify_step.py" \
  --model "$PROJECT/output/part.step" \
  --requirements "$PROJECT/requirements.json" \
  --report "$PROJECT/output/geometry-report.json"
```

See [requirements format](requirements.md). The helper reads exported STEP without running its generator, so it also works with STEP exported by CadQuery. Reports contain checks, source/requirements hashes and the manufacturing record, explicitly marked unevaluated. Exit codes: **0** geometry requirements pass, **1** geometric requirement fails, **2** invalid input or execution error. The report is replaced on each run; a report cannot overwrite either input. Verify that the current run succeeded and its hashes still match.

This does not inspect STL/3MF topology, recognize arbitrary features, prove all walls or test assemblies/motion. Use the native project checks for those cases. A STEP export of a formerly faceted mesh remains faceted.

## Render export files

```sh
"$WORKBENCH/.venv/bin/python" "$WORKBENCH/tools/render_model.py" \
  --model "$PROJECT/output/part.step" --section XZ=0 \
  --output "$PROJECT/output/review-001"
```

Accepts STEP/STP/STL/3MF; `--section PLANE=MM` can repeat for STEP only. Creates six views in `views.png`, section PNGs and `render-report.json`. Decodes generated PNGs and rejects sections missing the model. **The agent must inspect the images.** Mesh previews use one combined color and do not validate/preserve color visually; the original file is unchanged. Keep the native Blender scene for material-aware or assembled views.

Output must be a new directory, avoiding stale previews. Exit **0** means images were generated and decoded; **2** is an input/render error. The six-view renderer can show shading artifacts; use sections and numerical checks for geometry decisions.

## Native H2D project generation

The H2D is the user's fixed printer. Keep editable CAD source and separate named meshes, then let the pinned Bambu Studio generate the print-project archive. Do not implement Bambu XML/ZIP serialization or use the native export without complete profiles: that path writes defaults even without a selected printer and produced a CLI import crash in the local test. Undecided colours and hotend assignments may use documented provisional values. Declare assumed product variants as well; verification applies to those selected profiles, not an unidentified spool. Ask for missing choices when they affect design correctness or final print approval, rather than requiring them merely to generate a 3MF.

Export each material body as an STL in millimetres in the same coordinate frame and intended print orientation. Do not individually centre or drop the bodies to the bed: raised lettering must keep its offset from its base. Generate the native `assemble.json` directly from the project's existing body/plate assignments. This is Bambu's input format, not an additional project configuration system. For example (replace absolute paths):

```json
{
  "plates": [
    {
      "plate_name": "Einschubplaettchen",
      "need_arrange": true,
      "objects": [
        {"path": "/absolute/path/to/project/cad/output/Blende.stl", "count": 1, "filaments": [1], "assemble_index": [1]},
        {"path": "/absolute/path/to/project/cad/output/Schrift.stl", "count": 1, "filaments": [2], "assemble_index": [1]}
      ]
    },
    {
      "plate_name": "Pi-Halterung",
      "need_arrange": true,
      "objects": [
        {"path": "/absolute/path/to/project/cad/output/Halterung.stl", "count": 1, "filaments": [1], "assemble_index": [0]}
      ]
    }
  ]
}
```

Within a plate, a shared positive `assemble_index` creates one object with separate material parts; zero keeps an object independent. `filaments` selects logical slots, not hotends or AMS trays. The native exporter derives names from STL filenames (the checked version appends `_1` to part names and uses `assemble_1` for the assembly); inspect exported names before passing them to name-based checks. Plate arrangement may rotate an entire assembly in X/Y while preserving the relative body positions.

Use a fresh output directory. Prepare `$PROJECT/process.json` as a full resolved copy of the saved H2D process with the intended support policy and tower placement. The following two-slot example uses PLA Basic, black/white, one slot per hotend; replace these choices for the actual print:

```sh
BAMBU=/Applications/BambuStudio.app/Contents/MacOS/BambuStudio
OUT="$PROJECT/output/h2d-001"
mkdir "$OUT" || exit 1
"$BAMBU" --debug 2 \
  --load-assemble-list "$PROJECT/assemble.json" \
  --load-settings "$WORKBENCH/profiles/slicer/h2d-engineering/machine.json;$PROJECT/process.json" \
  --load-filaments "$WORKBENCH/profiles/slicer/h2d-engineering/pla.json;$WORKBENCH/profiles/slicer/h2d-engineering/pla.json" \
  --curr-bed-type 'Engineering Plate' --nozzle-volume-type Standard,Standard \
  --filament-colour '#000000;#FFFFFF' \
  --filament-map-mode Manual --filament-map 1,2 \
  --orient 0 --arrange 1 --slice 0 \
  --export-3mf h2d.3mf --outputdir "$OUT" > "$OUT/slicer.log" 2>&1
```

Do not pass positional input model files together with `--load-assemble-list`. Supply one fully resolved filament profile and colour per slot; mixed products need their selected profiles and scoped compatibility evidence. Passing `--filament-colour` triggers native purge recalculation for both H2D nozzles, including when the supplied colours are provisional. Bambu calculates the values; the user need not provide numerical purge volumes. Before printing with changed colours, products or hotend assignments, update the setup and trigger Bambu's Re-calculate (or run the CLI with the updated explicit colours/profiles/map), then re-slice and check the result. Merely slicing again can reuse stored purge values. Check both resulting matrices and multipliers, tower toolpaths, hotend mapping, dimensions, part count and plate membership. Read each entry in `result.json.sliced_plates` and all warning/error log entries. The shared `slice_bambu.py` does not wrap this multi-plate construction path or produce its verification report; perform these checks in the project and retain commands, effective profiles, logs and artifact hashes as evidence.

Reload the delivered `h2d.3mf` and re-slice all plates into another fresh directory using the same explicit profiles, colours and hotend map, replacing `--load-assemble-list` with the archive path. Confirm geometry, assignments and toolpaths survive. On the pinned version, a project exported before slicing failed this check with `No valid nozzle found`; the sliced export passed. If an unsliced project must be reloaded, explicitly declaring `--extruder-nozzle-count 1,1 --extruder-nozzle-volume-type Standard,Standard` passed the local test. This does not replace checking the actual hardware or the final sliced archive.

Verified on 29 October 2026 with small asymmetric test bodies on two plates: native H2D generation preserved body dimensions and lettering offsets, populated both purge matrices, generated tower paths on the multicolour plate and passed a sliced-project reload/re-slice. This verifies the export mechanism; the real model still needs its own support and warning review. Export needs macOS graphics access for previews. Native logs also contain T1001/T65535/T65279 parser diagnostics and may warn about missing bundled `machine_full`/`process_full` presets despite explicitly loaded profiles; do not equate return code zero with a clean verification.

## H2D slicing

Use this helper to verify an already oriented STL or an existing named-part H2D 3MF within its one-plate/one-assembly scope. For new multi-plate project creation, use [native H2D project generation](#native-h2d-project-generation).

```sh
"$WORKBENCH/.venv/bin/python" "$WORKBENCH/tools/slice_bambu.py" \
  --model "$PROJECT/output/part.stl" --material pla --support forbidden \
  --output "$PROJECT/output/slice-001"
```

Inputs: one closed-edge STL assumed in mm, already in the intended print orientation. The selected bed face and scale are preserved, while automatic arrangement can turn the object on the bed. The extent check accepts either X/Y order within 0.05 mm with Z unchanged and reports `placement_dimension_order` as `xyz`, `yxz` or null. This identifies the matching dimension order, not the exact rotation angle; it does not accept arbitrary axis permutations or tipping. Use the project's native placement controls if an in-plane rotation is forbidden. This is a serialization/placement check, not a physical print tolerance. Accepts material choices `pla` (PLA Basic), `petg` (**PETG Translucent**), `petg-cf`, `abs`, `asa`. They refer to saved Bambu profiles, not arbitrary variants.

`--support` is required: `forbidden` disables support and requires no support toolpaths; `allowed` enables it without requiring any; `required` enables it and requires emitted support paths. Use `--process /absolute/path/process.json` for a project-local **full resolved** process profile; copy the saved process profile and make intentional changes. The helper sets support enablement from the explicit policy in a new output-local snapshot, leaving the source profile untouched. It checks emitted wall loops, infill, layer height, support type/threshold, machine/nozzles, filament name and bed temperature. Other process requirements need additional project checks or preview review.

Output must be a new directory. Files: native `result.json`, G-code, `model.gcode.3mf`, copied effective `process.json`, `slicer.log` and `slicing-report.json` with input hashes. The report also verifies ZIP integrity, decodable PNG, bed wait temperature and identical standalone/embedded G-code. Exit **0** means the checked slicing requirements pass, **1** means failure or a plate warning requiring review, **2** means no verified slicing verdict due to input/runtime error. Review the full log, including Bambu parser diagnostics such as the known T1001/T65535/T65279 messages; they are not summarized by the plate warning field.

Currently pinned to Bambu Studio **02.08.02.61**, H2D dual 0.4-mm nozzles, Standard nozzle volume and Engineering Plate. These settings must match intended hardware. On macOS the 3MF preview export needs graphics access, which can fail inside the Codex sandbox. Preserve that error report and use an approved environment for a fresh output run; do not silently disable checks.

For a Bambu 3MF containing named normal parts, declare every part and logical filament slot. Repeat materials and colours in slot order for this print setup; currently this helper accepts one material product repeated across slots:

```sh
"$WORKBENCH/.venv/bin/python" "$WORKBENCH/tools/slice_bambu.py" \
  --model "$PROJECT/output/panel.3mf" --material pla --material pla \
  --colour '#202020' --colour '#EEEEEE' --part Blende=1 --part Schrift=2 \
  --extruder-map 2,2 --support forbidden --process "$PROJECT/process.json" \
  --output "$PROJECT/output/slice-colour-001"
```

Mixed-product rejection is a helper capability limit, not a material-compatibility verdict. Use the native project slicer for a user-proven PETG-CF/PLA combination and record the application/conditions in existing requirements.

Part names/slots must match the source exactly; slots start at 1 without gaps. `--extruder-map` assigns each slot to hotend 1 or 2, **not AMS trays**. Choose it for the actual hardware/material setup; the example uses hotend 2 for both colours. Manual mode is enforced because Bambu's automatic mode can override the requested map. The report checks exported names/slots, actual slot use, colours and emitted hotend map. Multi-part mesh topology and colour geometry still need project checks and toolpath inspection.

For the pinned H2D format, `flush_volumes_matrix` contains **two consecutive row-major N × N matrices: left, then right**, where N is the project filament count. The helper requires both complete matrices, finite positive off-diagonal entries and positive per-hotend `flush_multiplier`/`flush_multiplier_fast`; diagonal zeros are expected. It compares the project values with emitted G-code. A valid left matrix must not conceal an all-zero right matrix. This is a conservative completeness check for the registered slots, not a calibrated purge-volume threshold or a reconstruction of the exact tool-change sequence. Use Bambu's Re-calculate for the actual colours/products or measured transition data; do not invent a universal volume or copy the left matrix blindly. Purging through the chute and priming on the tower serve different purposes.

When multiple slots actually print on the plate, the helper also requires `enable_prime_tower=1` in both project and G-code, and emitted `Prime tower` feature paths. A missing tower fails this shared verification path; a deliberate exception requires a project-specific check and documented review. Single-colour plates do not require a tower merely because one is enabled in the profile.

Place the cleaning tower inside the selected hotends' printable area using a project-local process profile. The native two-colour test used `wipe_tower_x: ["100"]` and `wipe_tower_y: ["220"]`; these are test placements, not universal defaults. Keep native printable-area checks enabled. Preserve Hearth's assembly and separate parts when moving packaging to native Bambu generation. The helper never uploads or starts printing, and it does not verify which physical spool or feeder is loaded.

Open the **delivered archive**, not just its source mesh, in Bambu Studio. Inspect all plates, first layers, later islands/cantilevers and every warning. Minimum Z=0 and overall dimensions do not establish that all regions grow from supported layers. After geometry removal, reassess orientation and support instead of retaining assembly coordinates by default. Floating-region/cantilever warnings remain unresolved until an appropriate orientation/support/bridge assessment exists. A geometry import/export roundtrip does not test printability. This helper accepts exactly one plate and one assembly; a multi-plate project needs the project's native slicing/review path for each plate.

Primary CLI reference: [Bambu Studio command-line usage](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage). Settings precedence is CLI, then loaded profiles, then embedded settings; that is why checking emitted G-code matters. Full profiles are required for loading, not unresolved inheritance snippets. The installed version's `--help` is the authority for available flags.

### Support detection during 3MF generation

For Bambu Studio 02.08.02.61, the support-necessity check emits `It seems object … has floating regions/floating cantilever/large overhangs. Please re-orient the object or enable support generation.` The CLI includes this in the sliced plate's `warning_message` in `result.json` and logs it as a slicing warning. A successful return code can accompany it. Capture all slicing-warning entries from `slicer.log` as well: the CLI assigns successive warnings to the same field, so that field can retain only the last message. Treat other warnings separately rather than interpreting every warning as a request for support.

Use native Bambu generation/slicing for this loop on the H2D print project. Keep support intent in the CAD requirements; persist slicer support overrides in the print project:

1. Trial-slice each plate using the intended orientation, resolved profiles and normal validity checks. For an unsupported candidate, keep support disabled in the diagnostic copy, including object overrides. Preserve the original warnings and identify the affected plate and object unambiguously. `--slice N` selects a one-based plate; `--slice 0` selects all plates.
2. If support is allowed/required and its contact and removal meet the project requirements, enable automatic support for the affected object in Bambu Studio and save a new H2D project. For an independent object in an assembly list, native `print_params: {"enable_support": "1"}` supplies the override during generation. For a grouped object, apply support to the assembly in Bambu's object settings. Let Bambu serialize the result; preserve part assignments, meshes, transforms and other objects. Do not apply a global support change to unrelated plates. With forbidden or unspecified support, report the finding and resolve the orientation/design or policy first.
3. Re-slice into a fresh output directory once. Confirm the exported 3MF retains the intended object override and that the affected plate's G-code contains actual `Support`/`Support interface` feature paths. Inspect their coverage under the flagged regions, bed anchoring, critical-surface contact and removal access in Bambu. Bambu skips its necessity check when support is enabled, so disappearance of the warning alone is not proof that support is adequate. Preserve pre/post diagnostics and bind the final evidence to the final archive. Any remaining warning, missing paths or uncertain coverage leaves the plate needing review; stop automatic retries there.

The shared `slice_bambu.py --support allowed|required` sets a global process snapshot for its one-plate/one-assembly case; it does not implement this per-object generation loop. In multi-plate native CLI exports, confirm all expected plates/objects remain in the delivered project: a selected-plate sliced export may contain only that selection. Keep the complete generated source project and the per-plate sliced evidence distinct.

Verified on the Pi-Halterung in a temporary copy on 29 October 2026: support disabled produced the exact cantilever warning and no support paths; an object-level override with global support still disabled cleared the warning and emitted 22 support/interface feature blocks. This establishes detection and serialization, not complete support coverage or physical print success. Native behavior: [support-necessity check](https://github.com/bambulab/BambuStudio/blob/v02.08.02.61/src/libslic3r/PrintObject.cpp#L787) and [CLI warning reporting](https://github.com/bambulab/BambuStudio/blob/v02.08.02.61/src/BambuStudio.cpp#L6561).

## Physical dimension and fit coupons

```sh
"$WORKBENCH/.venv/bin/python" "$WORKBENCH/tools/calibration.py" create \
  --reference-diameter 4 --diametral-clearance 0.1 --diametral-clearance 0.2 \
  --diametral-clearance 0.3 --thickness 3 --tolerance 0.15 \
  --output "$PROJECT/calibration/pin-fit"
```

These are example values; use the actual measured reference diameter and required dimensional acceptance. Creates STEP/STL, a hashed coupon manifest and a blank measurement record. Clearances are **diametral**, not per side. The corner notch marks the first-hole end; hole IDs and centres are in `coupon.json`. This simple hole ladder is for pin/hole fits and outer dimensions. It does not reproduce snap fits, threads, heatsets or lettering.

Slice the generated STL using the intended orientation, material and process. Bind `measurements.json.slicing_report_sha256` to that report's SHA-256. After an operator prints and measures the specimen, record operator, ISO date, instrument, X/Y/Z dimensions and each fit as true/false; leave unknowns null. Define what an acceptable fit means before testing against the specified real reference. Never populate physical values from CAD or invent observations.

```sh
"$WORKBENCH/.venv/bin/python" "$WORKBENCH/tools/calibration.py" evaluate \
  --coupon "$PROJECT/calibration/pin-fit/coupon.json" \
  --measurements "$PROJECT/calibration/pin-fit/measurements.json" \
  --slicing-report "$PROJECT/calibration/pin-fit/slice/slicing-report.json" \
  --report "$PROJECT/calibration/pin-fit/physical-report.json"
```

Exit **0** means complete operator records with dimensions inside the declared tolerance; status is `recorded`. Exit **1** means failed dimensions or pending measurements/provenance; **2** means invalid input. A false fit remains a recorded observation and must be compared with the intended result in manufacturing requirements. The helper validates specimen, manifest, measurement and slicing hashes. It does not independently witness measurements or qualify strength.

## Bind manufacturing requirements to evidence

```sh
"$WORKBENCH/.venv/bin/python" "$WORKBENCH/tools/verify_manufacturing.py" \
  --requirements "$PROJECT/requirements.json" \
  --geometry "$PROJECT/output/geometry-report.json" \
  --slicing "$PROJECT/output/slice-001/slicing-report.json" \
  --physical "$PROJECT/calibration/pin-fit/physical-report.json" \
  --report "$PROJECT/output/manufacturing-report.json"
```

See [evidence format](requirements.md). Omit unavailable stage reports: their requirements remain pending. Exit **0** means all explicitly listed requirements pass, **1** means pending/failed evidence, **2** means invalid input. Changed requirements invalidate geometry evidence; changed artifacts, slicing profiles or measurement records invalidate their evidence. Regenerate dependent reports. Unlisted service conditions and checks are outside this verdict.

The pinned implementation stores purge matrices in [PrintConfig.cpp](https://github.com/bambulab/BambuStudio/blob/v02.08.02.61/src/libslic3r/PrintConfig.cpp); per-nozzle matrix handling is in [Plater.cpp](https://github.com/bambulab/BambuStudio/blob/v02.08.02.61/src/slic3r/GUI/Plater.cpp). Revalidate their layout when changing the slicer version.
