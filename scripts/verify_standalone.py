"""Bounded offline acceptance of a packaged Skill in an isolated process/directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import venv
import zipfile


def verify(output, archive=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="marketlens-acceptance-") as directory:
        # Windows TEMP may use an 8.3 alias while report paths resolve to long names.
        isolated = Path(directory).resolve()
        home = isolated / "empty-home"
        home.mkdir()
        env = {k: v for k, v in os.environ.items()
               if k not in {"PYTHONPATH", "PYTHONHOME", "CODEX_HOME", "VIRTUAL_ENV"}
               and not k.startswith("RESEARCH_WORKBENCH_")}
        for key in list(env):
            if any(word in key.upper() for word in ("MARKETLENS", "AUTHOR_DATA", "COMPONENT_PATH")):
                del env[key]
        env.update(HOME=str(home), USERPROFILE=str(home), XDG_CACHE_HOME=str(home / "cache"),
                   APPDATA=str(home / "appdata"), LOCALAPPDATA=str(home / "local"),
                   PYTHONNOUSERSITE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        package = isolated / "input.zip"
        if archive:
            package.write_bytes(Path(archive).read_bytes())
        else:
            subprocess.run([sys.executable, str(Path(__file__).with_name("build_package.py")),
                            "--output", str(package)], check=True, capture_output=True)
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        with zipfile.ZipFile(package) as zipped:
            names = zipped.namelist()
            assert not any(".." in Path(n).parts or Path(n).is_absolute() for n in names)
            assert not any(".git" in Path(n).parts or "__pycache__" in Path(n).parts
                           or Path(n).suffix in {".pdf", ".sqlite3", ".csv"} for n in names)
            zipped.extractall(isolated / "installed")
        root = isolated / "installed" / "marketlens"
        assert (root / "SKILL.md").is_file()
        links = []
        for document in root.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                if "://" not in target and not target.startswith("#"):
                    assert (document.parent / target.split("#")[0]).exists(), target
                    links.append(target)
        agents = (root / "agents/openai.yaml").read_text(encoding="utf-8")
        assert "display_name:" in agents and "$marketlens" in agents
        virtual = isolated / "venv"
        venv.EnvBuilder(with_pip=False).create(virtual)
        python = virtual / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        records = []

        def run(args, expected=0):
            result = subprocess.run([str(python), *args], cwd=root, env=env,
                                    capture_output=True, text=True, encoding="utf-8")
            records.append({"args": args, "returncode": result.returncode,
                            "stdout": result.stdout, "stderr": result.stderr})
            assert result.returncode == expected, records[-1]
            return result

        probe = run(["-I", "-c", "import sys,json,importlib.util; "
                     "sys.path.insert(0,'scripts'); import marketlens.engine as e; "
                     "import marketlens.demo,marketlens.narrative; "
                     "print(json.dumps({'sys_path':sys.path,'engine_origin':e.__file__,"
                     "'module_origins':{k:v.__file__ for k,v in sys.modules.items() if k.startswith('marketlens')},"
                     "'python':sys.version,'prefix':sys.prefix,'base_prefix':sys.base_prefix,"
                     "'yaml_present':importlib.util.find_spec('yaml') is not None}))"])
        origins = json.loads(probe.stdout)
        assert Path(origins["engine_origin"]).is_relative_to(root)
        assert all(Path(p).is_relative_to(root) for p in origins["module_origins"].values())
        assert not origins["yaml_present"]
        for path in origins["sys_path"]:
            resolved = (root / path).resolve() if path else root
            allowed = [root, virtual, Path(origins["base_prefix"])]
            assert any(resolved.is_relative_to(p.resolve()) for p in allowed), path
        result = run(["scripts/run.py", "demo", "--db", "work/demo.sqlite3",
                      "--out-dir", "work/demo-results"])
        paths = json.loads(result.stdout)
        snapshot = json.loads(Path(paths["snapshot"]).read_text(encoding="utf-8"))
        report = Path(paths["report"]).read_text(encoding="utf-8")
        assert snapshot["demo"] is True and snapshot["version"] == "v3-pilot-0.1"
        card = next(c for c in snapshot["cards"] if c["instrument"] == "SSE:510300")
        assert card["identity"].startswith("未知") and card["history_count"] == 179
        assert card["amount_percentile"] == 100 and card["net_share_change"] == -1_000_000
        assert card["net_creation_value_estimate"] < 0
        assert "合成" in report and "不是概率" in report
        for value in paths.values():
            assert Path(value).is_relative_to(root) and Path(value).is_file()
        frozen = Path(paths["snapshot"]).read_bytes()
        run(["scripts/run.py", "replay", "--db", "work/demo.sqlite3", "--demo",
             "--run-id", snapshot["run_id"], "--out-dir", "work/demo-results"])
        assert Path(paths["snapshot"]).read_bytes() == frozen
        # Missing available_at is an explicit error, never a zero or current-time fallback.
        (root / "work/bad.csv").write_text("date,instrument\n2026-10-09,SSE:510300\n", encoding="utf-8")
        bad = run(["scripts/run.py", "import", "--db", "work/bad.sqlite3", "--kind", "market",
                   "--input", "work/bad.csv", "--source", "synthetic-invalid"], 2)
        assert "列名" in bad.stderr
        (root / "work/unknown-time.json").write_text(json.dumps({
            "as_of": "2026-10-09T18:00:00+08:00", "claims": [],
            "evidence": [{"id": "unknown-time"}]}), encoding="utf-8")
        unknown = run(["scripts/run.py", "narrative", "--input", "work/unknown-time.json",
                       "--out-dir", "work/unknown-results"])
        unknown_snapshot = json.loads(Path(json.loads(unknown.stdout)["snapshot"]).read_text(encoding="utf-8"))
        assert unknown_snapshot["available_evidence"] == []
        assert "可用时间未知" in unknown_snapshot["excluded_evidence"][0]["reason"]
        notices = {n: (root / n).is_file() for n in ["LICENSE", "THIRD_PARTY_NOTICES.md"]}
        if not archive:
            assert all(notices.values())
            run(["scripts/build_package.py", "--output", "work/package.zip"])
            refusal = run(["scripts/build_package.py", "--output", "work/package.zip"], 1)
            assert "Refusing to overwrite" in refusal.stderr
        evidence = {"scope": "directory/process isolation; host still contains other repositories",
                    "archive_sha256": digest, "archive_files": names, "dependencies": "Python standard library only; venv without pip",
                    "origins": origins, "commands": records, "notices": notices,
                    "checked_local_links": links, "result": "standalone offline CLI passed",
                    "not_verified": ["natural-language Skill discovery", "visual acceptance", "real market sources", "cross-repository integration"]}
        (output / "acceptance.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "demo-snapshot.json").write_bytes(frozen)
        (output / "demo-report.md").write_text(report, encoding="utf-8")
        print(json.dumps({"result": evidence["result"], "archive_sha256": digest,
                          "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--archive")
    args = parser.parse_args()
    verify(args.output, args.archive)
