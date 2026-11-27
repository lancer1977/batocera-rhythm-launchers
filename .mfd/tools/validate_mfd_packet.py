#!/usr/bin/env python3
"""Validate a Mapped-Frontier build packet or approval brief's required structure."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REQUIRED = (
    "Intent",
    "Acceptance criteria",
    "Current behavior",
    "Baseline declaration",
    "Application surface inventory",
    "Capability and proof coverage",
    "Behavior map",
    "UI proof",
    "Public-app Product Profile",
    "Technical contract",
    "Runner capability assessment",
    "Verification map",
    "Verification Strategy",
    "Autonomy and verification matrix",
    "Sub-plan reviews",
    "Per-project merge policy",
    "Delivery map",
    "Blockers",
    "Future requirements",
    "Open decisions",
    "Approval",
    "Deviations",
    "Release controls and closeout evidence",
)
BRIEF_REQUIRED = (
    "Decision requested",
    "Outcome and non-goals",
    "Acceptance criteria",
    "Experience and behavior",
    "Boundaries requiring judgment",
    "Verification summary",
    "Verification strategy",
    "Consequential sub-plan review summary",
    "Autonomy and verification checkpoints",
    "Runner decision",
    "Delivery summary",
    "Risks and unresolved decisions",
    "Per-project merge policy",
    "Blockers",
    "Future requirements",
    "Open decisions",
    "Approval record",
    "Requested changes",
    "Material-deviation return",
    "Closeout delivery",
)
DEPLOYMENT_SECTION = "Deployment contract"
CLOSEOUT_SECTION = "Release closeout record"
MERGE_OVERRIDE_SECTION = "Merge policy override (optional)"
MERGE_OVERRIDE_FIELDS = (
    "Override integration branch",
    "Override required checks",
    "Override test tiers",
    "Auto-merge allowed",
    "Extra approval paths",
)
ALWAYS_APPROVAL_FIELD = "Always-approval categories (fixed, cannot be removed by an override)"
# Always mandatory: an override can never drop these, and a packet always gates them.
MANDATORY_APPROVAL_CATEGORIES = (
    "Secrets",
    "Production infrastructure",
    "Deployment",
    "Release",
)
# Operator gate only when the packet's live-settings field is YES (workstation-kit#2829, #2868).
CONDITIONAL_APPROVAL_CATEGORIES = (
    "Auth",
    "Security",
    "CI infrastructure",
)
LIVE_SETTINGS_FIELD = "Live-settings change (auth/security/CI)"
ALWAYS_TOUCHED_FIELD = "Always-approval category touched (secrets/production infrastructure/deployment/release)"
PROTECTED_BRANCHES = {"main", "master", "prod", "production", "release"}
PROTECTED_BRANCH_PREFIXES = ("release/", "release-", "prod/", "production/")
DEPLOYMENT_FIELDS = (
    "Target environments",
    "Deployment authority (separate from approval)",
    "Source commit",
    "Immutable artifact / digest",
    "Rollout record",
    "Authenticated smoke proof",
    "Rollback target",
    "Live verification result",
    "Deferred drift / follow-up issue",
)
PACKET_MARKERS = (
    "| Requirement | Scenario | Validation | Expected evidence |",
    "| Order | GitHub issue / card | Requirement / scenario | Dependencies | Validation |",
    "| Test tier | Command | Required | CI job name |",
    "| Blocker | Owner | Unblock condition |",
    "| Decision | Options | Recommendation |",
    "| Requirement | Kind | Owner | Needed by |",
    "- Target branch:",
    "- Approved commit or immutable revision:",
    "- Required checks:",
)
BRIEF_MARKERS = (
    "| Requirement | Scenario | Planned validation | Expected evidence |",
    "| Order | GitHub issue / card | Outcome | Dependencies |",
    "| Blocker | Owner | Unblock condition |",
    "| Decision | Options | Recommendation |",
    "- Required checks:",
    "- Owning GitHub issue:",
)


def sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^## (.+?)\s*$", text, re.MULTILINE))
    return {m.group(1): text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip() for i, m in enumerate(matches)}


def front_matter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    return match.group(1) if match else ""


def field_value(text: str, name: str) -> str | None:
    match = re.search(rf"^- {re.escape(name)}:[ \t]*(.*?)[ \t]*$", text, re.MULTILINE)
    return match.group(1) if match else None


def deployment_failures(text: str, template: bool) -> list[str]:
    failures = [
        f"missing required section: {name}"
        for name in (DEPLOYMENT_SECTION, CLOSEOUT_SECTION)
        if f"### {name}" not in text
    ]
    applicability = field_value(text, "Deployment applicability")
    if applicability is None:
        failures.append("missing required field: - Deployment applicability:")
        return failures
    for name in DEPLOYMENT_FIELDS:
        if field_value(text, name) is None:
            failures.append(f"missing required field: - {name}:")
    if template:
        return failures
    if applicability.startswith("Not applicable:"):
        if not applicability.removeprefix("Not applicable:").strip():
            failures.append("deployment applicability needs a not-applicable reason")
    elif applicability == "Applies":
        for name in DEPLOYMENT_FIELDS:
            value = field_value(text, name)
            if not value or value == "Pending" or re.fullmatch(r"[A-Z_]+", value):
                failures.append(f"deployment evidence is required when deployment applies: {name}")
    else:
        failures.append("deployment applicability must be Applies or Not applicable: REASON")
    return failures


def live_settings_answer(text: str) -> str | None:
    """Return the packet's live-settings answer (YES/NO/other), or None when the field is absent."""
    value = field_value(text, LIVE_SETTINGS_FIELD)
    return None if value is None else value.strip().upper()


def decision_value(text: str) -> str | None:
    match = re.search(r"^- Decision:[ \t]*(.*?)[ \t]*$", text, re.MULTILINE)
    return match.group(1) if match else None


def _yes_no_answer(text: str, name: str, template: bool) -> tuple[str | None, list[str]]:
    """Return (answer, failures) for one YES/NO approval-gate field."""
    answer = field_value(text, name)
    if answer is None:
        return None, []
    answer = answer.strip().upper()
    allowed = {"YES", "NO", "YES_OR_NO"} if template else {"YES", "NO"}
    if answer not in allowed:
        return answer, [f"{name} must be YES or NO"]
    return answer, []


def live_settings_failures(text: str, template: bool) -> list[str]:
    live, failures = _yes_no_answer(text, LIVE_SETTINGS_FIELD, template)
    if live is None:
        if template:
            return [f"missing required field: - {LIVE_SETTINGS_FIELD}:"]
        # Packets written before this field existed keep the conservative generic pending check.
        return []
    touched, touched_failures = _yes_no_answer(text, ALWAYS_TOUCHED_FIELD, template)
    failures.extend(touched_failures)
    if touched is None:
        failures.append(f"missing required field: - {ALWAYS_TOUCHED_FIELD}:")
    if template or failures:
        return failures
    # The operator gate applies to a live-settings change, to any always-approval category the
    # packet touches (secrets, production infrastructure, deployment, release), and whenever
    # deployment applies. Only plain code-only auth/security/CI work skips it.
    reasons = []
    if live == "YES":
        reasons.append(f"a live-settings change to {', '.join(CONDITIONAL_APPROVAL_CATEGORIES)}")
    if touched == "YES":
        reasons.append(f"a change touching {', '.join(MANDATORY_APPROVAL_CATEGORIES)}")
    if field_value(text, "Deployment applicability") == "Applies" and touched != "YES":
        reasons.append("a deployment (Deployment applicability: Applies)")
    if reasons:
        decision = decision_value(text)
        if decision is None or decision == "Pending" or not re.match(r"approv", decision, re.IGNORECASE):
            failures.append(
                f"{' and '.join(reasons)} needs a recorded operator approval: "
                "- Decision must be an approval (Approved...), not Pending or a rejection"
            )
    return failures


def merge_policy_override_failures(text: str, template: bool) -> list[str]:
    if f"### {MERGE_OVERRIDE_SECTION}" not in text:
        return []
    failures = [
        f"missing required field: - {name}:"
        for name in MERGE_OVERRIDE_FIELDS
        if field_value(text, name) is None
    ]
    always_approval = field_value(text, ALWAYS_APPROVAL_FIELD)
    if always_approval is None:
        failures.append(f"missing required field: - {ALWAYS_APPROVAL_FIELD}:")
    else:
        missing = [
            category
            for category in MANDATORY_APPROVAL_CATEGORIES
            if category.lower() not in always_approval.lower()
        ]
        if missing:
            failures.append(
                "merge policy override attempts to drop mandatory approval "
                f"categories: {', '.join(missing)}"
            )
    if template:
        return failures
    branch = (field_value(text, "Override integration branch") or "").strip().strip("`").lower()
    if branch in PROTECTED_BRANCHES or branch.startswith(PROTECTED_BRANCH_PREFIXES):
        failures.append(
            "merge policy override: integration branch cannot be a default, "
            f"release or production branch: {branch}"
        )
    tiers = field_value(text, "Override test tiers") or ""
    unit = re.search(r"\bunit\s*=\s*(\w+)", tiers, re.IGNORECASE)
    if unit is None or unit.group(1).lower() != "yes":
        failures.append("merge policy override: test tiers must keep unit=yes")
    auto_merge_allowed = field_value(text, "Auto-merge allowed")
    if auto_merge_allowed is not None and auto_merge_allowed.strip().lower() not in {"yes", "no"}:
        failures.append("merge policy override: Auto-merge allowed must be yes or no")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--brief", action="store_true", help="validate an approval brief instead of a build packet")
    args = parser.parse_args()
    text = args.packet.read_text(encoding="utf-8")
    found = sections(text)
    kind = "brief" if args.brief else "packet"
    required = BRIEF_REQUIRED if args.brief else REQUIRED
    failures = []
    if not re.search(r"^schema: 2\s*$", front_matter(text), re.MULTILINE):
        failures.append("missing required front matter: schema: 2")
    failures.extend(f"missing required section: {name}" for name in required if name not in found)
    if not args.brief:
        failures.extend(deployment_failures(text, args.template))
        failures.extend(live_settings_failures(text, args.template))
        failures.extend(merge_policy_override_failures(text, args.template))
    markers = BRIEF_MARKERS if args.brief else PACKET_MARKERS
    failures.extend(f"missing required field: {marker}" for marker in markers if marker not in text)
    if not args.template:
        for placeholder in ("FEATURE", "OWNER", "ISSUE_URL", "YYYY-MM-DD", "COMMAND_OR_CHECK", "EVIDENCE_LOCATION"):
            if re.search(rf"\b{placeholder}\b", text):
                failures.append(f"unresolved placeholder: {placeholder}")
        # The Live-settings answer owns the decision gate: NO needs no operator decision and YES
        # is checked in live_settings_failures. Packets without the field keep the legacy check.
        if live_settings_answer(text) is None and re.search(
            r"^- Decision:\s*Pending\s*$", text, re.MULTILINE
        ):
            failures.append("approval decision is still pending")
    if failures:
        print("\n".join(f"FAIL: {failure}" for failure in failures))
        return 1
    print(f"OK: valid MFD {kind} {'template' if args.template else 'document'}: {args.packet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
