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

- `house/`: NewGRF generator, language files, house definitions, and source art;
- `assets/`: provenance records and staged AI-assisted art inputs;
- `research/`: technical research and adjacency experiments;
- `docs/`: generated project documentation.

## Building

### Preparation

This depends on an up-to-date version of `agrf`, which in turn depends on
`grf-py`. Python 3.12 is the reference environment used by CI.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

`agrf` invokes GoRender for the existing MagicaVoxel sources. Ensure the Go
toolchain is available in `PATH` when rendering uncached sprites.

### Make

After installing dependencies, run `make` to build the NewGRF.

```sh
make
```

The output is `building.grf`.

## Licensing and contribution

Unless otherwise designated, source code and project-owned art in this
repository are licensed under GPL-2.0-or-later. Reference photographs and
generated intermediates must be recorded in `assets/manifest.csv`; do not add
material whose redistribution rights are unclear.
