#!/usr/bin/env python3
"""Validate the dependency-free, JSON-compatible MFD deployment YAML profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = {
    "schema_version",
    "ownership",
    "environments",
    "artifact",
    "smoke_checks",
    "rollback",
    "drift",
}
ALLOWED = {
    "profile": REQUIRED,
    "ownership": {"deployment_owner", "source_path"},
    "environment": {"name", "approval_required"},
    "artifact": {"immutable", "convention"},
    "smoke_check": {"name", "command"},
    "rollback": {"reference"},
    "drift": {"command", "expectation"},
}
CONTRACT_WHITESPACE = frozenset(
    "".join(chr(code_point) for code_point in range(0x0009, 0x000E))
    + "".join(chr(code_point) for code_point in range(0x001C, 0x0021))
    + "\u0085\u00a0\u1680"
    + "".join(chr(code_point) for code_point in range(0x2000, 0x200B))
    + "\u2028\u2029\u202f\u205f\u3000"
)


def nonempty(value: object) -> bool:
    return isinstance(value, str) and any(
        character not in CONTRACT_WHITESPACE for character in value
    )


def unknown_fields(value: object, shape: str, path: str) -> list[str]:
    if not isinstance(value, dict):
        return []
    return [
        f"unknown field: {path}.{key}"
        for key in sorted(value.keys() - ALLOWED[shape])
    ]


def validate(profile: object) -> list[str]:
    if not isinstance(profile, dict):
        return ["profile must be an object"]
    failures = [f"missing required field: {key}" for key in sorted(REQUIRED - profile.keys())]
    failures.extend(unknown_fields(profile, "profile", "$"))
    schema_version = profile.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, (int, float))
        or schema_version != 1
    ):
        failures.append("schema_version must be numeric integer 1")
    ownership = profile.get("ownership")
    failures.extend(unknown_fields(ownership, "ownership", "$.ownership"))
    if not isinstance(ownership, dict) or not all(
        nonempty(ownership.get(key)) for key in ("deployment_owner", "source_path")
    ):
        failures.append("ownership requires deployment_owner and source_path")
    environments = profile.get("environments")
    if isinstance(environments, list):
        for index, environment in enumerate(environments):
            failures.extend(
                unknown_fields(environment, "environment", f"$.environments[{index}]")
            )
    if not isinstance(environments, list) or not environments or not all(
        isinstance(item, dict)
        and nonempty(item.get("name"))
        and isinstance(item.get("approval_required"), bool)
        for item in environments
    ):
        failures.append("environments require name and boolean approval_required")
    artifact = profile.get("artifact")
    failures.extend(unknown_fields(artifact, "artifact", "$.artifact"))
    if not isinstance(artifact, dict) or artifact.get("immutable") is not True or not nonempty(
        artifact.get("convention")
    ):
        failures.append("artifact must be immutable and define a convention")
    smoke_checks = profile.get("smoke_checks")
    if isinstance(smoke_checks, list):
        for index, smoke_check in enumerate(smoke_checks):
            failures.extend(
                unknown_fields(smoke_check, "smoke_check", f"$.smoke_checks[{index}]")
            )
    if not isinstance(smoke_checks, list) or not smoke_checks or not all(
        isinstance(item, dict)
        and nonempty(item.get("name"))
        and nonempty(item.get("command"))
        for item in smoke_checks
    ):
        failures.append("smoke_checks require name and command")
    for section, fields in (("rollback", ("reference",)), ("drift", ("command", "expectation"))):
        value = profile.get(section)
        failures.extend(unknown_fields(value, section, f"$.{section}"))
        if not isinstance(value, dict) or not all(nonempty(value.get(field)) for field in fields):
            failures.append(f"{section} requires {', '.join(fields)}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAIL: cannot read deployment profile: {error}")
        return 1
    failures = validate(profile)
    if failures:
        print("\n".join(f"FAIL: {failure}" for failure in failures))
        return 1
    print(f"OK: valid deployment profile: {args.profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
