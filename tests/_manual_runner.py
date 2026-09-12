"""
Manual test runner used ONLY to verify this repo works in environments
without pytest installed (e.g. sandboxed build environments). If you have
pytest, just run `pytest` from the repo root instead — these test files are
written in standard pytest style with a `tmp_path` fixture.

This script fakes `tmp_path` with tempfile.TemporaryDirectory() and calls
every `test_*` function it finds, module by module.
"""

import inspect
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

MODULES = [
    "test_scope_guard",
    "test_ledger",
    "test_evidence_store",
    "test_skill_registry",
    "test_content_isolation",
]

passed = 0
failed = 0

for mod_name in MODULES:
    mod = __import__(mod_name)
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if not name.startswith("test_"):
            continue
        sig = inspect.signature(fn)
        try:
            if "tmp_path" in sig.parameters:
                with tempfile.TemporaryDirectory() as td:
                    fn(Path(td))
            else:
                fn()
            print(f"PASS  {mod_name}.{name}")
            passed += 1
        except Exception:
            print(f"FAIL  {mod_name}.{name}")
            traceback.print_exc()
            failed += 1

print()
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
