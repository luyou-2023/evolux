"""midscenejs_luke — Luke 自研视觉 UI 自动化引擎桥接（Playwright）。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from evolux_constants import get_evolux_home


def luke_engine_root() -> Path:
    return Path(__file__).resolve().parents[1] / "midscenejs_luke"


def ui_test_workspace(home: Path | None = None) -> Path:
    return (home or get_evolux_home()) / "ui-tests"


def node_bin() -> str:
    return os.environ.get("EVOLUX_NODE_BIN") or shutil.which("node") or "node"


def npm_bin() -> str:
    return os.environ.get("EVOLUX_NPM_BIN") or shutil.which("npm") or "npm"


def npx_bin() -> str:
    return os.environ.get("EVOLUX_NPX_BIN") or shutil.which("npx") or "npx"


def engine_installed(root: Path | None = None) -> bool:
    base = root or luke_engine_root()
    return (base / "node_modules" / "playwright").exists()


def ensure_engine_deps(root: Path | None = None, *, timeout: int = 300) -> tuple[bool, str]:
    base = root or luke_engine_root()
    if engine_installed(base):
        return True, str(base)
    if not (base / "package.json").exists():
        return False, f"missing midscenejs_luke at {base}"
    try:
        completed = subprocess.run(
            [npm_bin(), "install", "--no-fund", "--no-audit"],
            cwd=str(base),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, str(exc)
    if completed.returncode != 0:
        return False, (completed.stderr or completed.stdout)[-2000:]
    return engine_installed(base), str(base)


def run_luke_workflow(payload: dict[str, Any], *, timeout: int = 180) -> dict[str, Any]:
    root = luke_engine_root()
    ok, detail = ensure_engine_deps(root)
    if not ok:
        return {"success": False, "error": f"midscenejs_luke deps not ready: {detail}"}

    runner = root / "runner.mjs"
    try:
        completed = subprocess.run(
            [node_bin(), str(runner), json.dumps(payload, ensure_ascii=False)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"workflow timed out after {timeout}s"}

    if completed.returncode != 0:
        return {
            "success": False,
            "error": (completed.stderr or completed.stdout)[-4000:],
            "exit_code": completed.returncode,
        }
    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {"success": False, "error": "invalid JSON from runner", "raw": completed.stdout[-2000:]}


def init_ui_test_project(home: Path | None = None) -> Path:
    target = ui_test_workspace(home)
    engine = luke_engine_root()
    templates = engine / "templates"
    target.mkdir(parents=True, exist_ok=True)

    shutil.copy2(templates / "playwright.config.mjs", target / "playwright.config.mjs")
    e2e = target / "e2e"
    e2e.mkdir(parents=True, exist_ok=True)
    shutil.copy2(templates / "e2e" / "fixture.mjs", e2e / "fixture.mjs")
    shutil.copy2(templates / "e2e" / "smoke.spec.mjs", e2e / "smoke.spec.mjs")

    pkg = {
        "name": "evolux-ui-tests",
        "private": True,
        "type": "module",
        "dependencies": {
            "midscenejs_luke": f"file:{engine.resolve()}",
            "playwright": "^1.52.0",
            "@playwright/test": "^1.52.0",
        },
    }
    (target / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
    readme = target / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Evolux UI Tests (midscenejs_luke + Playwright)\n\n"
            "Set vision model env:\n\n"
            "```bash\n"
            "export MIDSCENE_LUKE_MODEL_BASE_URL=https://api.deepseek.com/v1\n"
            "export MIDSCENE_LUKE_MODEL_API_KEY=...\n"
            "export MIDSCENE_LUKE_MODEL_NAME=deepseek-chat\n"
            "npm install && npx playwright install chromium\n"
            "npx playwright test\n"
            "```\n",
            encoding="utf-8",
        )
    return target


def run_playwright_test(spec: str, *, home: Path | None = None, timeout: int = 300) -> dict[str, Any]:
    workspace = ui_test_workspace(home)
    if not (workspace / "package.json").exists():
        init_ui_test_project(home)
    root = luke_engine_root()
    ok, detail = ensure_engine_deps(root)
    if not ok:
        return {"success": False, "error": detail}

    subprocess.run([npm_bin(), "install"], cwd=str(workspace), capture_output=True, text=True)

    spec_path = Path(spec).expanduser()
    if not spec_path.is_absolute():
        spec_path = (workspace / spec).resolve()
    if not spec_path.exists():
        return {"success": False, "error": f"spec not found: {spec_path}"}

    try:
        completed = subprocess.run(
            [npx_bin(), "playwright", "test", str(spec_path)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"playwright timed out after {timeout}s"}

    return {
        "success": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-4000:],
        "spec": str(spec_path),
        "engine": "midscenejs_luke",
    }
