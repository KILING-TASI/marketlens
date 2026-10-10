"""Build a source-only Skill archive with licensing notices."""
import argparse
from pathlib import Path
import zipfile


def build(output):
    root = Path(__file__).resolve().parent.parent
    mandatory = ["SKILL.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
                 "CONTRIBUTING.md", "SECURITY.md", "LIFECYCLE.md",
                 "RIGHTS_INDEX.json", "SHARED_CODE.json"]
    for name in mandatory:
        if not (root / name).is_file():
            raise ValueError(f"Required package file missing: {name}")
    files = [root / name for name in mandatory + ["README.en.md", "CHANGELOG.md", "README.md", "BEGINNER.md", "try_demo.py", "Start-Demo.cmd", "Start-Demo.sh", "EXPANSION.md", "AUDIT_SCOPE.md", "pyproject.toml", "setup.py", "_build_skill.py", "MANIFEST.in"]]
    files.extend(root / name for name in ["examples/teaching-report.html", "examples/teaching-report.jpg", "examples/teaching-report-note.md"])
    for directory in ["agents", "references", "scripts", "docs", "tools"]:
        files.extend(p for p in (root / directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts
                     and p.suffix.lower() in {".py", ".md", ".yaml", ".yml"})
    files.extend((root / "examples/expansion-teaching").glob("*.json"))
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("Refusing to overwrite an existing archive")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            archive.write(path, Path("marketlens") / path.relative_to(root))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive integrity check failed")
        assert all("marketlens/" + name in archive.namelist() for name in mandatory)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    print(build(parser.parse_args().output))
