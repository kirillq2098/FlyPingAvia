"""RL-02: единая версия проекта и release metadata."""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_pyproject_version_is_031() -> None:
    assert _pyproject_version() == "0.3.1"


def test_package_dunder_version() -> None:
    import flypingavia

    assert flypingavia.__version__ == _pyproject_version()


def test_fallback_matches_pyproject(monkeypatch) -> None:
    import flypingavia.version as ver

    def _boom(_name: str) -> str:
        raise ver.PackageNotFoundError(_name)

    monkeypatch.setattr(ver, "version", _boom)
    assert ver.get_version() == ver.FALLBACK_VERSION
    assert ver.FALLBACK_VERSION == _pyproject_version()


def test_metadata_when_installed() -> None:
    from importlib.metadata import PackageNotFoundError, version

    expected = _pyproject_version()
    try:
        assert version("flypingavia") == expected
    except PackageNotFoundError:
        import flypingavia.version as ver

        assert ver.get_version() == ver.FALLBACK_VERSION == expected


def test_fastapi_app_version() -> None:
    from flypingavia.api.app import create_api
    from flypingavia.config import Settings
    import flypingavia

    app = create_api(
        Settings(
            bot_token="1:T",
            app_env="test",
            webapp_dev_user_id=0,
            travelpayouts_token="",
        )
    )
    assert app.version == flypingavia.__version__ == "0.3.1"


@pytest.mark.asyncio
async def test_health_version_and_preserved_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "rl02.db"))
    monkeypatch.setenv("BOT_TOKEN", "1:T")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")

    from flypingavia.config import get_settings
    import flypingavia
    import flypingavia.db.session as db_session
    from flypingavia.api.app import create_api
    from flypingavia.db.session import init_db

    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_factory = None
    await init_db()

    app = create_api(get_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/health")
        openapi = await c.get("/openapi.json")

    assert res.status_code == 200
    body = res.json()
    assert body["version"] == flypingavia.__version__
    assert body["version"]
    assert "display_timezone" in body  # TR-04
    assert body.get("telegram_webapp_auth") is True  # WA-03
    assert "app_env" in body and "webapp_configured" in body  # WA-02
    blob = res.text.lower()
    assert "/workspace" not in blob
    assert "site-packages" not in blob
    assert openapi.status_code == 200
    assert openapi.json()["info"]["version"] == flypingavia.__version__

    if db_session._engine is not None:
        await db_session._engine.dispose()
    db_session._engine = None
    db_session._session_factory = None
    get_settings.cache_clear()


def test_readme_and_changelog_and_backlog() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")
    backlog = (ROOT / "docs/FEATURE_BACKLOG.md").read_text(encoding="utf-8")

    assert "0.3.1" in readme
    assert "python -m flypingavia --version" in readme
    assert re.search(r"## \[0\.3\.1\]", changelog)
    assert re.search(r"## \[0\.3\.0\]", changelog)
    assert re.search(
        r"### RL-02[^\n]*\n(?:.*\n)*?- \*\*Статус:\*\* Done",
        backlog,
    )
    assert "| 11 | RL-02 |" in backlog and "Done |" in backlog.split("| 11 | RL-02 |")[1][:80]


def test_no_runtime_020_in_python() -> None:
    py_files = list((ROOT / "flypingavia").rglob("*.py"))
    offenders = []
    for path in py_files:
        text = path.read_text(encoding="utf-8")
        if 'version="0.2.0"' in text or "version = \"0.2.0\"" in text:
            offenders.append(str(path.relative_to(ROOT)))
        if re.search(r'__version__\s*=\s*"0\.[12]\.0"', text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_dockerfile_app_version_label() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG APP_VERSION=0.3.1" in text
    assert "org.opencontainers.image.version=$APP_VERSION" in text
    assert "pip install" in text and "--no-deps" in text


def test_cli_version_subprocess(tmp_path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    # Avoid picking up real tokens / writing into project data/
    env.pop("BOT_TOKEN", None)
    env.pop("TELEGRAM_TOKEN", None)
    env["APP_ENV"] = "test"
    env["DB_PATH"] = str(tmp_path / "should-not-create.db")

    for flag in ("--version", "-V"):
        proc = subprocess.run(
            [sys.executable, "-m", "flypingavia", flag],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
        assert len(lines) == 1
        assert lines[0] == "FlyPingAvia 0.3.1"
        assert "Traceback" not in (proc.stderr or "")
        assert not (tmp_path / "should-not-create.db").exists()
        # no sqlite file created under cwd
        assert list(tmp_path.glob("*.db")) == []


def test_version_module_constants() -> None:
    from flypingavia.version import FALLBACK_VERSION, PACKAGE_NAME

    assert PACKAGE_NAME == "flypingavia"
    assert FALLBACK_VERSION == "0.3.1"
