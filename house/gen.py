#!/usr/bin/env python
import argparse
import os
import shutil
import subprocess
from pathlib import Path


def get_string_manager():
    import grf

    s = grf.StringManager()
    s.import_lang_dir("house/lang", default_lang_file="english-uk.lng")

    return s


def gen(args):
    from house.nml_gen import build

    build()

    nmlc = os.environ.get("NMLC") or shutil.which("nmlc") or ".venv/bin/nmlc"
    subprocess.run(
        [
            nmlc,
            "-l",
            "house/lang",
            "--default-lang=english-uk.lng",
            "building/building.nml",
            "--grf",
            "building.grf",
        ],
        check=True,
    )


def docs(args):
    from house.lib.docgen import gen_docs, build_docs
    from house.lib.png_houses import load_png_houses

    houses = load_png_houses(Path("assets/manifest.csv"), get_string_manager())
    # Generate content (markdown files, po files, images)
    gen_docs(get_string_manager(), houses)

    # Build HTML documentation for all languages
    docs_dir = Path(__file__).parent.parent / "docs"
    if not build_docs(docs_dir):
        raise RuntimeError("Documentation build failed")


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(required=True)

    gen_parser = subparsers.add_parser("gen")
    gen_parser.set_defaults(func=gen)

    doc_parser = subparsers.add_parser("doc")
    doc_parser.set_defaults(func=docs)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
