# Requirements and design evidence

Use a versioned project-local requirements file before construction or remix. Keep requirements proportional to the part: record facts that affect design or acceptance, and mark unknowns rather than filling them with plausible numbers.

## Separate three meanings of tolerance

- **Nominal interface and modeled clearance:** what the design intends; specify diametral versus per-side clearance, units and mating part dimensions. Derive hole/pocket dimensions from those named values.
- **Numerical check tolerance:** permitted difference when comparing exported CAD to its nominal dimensions, in mm or mm³. This tests the CAD/export pipeline; it is not printer accuracy.
- **Physical manufacturing tolerance:** acceptable measured deviation of the printed part. Establish using the selected material, orientation and process, with calibration/fit coupons where needed. Keep slicer compensation separate so it is not applied twice.

For snap fits, heatsets, screws and bearings, use confirmed mating dimensions, manufacturer drawings and applicable standards. Check remaining ligaments and assembly access as well as hole diameters. A point/box probe proves material or clearance locally; full diameter, ligament, swept-volume or mating checks may require the project's native geometry assertions.

## Manufacturing intent

For a reusable model, record service temperature/environment, expected load magnitude/direction/duration, material constraints, logical material roles and intended bed face. For a print project, record selected product profiles, colours, nozzle mapping, support/process profiles and applicable datasheet sources. Mark provisional choices explicitly; missing final colours or hotend assignments do not block generation and slicing under a declared setup. Verification against actual loaded filaments remains pending until those choices are confirmed and the updated setup is recalculated and sliced. Leave manufacturing choices undecided at the model stage when they do not affect geometry. Treat load direction relative to printed layers, unsupported spans, bed contact and support removal as design inputs. Avoid treating infill percentage or bulk datasheet strength as a structural qualification of a printed component.

Accept user-reported successful prints as scoped observations in the existing project record: record the combination, application and known printer/process conditions, and leave unknown details explicit. PETG-CF plus PLA having worked for the user is evidence for that use, not a reason to reject it categorically or assume universal compatibility, strength or adhesion. Distinguish a helper's unsupported input from a physically unsuitable combination.

For critical mating/cosmetic surfaces, record where support contact is acceptable. Prefer a geometry/orientation that meets those requirements; changes such as splitting a part or changing material remain design decisions to discuss when they alter the requested design. Coupons should isolate the critical interface or lettering using the intended orientation and process.

Review moisture/drying instructions, nozzle/feeder compatibility and plate guidance for the actual filament. Carbon-filled material is not automatically the right material for a compliant snap feature. Use primary product guidance rather than assuming all products in a family behave alike. Relevant sources include the [Bambu PETG-CF product guidance](https://bambulab.com/es-mx/filament/petg-cf), the selected product's datasheet and the versioned local profiles. Follow current product instructions rather than copying generic temperatures into the skill.

## STEP requirement format

`tools/verify_step.py` accepts JSON with `schema: 1` and these geometry fields. Include at least one actual geometry requirement; omit fields that do not apply. Nominal and tolerance are explicit, finite and nonnegative. This example is a synthetic **40 × 20 × 4 mm test plate**, not a hardware dimension or universal design rule:

```json
{
  "schema": 1,
  "solid_count": 1,
  "dimensions_mm": {
    "x": {"nominal": 40, "tolerance": 0.01},
    "y": {"nominal": 20, "tolerance": 0.01},
    "z": {"nominal": 4, "tolerance": 0.01}
  },
  "probes": [
    {"name": "hole at origin", "center_mm": [0, 0, 2], "size_mm": [1, 1, 1], "expect": "empty"}
  ],
  "walls": [
    {"name": "floor section", "plane": "XZ", "at_mm": 0, "min_mm": 0.8}
  ],
  "manufacturing": {
    "material": {"product": "Bambu PLA Basic", "source": "record the selected datasheet or profile"},
    "orientation": {"bed_face": "XY at Z=0", "reason": "record bed contact and load direction"},
    "support": {"policy": "forbidden"},
    "fits": [],
    "loads": [],
    "physical_tests": ["record required calibration, fit and load tests with their actual status"]
  }
}
```

Optional `volume_mm3` takes the same `{nominal, tolerance}` structure. `walls` uses XY at Z, XZ at Y, YZ at X. The minimum is sampled in that section, not a global proof. `probes` uses **center and positive box sizes**, not two corners: solid means at least 98% material, empty at most 2%. A probe wholly outside model bounds fails instead of claiming it proves a hole. Use finer project assertions when those fractions are not appropriate.

`manufacturing` is an open project record carried into the report and explicitly **not evaluated** by the geometry helper. Its fields are not a machine-enforced certification schema. Material selection must also match the slicer report; physical fit/load claims need their own evidence. Record custom checks and outcomes beside this file, rather than assuming a generic helper understands every engineering requirement.

## Manufacturing evidence format

Keep the geometry fields above and add `artifacts` and `requirements` inside `manufacturing`. Artifact and specimen paths are relative to the requirements file. This illustrative mapping uses named checks from the helper reports:

```json
{
  "artifacts": {"geometry": "out/panel.step", "print": "out/panel.3mf"},
  "requirements": [
    {"id": "WIDTH", "stage": "geometry", "check": "dimension_x_mm"},
    {"id": "MATERIAL", "stage": "slicing", "check": "material_products", "expected": ["Bambu PLA Basic @BBL H2D", "Bambu PLA Basic @BBL H2D"]},
    {"id": "COLOURS", "stage": "slicing", "check": "filament_colour", "expected": "#202020;#EEEEEE"},
    {"id": "PARTS", "stage": "slicing", "check": "part_filament_slots", "expected": {"Blende": 1, "Schrift": 2}},
    {"id": "PIN-FIT", "stage": "physical", "check": "fit_2", "expected": true, "specimen": "calibration/pin-fit/coupon.stl"}
  ]
}
```

This is the contents of `manufacturing`, not a complete requirements file. Each ID is unique. `stage` selects a geometry, slicing or physical report; `check` names exactly one finding. For geometry, acceptance already lives in the hashed geometry specification; `expected` is optional. Slicing/physical requirements require an explicit `expected` matching the finding's actual value (fit observations must be JSON booleans). Use the exact selected profile product name, not a generic material family.

`verify_manufacturing.py` checks model hashes, the complete geometry requirements hash, sliced archive/current profile hashes, and physical specimen/manifest/raw-record/slicing provenance. It recomputes physical findings from the records. Missing evidence or required review remains pending; failed or stale evidence cannot pass. Finalize requirements before generating reports. Editing them requires a fresh geometry check.

A coupon requirement explicitly names the coupon specimen. Passing it does not prove final-part fit or strength. Record reference-pin dimensions, the meaning of acceptable fit, printer/material/process and test conditions beside the measurement record. Print, measure and record observations before evaluating. The helper handles outer dimensional acceptance and a pin/hole fit ladder; use project-specific tests for load, creep, temperature, snap fits or other interfaces. Keep those requirements unresolved until corresponding evidence exists. Reports carry local operator observations, not independently witnessed certification.

## Sources and model representation

[build123d import/export documentation](https://build123d.readthedocs.io/en/latest/import_export.html) describes the supported representations. Prefer versioned Python source for parametrization and STEP for exact exchange. Keep original mesh geometry and attribution when remixing. For a mesh remodel, state approximation and compare required interfaces rather than claiming original feature-history recovery.
