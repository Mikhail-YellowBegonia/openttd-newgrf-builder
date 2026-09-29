# China Set: Buildings

![Docs](https://github.com/OpenTTD-China-Set/China-Set-Buildings/actions/workflows/sphinx-gh-pages.yml/badge.svg)
![Build](https://github.com/OpenTTD-China-Set/China-Set-Buildings/actions/workflows/build.yml/badge.svg)

<!-- start elevator-pitch -->
This repository contains the source code and art pipeline for a 32bpp OpenTTD
NewGRF featuring Chinese buildings across different eras and settlement
densities.
<!-- end elevator-pitch -->

The project is developed under the
[OpenTTD-China-Set](https://github.com/OpenTTD-China-Set) organization. The
current development lead is
[Mikhail-YellowBegonia](https://github.com/Mikhail-YellowBegonia). Existing
contributors and credits are preserved in the generated documentation.

## Project status

Active pre-release development began on 25 September 2026. The current targets
are:

- playable demo by 30 September 2026;
- first public release by 5 October 2026;
- a scalable AI-assisted art pipeline constrained by real-world references;
- research into Action 2/VarAction2 for adjacency-aware buildings.

See [the development roadmap](docs/roadmap_zh.md) and
[the research index](research/README.md) for the working plan.

## Repository layout

- `house/`: PNG-driven NewGRF generator, language files, and house definitions;
- `house/legacy_voxel/`: notes for the previous VOX/GoRender prototype;
- `assets/`: provenance records and staged AI-assisted art inputs;
- `assets/work_orders/`: machine-readable building art tasks and calibration parameters;
- `research/`: technical research and adjacency experiments;
- `docs/`: generated project documentation.

## Building

### Preparation

The production build uses OpenTTD's NML compiler (`nmlc`). Python 3.12 is the
reference environment used by CI; Pillow derives normal and zi2 images from
the approved zi4 master.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

The old grf-py/GoRender documentation generator is retained as an optional
legacy path; install `requirements-legacy.txt` only when working on that code.

The production art path consumes approved PNG files from the asset manifest.
The historical VOX/GoRender prototype is retained for reference only and is
not imported by the default generator.

### Make

The first two commands are available during the research phase and do not
require GoRender or any approved image yet:

```sh
make validate
make lock
```

After installing the Python dependencies, run `make package` to check the
manifest, build the NewGRF, and write checksums for the result. The
shorter `make` target remains available for the GRF-only build.

```sh
make package
```

The outputs are `building.grf`, `building.grf.sha256`, and
`assets/manifests/manifest.lock.yaml`.

For the basic 1x1 art workflow, see [the work order guide](docs/work-order_zh.md).
The local helper supports work-order creation, calibration previews, repeatable
processing, and registration of reviewed `zi4` PNGs into the manifest.

For the complete human-in-the-loop workflow, start the local web workbench:

```sh
make workbench
# open http://127.0.0.1:4173/workbench/
```

The workbench records building/NML parameters and references, accepts external
AI generation results, provides polygon masking and XY calibration, runs the
deterministic `zi4`/slice pipeline, and exposes review, manifest registration,
and full GRF build actions. AI service credentials are not stored by the app.

The build generates a readable NML file at `building/building.nml` from the
approved manifest. The current basic path supports 1x1 and 2x2 Houses; for a
2x2 full-canvas source, the north tile carries the building image and the
other three tiles use transparent sprites.

## Licensing and contribution

Unless otherwise designated, source code and project-owned art in this
repository are licensed under GPL-2.0-or-later. Reference photographs and
generated intermediates must be recorded in `assets/manifest.csv`; do not add
material whose redistribution rights are unclear.
