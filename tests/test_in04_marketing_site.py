"""IN-04: marketing website packaging (Next.js) for flyping.ru."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"


def test_website_is_nextjs_app_router() -> None:
    assert (WEBSITE / "package.json").is_file()
    pkg = (WEBSITE / "package.json").read_text(encoding="utf-8")
    assert '"next"' in pkg
    assert '"build": "next build"' in pkg
    assert (WEBSITE / "app" / "page.tsx").is_file()
    assert (WEBSITE / "Dockerfile").is_file()
    cfg = (WEBSITE / "next.config.ts").read_text(encoding="utf-8")
    assert 'output: "standalone"' in cfg


def test_website_env_example_production_domains() -> None:
    env = (WEBSITE / ".env.example").read_text(encoding="utf-8")
    assert "https://flyping.ru" in env
    assert "FlyPingAvia_Bot" in env
    assert "t.me/FlyPingAvia_Bot" in env
    assert "localhost" not in env
    assert "trycloudflare" not in env


def test_website_does_not_call_flyping_api() -> None:
    sources = list(WEBSITE.rglob("*.{ts,tsx,js,jsx,mjs}"))
    # pathlib rglob brace not supported — manual
    sources = [
        p
        for p in WEBSITE.rglob("*")
        if p.suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs"}
        and "node_modules" not in p.parts
        and ".next" not in p.parts
    ]
    blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in sources)
    assert "api.flyping.ru" not in blob
    assert "/api/health" not in blob
    assert "localhost:8080" not in blob


def test_compose_and_nginx_separate_site_from_miniapp() -> None:
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "flyping-site" in compose
    assert "127.0.0.1" in compose and "3000" in compose
    nginx = (ROOT / "deploy" / "nginx" / "flyping.conf").read_text(encoding="utf-8")
    assert "upstream flyping_site" in nginx
    assert "proxy_pass http://flyping_site" in nginx
    # Mini App / API still on flyping_app
    assert "server_name app.flyping.ru" in nginx
    assert "server_name api.flyping.ru" in nginx
    assert "proxy_pass http://flyping_app" in nginx


def test_rollback_and_deploy_landing_scripts_exist() -> None:
    deploy = ROOT / "deploy" / "scripts" / "deploy-landing.sh"
    rollback = ROOT / "deploy" / "scripts" / "rollback-landing.sh"
    assert deploy.is_file() and rollback.is_file()
    assert "landing-stub-" in deploy.read_text(encoding="utf-8")
    assert "landing-stub-" in rollback.read_text(encoding="utf-8")
    assert "nginx -t" in rollback.read_text(encoding="utf-8")


def test_version_unchanged() -> None:
    from flypingavia.version import __version__

    assert __version__ == "0.3.0"
