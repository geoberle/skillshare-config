# Hearth's existing rack workflows

Use this reference for work under Hearth's `rack/` directory. It records the layout inspected on 26 October 2026; read the target README and Makefile for current commands and dependencies.

## UniFi Flex 2.5G PoE

`rack/unifi-flex-2.5g-poe/` uses CadQuery for mechanical parts and Blender for scenes. `cad/build_concept.py` generates STEP/STL and intersection reports against original rack geometry. It is a concept with image-derived port positions and unconfirmed cable, ventilation and fastener dimensions.

Use the Makefile's existing generate/inspect/scene/render targets as appropriate. `render` reads the preserved scene; after CAD changes, `scene` must rebuild it first. Appearance-only Blender lettering is not part of the generated front STL. The separate Python environment uses the project's `requirements.txt`; the shared build123d environment does not replace CadQuery.

## LabStack Mini

`rack/labstack-mini/` uses Blender for named **Blende** and **Schrift** material bodies plus a shared `Pi-Halterung`, grouped on two plates. Keep Blende → logical slot 1 and Schrift → logical slot 2; these roles do not prescribe colours, products or physical nozzles. Read the current README, requirements and generator for the current insert/interface design and print transforms rather than copying coordinates or orientations from an earlier design.

Generate the delivered H2D 3MF from separate body meshes and the two-plate assembly list through native Bambu Studio with complete H2D profiles. Replace custom Bambu XML/ZIP packaging when updating the project's export path; preserve Blender modeling, body/plate assignments and print transforms. Keep editable CAD source and meshes as the model handoff when print inputs are still undecided. A printer-neutral 3MF is not required. See [native H2D project generation](tools.md#native-h2d-project-generation).

The user reports successful PETG-CF/PLA printing (29 October 2026); exact product variants, printer/process parameters and test conditions were not supplied here. Record that experience within its known scope when preparing a print project.

After removing material from the carrier's bed-facing side, review its orientation and overhangs again. Minimum Z=0 and one connected mesh do not establish support-free printing. Native geometry verification and a Bambu import/export roundtrip do not prove printability; trial-slice and review each plate for a concrete print project. The shared slicing helper's one-plate/one-assembly limit does not cover this entire model.

Scene/render targets additionally use CadQuery to prepare rack and switch assets. Read their current Makefile dependencies before running visualization-only work. Render the exported model and preserve the project's original meshes, attribution and parameter source; no workflow migration is implied.

Preserve cached upstream originals and their source/license records. Neither workflow needs conversion to build123d or a new MCP adapter merely to use the shared skill.
