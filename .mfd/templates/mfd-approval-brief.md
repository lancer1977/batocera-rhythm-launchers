---
title: Mapped-Frontier Approval Brief - FEATURE
status: draft
schema: 2
owner: OWNER
issue: ISSUE_URL
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# Mapped-Frontier Phase 0 Approval Brief: FEATURE

## Decision requested

Review this single brief and record one decision on the owning GitHub issue.

- [ ] Approve the immutable packet revision for scoped implementation
- [ ] Request changes listed below
- [ ] Reject the proposed direction

Approval alone does not authorize a merge; a brief by itself does not confer
execution authority. It does not authorize merge, deployment, issue closure,
secret access or rotation, external communication, or a production-success
claim. Phase 0 approval plus a valid `.mfd/project.yaml` v2
`merge_policy`, with every required check passing on the current PR head,
pre-authorizes agents to merge ordinary validated PRs to `dev`. Changes touching
secrets, authentication or authorization, security, production infrastructure,
deployment, or release promotion still require the owner's explicit OK. Every
promotion to `main` requires the owner's explicit OK and a green `dev` smoke
test. Phase 0 approval does not authorize deployment, issue closure, secret
access or rotation, external communication, or a production-success claim.

The v2 project profile is `.mfd/project.yaml`: `schema_version: 2`, with
`merge_policy` fields `integration_branch: dev`, `protected_branch: main`,
`required_checks`, `test_tiers` (`unit`, `integration`, `automation`, or `smoke`
entries each containing `command` and `required_for: [dev|main]`),
`require_pr_tests`, `test_paths`, `escalate_paths`, and `escalate_labels`. A merge to `main` requires a green `dev` smoke test. A PR qualifies only if (1) it adds or updates tests covering the behavior it changes, or states why none apply (pure docs or pure config), and (2) the PR gate runs the profile's general `unit` tier with every required check green on the current head.

## Outcome and non-goals

**Outcome:** ONE_PARAGRAPH_OUTCOME

**Non-goals:** EXPLICIT_NON_GOALS

## Acceptance criteria

- [ ] AC1: CRITERION

## Experience and behavior

- Baseline mode and rationale: BASELINE_MODE_AND_RATIONALE
- Surface inventory and dispositions: SURFACE_INVENTORY_SUMMARY
- Capability-to-proof coverage: CAPABILITY_PROOF_COVERAGE
- Primary journeys: JOURNEY_SUMMARY
- Failure and recovery states: FAILURE_STATE_SUMMARY
- Project package ID, immutable revision/digest and repository membership: PROJECT_PACKAGE_REF_OR_NOT_APPLICABLE
- Storyboard/concept, approved vs candidate designs, actual version captures and historical gaps: PACKAGE_EVIDENCE_SUMMARY
- Publication scope: PRIVATE_OR_SEPARATELY_AUTHORIZED_SANITIZED_REVISION
- UI proof: LIVING_ARTIFACT_PAGE_LINK_OR_NOT_APPLICABLE
  - Declaration: DECLARATION_VALUE, copied exactly from the build packet `## UI proof` block (one of `not-applicable`, `existing-authority`, or `candidate-generation`).
  - Reason and owner: REASON_AND_OWNER from the build packet. For `not-applicable`, state the one scope reason and owner only; no per-surface lines follow.
  - Per-surface lines (applicable packets only; one line per governed surface): SURFACE_ID; class CLASS (authority, implementation, candidate, or historical); approval status APPROVAL_STATUS (not-approved, candidate, or approved); desktop viewport DESKTOP_COVERAGE; mobile viewport MOBILE_COVERAGE; operational states STATE_COVERAGE; gap count GAP_COUNT.
  - Gaps (every gap, with owner, status, and blocker): GAP_OWNER_STATUS_BLOCKER. Status is one of unassessed, missing, unavailable, planned, or resolved; `resolved` needs resolution evidence. A gap allows a draft and blocks approval.
  - Immutable references (per artifact): IMMUTABLE_LOCATOR_AND_BARE_SHA256, or the stated absence of an artifact, which is also a gap. Branch names, `latest`, moving URLs, and bare filenames are not authority.
  - Approval: this brief states no approval for any row without a named human decision that cites the surface and bare SHA-256. Candidate and historical rows are not approved.
  - Core warning: the proof-readiness semantic rules are Core-owned and are not enforced by pinned Core 1.3.0. This summary is not Core validation, and no Core diagnostic is claimed here.
  - Boundary (verbatim): Candidate proofs are not approved. Visual approval requires human review against the cited proof. Screenshots and schema checks do not prove behavior, accessibility, authorization, persistence, live health, or visual fidelity.

For frontend work, the linked living-artifact page is the reviewable UI-proof
authority; this brief pins it by immutable permalink/revision. The page names
the design authority and shared stylebook/design-system decision, covered
routes/roles/viewports/themes/states, supporting candidate or approved proofs,
accessibility and reconstruction expectations, and any explicit exclusions. A
screenshot alone is not UI proof. Use `Not applicable — REASON` when the scoped
work has no graphical/frontend UI.

For reconstruction mode, approval confirms that code was used as functional
evidence, historical screenshots only as context, and the linked future-state
proof revisions as the intended design authority. Every discovered surface and
material capability must be covered or explicitly retired.

## Boundaries requiring judgment

- Technical and integration: TECHNICAL_BOUNDARIES
- Authentication, authorization, privacy, and security: SECURITY_BOUNDARIES
- Data, migration, and retention: DATA_BOUNDARIES
- Operations, rollout, rollback, and cost: OPERATIONAL_BOUNDARIES

## Verification summary

| Requirement | Scenario | Planned validation | Expected evidence |
| --- | --- | --- | --- |
| R1 | S1 | VALIDATION | EVIDENCE |

## Verification strategy

- Strategy page: VERIFICATION_STRATEGY_LINK_OR_NOT_APPLICABLE
- Unit coverage: UNIT_COVERAGE_SUMMARY
- Integration / contract coverage: INTEGRATION_COVERAGE_SUMMARY
- End-to-end / consumer happy paths: END_TO_END_COVERAGE_SUMMARY
- Post-build live smoke: LIVE_SMOKE_COVERAGE_SUMMARY
- Explicit non-applicable layers and reasons: NOT_APPLICABLE_LAYER_SUMMARY

Every feature-shaped requirement has all applicable layers represented. A green
build, unit test, HTTP 200, or screenshot alone is not delivery proof for a
runnable feature. Libraries include unit and consumer-contract/install proof;
websites and apps include end-to-end happy-path and post-build live proof.

## Consequential sub-plan review summary

- Classification and rationale: SUB_PLAN_REVIEW_CLASSIFICATION
- Consequential conclusions or degraded limitations: SUB_PLAN_REVIEW_CONCLUSIONS
- Unresolved product-owner decisions: SUB_PLAN_REVIEW_DECISIONS
- Immutable sanitized evidence: SUB_PLAN_REVIEW_EVIDENCE

Summarize conclusions only; do not reproduce candidate plans. Analysts and the
conductor advise, while the product owner retains the single Phase 0 decision.

## Autonomy and verification checkpoints

| Requirement | Human decision before execution or release | Agent may do autonomously | Proof required before handoff |
| --- | --- | --- | --- |
| R1 | HUMAN_CHECKPOINT | IMPLEMENTATION_AND_REPAIR_BOUNDARY | AUTOMATED_UI_OR_LIVE_EVIDENCE |

Human approval is required for a new user-visible direction, permission or trust
boundary, data retention/migration, cost commitment, destructive action, or
production release. Within this approved boundary, agents may implement, run
the listed tests, repair deterministic failures, and address review feedback.

## Runner decision

- Trust level: TRUST_LEVEL
- Required operating system, architecture, capabilities, and resources: RUNNER_REQUIREMENTS
- Network, secret-access, and repository boundary: RUNNER_BOUNDARY
- Selected runner and availability evidence, or provisioning blocker: RUNNER_ASSIGNMENT
- Required labels and exact-match validation: RUNNER_LABEL_VALIDATION
- Offline or busy fallback: RUNNER_FALLBACK

Runner selection does not authorize runner provisioning, secret access,
workflow routing, deployment, or use of an unrelated repository runner.

## Delivery summary

| Order | GitHub issue / card | Outcome | Dependencies |
| --- | --- | --- | --- |
| 1 | ISSUE_URL | CARD_OUTCOME | DEPENDENCIES |

## Risks and unresolved decisions

| Item | Owner | Recommendation or decision needed |
| --- | --- | --- |
| RISK_OR_DECISION | OWNER | RECOMMENDATION |

## Per-project merge policy

- Required checks: REQUIRED_CHECKS_FROM_PROJECT_YAML
- Integration branch: INTEGRATION_BRANCH
- Protected branch: PROTECTED_BRANCH

| Test tier | Command | Required | CI job name |
| --- | --- | --- | --- |
| Unit | COMMAND | Yes/No | CI_JOB_NAME |
| Integration | COMMAND | Yes/No | CI_JOB_NAME |
| Automation | COMMAND | Yes/No | CI_JOB_NAME |

## Blockers

| Blocker | Owner | Unblock condition |
| --- | --- | --- |
| BLOCKER | OWNER | UNBLOCK_CONDITION |

## Future requirements

- Secrets: SECRETS_SOURCED_VIA_SECURITY_BOT_OR_INFISICAL_OR_NONE
- Infrastructure: INFRASTRUCTURE_REQUIREMENTS_OR_NONE
- Hardware: HARDWARE_REQUIREMENTS_OR_NONE

## Open decisions

| Decision | Options | Recommendation |
| --- | --- | --- |
| DECISION | OPTION_A_OR_OPTION_B | RECOMMENDATION |

## Approval record

- Owning GitHub issue: ISSUE_URL
- Immutable build-packet revision: COMMIT_OR_PERMALINK
- Product owner: OWNER
- Decision: Pending
- Decision comment: Pending
- Decision date: Pending

## Requested changes

<!-- Fill only when the product owner requests changes. -->

None.

## Material-deviation return

If execution crosses an approved boundary, return a focused brief containing:

- what changed and why
- affected requirement and scenario IDs
- changed UI, technical, security, data, or operational risk
- affected cards and evidence
- the recommended decision

## Closeout delivery

At Phase 4, update or reply to this brief with links to:

- delivered PRs and exact revisions
- requirement and scenario evidence
- UI proof comparisons
- whether the work is done (merged green into `dev`) or shipped (promoted to
  `main` after the milestone retrospective and QA)
- at the milestone promotion gate, a golden-path live check for every shipped
  feature-shaped requirement, run with a live-capable tool (browser
  automation, target device/emulator, or equivalent) — required there, not
  per dev PR; requirements with no live surface record Not applicable with a
  reason instead of a silent skip
- deployment and live verification when applicable
- recorded deviations and their approvals
- rollback evidence
- deferred follow-up issues
