"""Stage the static website and portable data for GitHub Pages."""
from pathlib import Path
from shutil import copy2, copytree

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "_site"
    if output.exists() and any(output.iterdir()):
        raise SystemExit("_site must be empty before building, to avoid stale files.")
    bundle = ROOT / "dist/cn-history-data.zip"
    if not bundle.is_file():
        raise SystemExit("Run python scripts/package.py before building the website.")
    output.mkdir(exist_ok=True)
    for folder in ("web", "data", "schemas", "dist"):
        copytree(ROOT / folder, output / folder)
    for name in ("index.html", "DATA_FORMAT.md"):
        copy2(ROOT / name, output / name)
    (output / ".nojekyll").touch()
    size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    print(f"Staged website: {output} ({size / 1024**2:.1f} MiB)")


if __name__ == "__main__":
    main()
