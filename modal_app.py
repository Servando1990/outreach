from __future__ import annotations

import modal


app = modal.App("lightfield-parallel-prospect-engine")
image = modal.Image.debian_slim(python_version="3.12").uv_sync().add_local_python_source("automation")


@app.function(image=image)
def discover(query: str, limit: int = 10, dry_run: bool = True) -> list[dict]:
    from automation.main import run_discover

    return run_discover(query=query, limit=limit, dry_run=dry_run)


@app.function(image=image)
def backfill(csv_path: str | None = None, limit: int | None = None, dry_run: bool = True) -> list[dict]:
    from automation.main import run_backfill

    return run_backfill(csv_path=csv_path, limit=limit, dry_run=dry_run)


@app.function(image=image)
@modal.asgi_app()
def web():
    from automation.api.webhooks import create_app

    return create_app()
