"""Helpers for user-facing application version labels."""

from __future__ import annotations


def normalize_environment(ref: str = "", explicit: str = "") -> str:
    """Return the environment name implied by a branch/ref/env value."""
    value = (explicit or ref or "").strip().lower()
    if value.startswith("refs/heads/"):
        value = value.removeprefix("refs/heads/")

    if value in {"dev", "leounib-dev", "development"}:
        return "dev"
    if value in {"nonprod", "leounib-nonprod", "staging", "stage"}:
        return "nonprod"
    if value in {"prod", "production", "main", "leounib-main"}:
        return "prod"
    return value


def display_version(base_version: str, ref: str = "", environment: str = "") -> str:
    """Build the version string shown in the app sidebar."""
    base = str(base_version or "").strip()
    env = normalize_environment(ref=ref, explicit=environment)
    if not base or not env:
        return base
    if base.endswith(f"-{env}"):
        return base
    return f"{base}-{env}"
