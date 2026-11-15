"""Command-line interface: ``aiguard --help``."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from aiguard.core.errors import AIGuardError
from aiguard.core.models import ModelCreate
from aiguard.governance.compliance import render_markdown
from aiguard.security import calculate_model_hash, scan_artifact
from aiguard.security.vulnerability import SEVERITY_ORDER
from aiguard.service import AIGuard

app = typer.Typer(help="AIGuard: AI model governance and security.", no_args_is_help=True)

ACTOR = "cli"


def _print(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


def _guard() -> AIGuard:
    return AIGuard()


def _fail(exc: Exception) -> typer.Exit:
    typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
    return typer.Exit(2)


@app.command("hash")
def hash_file(path: Path) -> None:
    """Print the SHA-256 digest of a file."""
    typer.echo(calculate_model_hash(path))


@app.command()
def scan(
    path: Path,
    fail_on: Annotated[str, typer.Option(help="Exit 1 at or above this severity.")] = "high",
) -> None:
    """Statically inspect a model artifact without loading it. Needs no database."""
    if fail_on not in SEVERITY_ORDER:
        raise _fail(ValueError(f"--fail-on must be one of {', '.join(SEVERITY_ORDER)}"))
    result = scan_artifact(path)
    findings = [f.to_dict() for f in result["findings"]]
    _print({"format": result["format"], "findings": findings})
    threshold = SEVERITY_ORDER.index(fail_on)
    if any(SEVERITY_ORDER.index(f["severity"]) >= threshold for f in findings):
        raise typer.Exit(1)


@app.command()
def register(
    name: str,
    version: str,
    artifact: Path,
    framework: str = "unknown",
    owner: str = "",
    description: str = "",
    intended_use: str = "",
    impact_tier: str = "limited",
    human_oversight: str = "",
) -> None:
    """Register a model artifact and record its digest."""
    try:
        data = ModelCreate(
            name=name,
            version=version,
            framework=framework,
            artifact_path=str(artifact),
            owner=owner,
            description=description,
            intended_use=intended_use,
            impact_tier=impact_tier,  # type: ignore[arg-type]
            human_oversight=human_oversight,
        )
        _print(_guard().register_model(data, ACTOR, trusted_path=True))
    except (AIGuardError, ValueError) as exc:
        raise _fail(exc) from exc


@app.command("list")
def list_models() -> None:
    """List registered models and their governance posture."""
    _print(_guard().list_models())


@app.command()
def verify(model_id: str, artifact: Annotated[Path | None, typer.Argument()] = None) -> None:
    """Verify an artifact against the registered digest. Exit 1 on mismatch."""
    try:
        result = _guard().verify_integrity(
            model_id,
            artifact_path=str(artifact) if artifact else None,
            actor=ACTOR,
            trusted_path=True,
        )
    except AIGuardError as exc:
        raise _fail(exc) from exc
    _print(result)
    if not result["verified"]:
        raise typer.Exit(1)


@app.command()
def assess(model_id: str) -> None:
    """Run the security assessment for a registered model. Exit 1 on high findings."""
    try:
        result = _guard().assess_security(model_id, actor=ACTOR)
    except AIGuardError as exc:
        raise _fail(exc) from exc
    _print(result)
    if result["status"] != "pass":
        raise typer.Exit(1)


@app.command()
def gate(model_id: str) -> None:
    """CI/CD gate: assess risk, evaluate all policies, exit 1 if any policy fails."""
    try:
        guard = _guard()
        guard.assess_risk(model_id, ACTOR)
        result = guard.evaluate_policies(model_id, actor=ACTOR)
    except AIGuardError as exc:
        raise _fail(exc) from exc
    for item in result["results"]:
        colour = {"pass": typer.colors.GREEN, "fail": typer.colors.RED}.get(item["status"])
        typer.secho(
            f"[{item['status'].upper():<14}] {item['policy_id']}  {item['title']}", fg=colour
        )
        if item["status"] in ("fail", "error"):
            typer.echo(f"                 {item['explanation']} {item['remediation']}")
    if result["summary"]["status"] != "pass":
        raise typer.Exit(1)


@app.command()
def report(
    model_id: str,
    fmt: Annotated[str, typer.Option("--format", help="markdown or json")] = "markdown",
    output: Annotated[Path | None, typer.Option(help="Write to a file instead of stdout.")] = None,
) -> None:
    """Produce a governance evidence report."""
    try:
        data = _guard().compliance_report(model_id)
    except AIGuardError as exc:
        raise _fail(exc) from exc
    text = render_markdown(data) if fmt == "markdown" else json.dumps(data, indent=2)
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        typer.echo(text)


@app.command("audit-verify")
def audit_verify() -> None:
    """Verify the audit hash chain. Exit 1 if it is broken."""
    result = _guard().verify_audit_chain()
    _print(result)
    if not result["valid"]:
        raise typer.Exit(1)


@app.command("seed-demo")
def seed_demo() -> None:
    """Register synthetic demo models so the dashboard has data."""
    from aiguard.integrations.demo import seed_demo as run

    created = run(_guard())
    typer.echo(f"Registered {len(created)} demo model(s).")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the REST API and dashboard."""
    import uvicorn

    from aiguard.api import create_app

    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    app()
