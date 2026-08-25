"""Fast static checks on the Tano Retail addons.

Catches XML syntax errors, Python syntax errors, manifest problems and
missing data files in seconds, instead of after a multi-minute Odoo install.

Usage:  python scripts/preflight.py
"""

import ast
import pathlib
import sys
from xml.etree import ElementTree

ADDONS = pathlib.Path(__file__).resolve().parent.parent / "addons"
problems = []

modules = sorted(p for p in ADDONS.iterdir() if p.is_dir() and (p / "__manifest__.py").exists())

for module in modules:
    # Manifest must be a literal dict.
    try:
        manifest = ast.literal_eval((module / "__manifest__.py").read_text())
    except Exception as exc:
        problems.append(f"{module.name}: unreadable manifest: {exc}")
        continue

    for key in ("name", "version", "license", "depends", "data"):
        if key not in manifest:
            problems.append(f"{module.name}: manifest missing '{key}'")

    version = manifest.get("version", "")
    if not str(version).startswith("18.0"):
        problems.append(f"{module.name}: version '{version}' is not 18.0.x")

    # Every declared data file must exist and, if XML, must parse.
    for rel in manifest.get("data", []):
        path = module / rel
        if not path.exists():
            problems.append(f"{module.name}: data file missing: {rel}")
            continue
        if path.suffix == ".xml":
            try:
                ElementTree.parse(path)
            except Exception as exc:
                problems.append(f"{module.name}: bad XML in {rel}: {exc}")

    # Every Python file must compile.
    for py in module.rglob("*.py"):
        try:
            ast.parse(py.read_text(), filename=str(py))
        except SyntaxError as exc:
            rel = py.relative_to(module)
            problems.append(f"{module.name}: syntax error in {rel}: {exc}")

    # Any XML in the tree, even if not declared, should still be well formed.
    for xml in module.rglob("*.xml"):
        try:
            ElementTree.parse(xml)
        except Exception as exc:
            rel = xml.relative_to(module)
            problems.append(f"{module.name}: bad XML in {rel}: {exc}")

print(f"Checked {len(modules)} modules: {', '.join(m.name for m in modules)}")
if problems:
    print(f"\n{len(problems)} problem(s):")
    for problem in problems:
        print(f"  - {problem}")
    sys.exit(1)
print("All checks passed.")
