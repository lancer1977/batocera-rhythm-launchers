---
title: Mapped-Frontier Build Packet - FEATURE
status: draft
schema: 2
owner: OWNER
issue: ISSUE_URL
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# Mapped-Frontier Build Packet: FEATURE

<!-- Replace instructional comments and placeholders before requesting approval. -->

## Intent

<!-- State the problem, target users, desired outcome, non-goals, and measurable success. -->

## Current behavior

<!-- Record current workflows, stable behavior, gaps, constraints, and evidence. -->

## Baseline declaration

Mode: BASELINE_MODE

Rationale: BASELINE_RATIONALE

Current implementation evidence: CURRENT_IMPLEMENTATION_EVIDENCE

Historical evidence policy: HISTORICAL_EVIDENCE_POLICY

<!-- Use exactly one mode: live-baseline, reconstruction, or greenfield.
For reconstruction, explain why the current UI is unavailable or untrustworthy.
Code is functional evidence, historical captures are context, proposed images
are candidate authority, and only explicit human approval establishes design
authority. -->

## Application surface inventory

| Surface | Route / entry point | Functional source | Roles | Disposition | Future proof |
| --- | --- | --- | --- | --- | --- |
| SURFACE_ID | ROUTE_OR_ENTRY_POINT | PAGE_VIEWMODEL_HANDLER_OR_SERVICE | USER_OR_ROLE | SURFACE_DISPOSITION | PROOF_LINK_OR_EXPLICIT_RETIREMENT |

<!-- For reconstruction mode, include every discovered route or meaningful
surface. Use retain, redesign, merge, split, relocate, or retire. -->

## Capability and proof coverage

| Capability | Source evidence | User outcome / behavior | Future surface | Proof / state | Disposition |
| --- | --- | --- | --- | --- | --- |
| CAPABILITY_ID | CODE_DOC_OR_HISTORICAL_EVIDENCE | USER_VISIBLE_OUTCOME | FUTURE_SURFACE | PROOF_AND_STATE | covered |

<!-- For reconstruction mode, include every material ViewModel property,
command, form, handler, role-sensitive behavior, integration, and applicable
healthy, busy, degraded, stale, offline, empty, reconnecting, or
permission-limited state. Use covered or retired; missing and unresolved
coverage blocks approval. -->

## Behavior map

<!-- Map journeys, inputs, outputs, states, recovery, boundaries, and acceptance scenarios. -->

## Project evidence package

Project ID / owning package: PROJECT_ID_AND_PACKAGE_OR_NOT_APPLICABLE_WITH_REASON

Project membership and immutable package revision/digest: PROJECT_PACKAGE_REF

<!-- Use assets/project-evidence-package/README.md for application-level
storyboard/concept, screen/state inventory, design approval and versioned actual
captures. Link existing Product Profile and release proof sets rather than
copying authorities. Include historical adoption gaps and explicit visibility.
This draft policy extension is not enforced by the pinned Core mfd/2 validator. -->

## UI proof

<!-- For a frontend product, link one versioned living-artifact page (normally
under docs/mfd/ or docs/design/) instead of a bare screenshot or mutable URL.
The packet or approval brief pins that page by immutable permalink/revision.
The page names the selected design authority and any shared stylebook/design-
system decision; covered routes, roles, viewports, themes, and important
states; candidate and approved proof references; the interaction,
accessibility, and reconstruction expectations; and explicit gaps or
exclusions. A screenshot is supporting evidence, never the authority by
itself. In reconstruction mode, candidate proofs may be linked during
drafting, but approval must name their immutable revisions. Use Not applicable
with a reason when the scoped work has no graphical/frontend UI. -->

Declaration: DECLARATION_VALUE

Reason: REASON_NAMING_SCOPE_EVIDENCE_OR_PLAN

Owner: OWNER

Authority references: AUTHORITY_REFERENCES_OR_OMIT

<!-- Declaration block: exactly one Declaration value per packet, one of three:
- not-applicable: no graphical/frontend UI. Reason is one sentence naming the
  scope evidence checked. Bare N/A, TBD, none, not needed, or backend is
  rejected. Owner is the accountable owner.
- existing-authority: approved immutable authority exists. Authority references
  lists each immutable reference with a bare 64-character lowercase SHA-256 (no
  sha256: prefix) and names the human decision that approved it. A branch name,
  latest, a moving URL, or a bare filename is never authority. Historical-only
  inputs never qualify.
- candidate-generation: candidates from generation, capture, or supply, with a
  plan named in Reason. Historical-only packets use this value with a plan.
  Nothing here is approved. Omit Authority references.
Routes are per row: generate, capture, or supply. Generation is one optional
route; capture and supply are equally valid. Candidates are never approved
automatically. Each surface needs its own decision reference before approval. -->

<!-- Governed UI-proof table: include ONLY for an applicable UI packet
(existing-authority or candidate-generation with governed UI surfaces). One row
per governed surface; a surface with neither a row nor a gap is invalid. Missing
required fields are structural errors; a missing viewport or state is an explicit
gap with owner and blocker; an absent artifact gets a gap and no invented hash.
Color follows the color/token rule: a semantic contract or approved design-
dictionary pointer, an owned gap, or a reasoned not-applicable. Gaps never imply
approval. Only authority rows may be approved, with the named human decision.
Filenames and URLs are not surface IDs; use stable namespaced identities.
Remote URIs are never fetched by deterministic proof-readiness validation. -->

Governed UI-proof table (applicable UI packets only; delete for no-UI packets):

| Surface ID | Route or entry | Primary operator | Disposition | Class | Route | Desktop | Mobile | Operational states | Artifact locator | SHA-256 | Provenance | Approval status and decision ref | Blocker and owner | Color/token contract |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SURFACE_ID_NAMESPACED | ROUTE_OR_ENTRY | PRIMARY_OPERATOR | retain, redesign, merge, split, relocate, or retire | authority, implementation, candidate, or historical | generate, capture, or supply | covered, not-applicable (reason), or gap (blocker and owner) | covered, not-applicable (reason), or gap (blocker and owner) | applicable subset of healthy, busy, degraded, stale, offline, empty, reconnecting, permission-limited: each covered, gap, or not-applicable (reason) | immutable path or URI, or stated absence | bare 64 lowercase hex, or none when the artifact is absent | capture, generation, or source date; method; tool or source revision | not-approved, candidate, or approved with decision ref naming this surface and SHA-256 | required for a gap or missing artifact: status (unassessed, missing, unavailable, planned, resolved; resolved needs evidence), blocker, owner | semantic contract, approved design-dictionary pointer, or owned gap where color carries meaning; reasoned not-applicable otherwise |

<!-- No-UI packets: use Declaration not-applicable with one Reason naming the
scope evidence checked and one Owner. Omit the governed table, UI rows, color
fields, and UI artifact references entirely. Technical and source inventory and
non-UI technical references remain allowed. -->

Boundary (verbatim): Candidate proofs are not approved. Visual approval requires human review against the cited proof. Screenshots and schema checks do not prove behavior, accessibility, authorization, persistence, live health, or visual fidelity.

<!-- Core warning: semantic rules for this block are Core-owned and are not enforced
by pinned Core 1.3.0. No product packet validator checks them; product tests check
text presence only. -->

## Public-app Product Profile

Applicability: REQUIRED_OR_NOT_APPLICABLE_WITH_REASON

Profile directory: PRE_PROFILE_DIRECTORY_PATH_OR_NOT_APPLICABLE

Profile page: PRE_PROFILE_DIRECTORY_PATH/README.md_OR_NOT_APPLICABLE

Immutable revision and digest: PRE_PROFILE_REVISION_AND_SHA256_OR_NOT_APPLICABLE

<!-- Public-facing applications must copy the bundled
`assets/public-app-product-profile/` directory and make its README the living-
artifact page. It leads with the north star, audience, measurable user outcome,
and feature story; then links proposed screen/layout proof, the semantic
stylesheet, and delivery-coverage checklist. Screenshots or wireframes are
candidate evidence with provenance and alt text; they support the profile but
do not replace its versioned narrative, accessibility, and delivery evidence.
Internal-only, API-only, CLI-only, library, or genuinely non-public work may
use Not applicable only with a concise reason. Record the profile revision and
digest here, not inside the profile, to avoid self-referential content. For a
Git-backed profile, compute the digest from the frozen revision over the whole
profile directory with:
`git archive --format=tar COMMIT -- PROFILE_DIRECTORY_PATH | sha256sum`. -->

## Technical contract

<!-- Define APIs/events, ownership, data and migration effects, auth rules, dependencies, observability, and operational expectations. -->

## Runner capability assessment

- Trust level: Pending
- Operating system and architecture: Pending
- Capabilities and resources: Pending
- Network and secret-access boundary: Pending
- Required runner labels: Pending
- Repository scope: Pending
- Selected runner or provisioning issue: Pending
- Availability evidence: Pending
- Offline or busy fallback: Pending
- Exact label-match validation: Pending

<!-- Use exactly one trust level: Public runner allowed, Isolated private runner required, or No CI runner permitted. Record deterministic local validation separately from runner-backed CI and live-host proof. Never route work to an unrelated repository runner as a fallback. -->

## Verification map

<!-- For every feature-shaped requirement, Validation names the PR-level tests
that run per dev PR and the live smoke test that runs at the milestone
promotion gate (dev to main), performed after build with a tool capable of
driving the real target (e.g. Chrome-extension browser automation for web
surfaces, a target device or emulator for device-targeted features). Passing CI
or unit tests alone do not satisfy the live row. A requirement with no live
surface records Not applicable with a reason instead of a silent skip. Gate
placement: [two-speed/v1](https://github.com/lancer1977/workstation-kit/blob/dev/standards/two-speed/v1/STANDARD.md), [ci-tier/v1](https://github.com/lancer1977/workstation-kit/blob/dev/standards/ci-tier/v1/STANDARD.md). -->

| Requirement | Scenario | Validation | Expected evidence |
| --- | --- | --- | --- |
| R1 | S1 | COMMAND_OR_CHECK | EVIDENCE_LOCATION |

## Verification Strategy

Verification strategy page: `docs/mfd/verification-strategy.md` or
`Not applicable — REASON`

| Requirement / feature | Unit | Integration / contract | End-to-end / consumer | Post-build live smoke | Not-applicable reason / replacement evidence | Not-applicable owner |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | COMMAND_OR_REASON | COMMAND_OR_REASON | COMMAND_OR_REASON | TOOL_AND_EVIDENCE_OR_REASON | REASON_OR_NOT_APPLICABLE | OWNER_OR_NOT_APPLICABLE |

<!-- Every feature-shaped requirement maps to every applicable layer. Libraries
require unit and consumer-contract/install proof unless a precise reason is
recorded. Websites and apps require an end-to-end happy path and post-build live
browser/device/app smoke. Passing CI, a unit test, HTTP 200, or a screenshot
alone never proves a runnable feature. The reason names the affected layer and
the owner is accountable for every non-applicable claim in its row. “100%” means complete declared
requirement and applicable happy-path coverage, not a line-coverage target. -->

## Demo Contract companion

Milestone dispositions / owner selection: CONTRACT_LINK_OR_DISPOSITIONS_WITH_REASON_AND_OWNER

Use the [Demo Contract guide](https://github.com/lancer1977/mapped-frontier-development/blob/v1.6.0/plugins/mapped-frontier-development/skills/mapped-frontier-development/references/demo-contract.md) and
[template](https://github.com/lancer1977/mapped-frontier-development/blob/v1.6.0/plugins/mapped-frontier-development/skills/mapped-frontier-development/assets/mfd-demo-contract.md) for a repeatable milestone journey. Declare
automated / recorded / evidence-only / not-applicable per milestone, with reason
and owner; select adoption explicitly after the pilot. Link the existing
Verification Strategy and project screen/state IDs. A demo never replaces full
layered gates or remaining acceptance. Presentation is optional, independently
verified and separately authorized; this companion is not Core enforcement.

## Autonomy and verification matrix

<!-- Define the human checkpoint and autonomous boundary for every requirement. Human approval is required for product intent, user-visible scope changes, trust/security/data/cost boundaries, destructive actions, and release. Agent authority covers implementation and evidence gathering within the approved boundary. -->

| Requirement | Human decision | Agent authority | Automated proof | UI / live proof | Release authority | Rollback |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | HUMAN_DECISION | AGENT_AUTHORITY | COMMAND_OR_CHECK | UI_OR_LIVE_PROOF | RELEASE_AUTHORITY | ROLLBACK_PLAN |

## Sub-plan reviews

<!-- Use exactly one shape. Ordinary bounded work uses Not required with a
concise rationale. Consequential work uses Required and one complete evidence
row per independently reviewed sub-package. Reports must be sanitized immutable
commit permalinks. Only Passed or explicitly disclosed Degraded evidence may
enter an approvable packet. -->

Status: Not required

Rationale: SUB_PLAN_REVIEW_RATIONALE

| Sub-package | Requirements | Packet ID | Packet digest | Immutable report | Gate result | Valid analysts | Synthesis | Rejected alternatives | Unresolved decisions | Staleness | Reconciliation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Per-project merge policy

<!-- Mirror `.mfd/project.yaml` `merge_policy` for this repository. Keep this
section and that file in sync; do not let them drift. -->

- Required checks: REQUIRED_CHECKS_FROM_PROJECT_YAML
- Integration branch: INTEGRATION_BRANCH
- Protected branch: PROTECTED_BRANCH

| Test tier | Command | Required | CI job name |
| --- | --- | --- | --- |
| Unit | COMMAND | Yes/No | CI_JOB_NAME |
| Integration | COMMAND | Yes/No | CI_JOB_NAME |
| Automation | COMMAND | Yes/No | CI_JOB_NAME |

- [ ] Auto-deploy to dev: dev site deploys from CI/CD on push/merge to dev
  with no manual workflow_dispatch or approval; main/prod deploy needs an
  explicit decision from Christopher (or N/A: no dev site)

### Codex review

<!-- No Codex review is requested on PRs into the integration branch (dev);
those merge on the merge bar alone. Every PR from dev to main gets an
"@codex review" comment, and its P0/P1 findings block promotion. This is a
floor: the Merge policy override subsection below may only ADD Codex review
restrictions; it cannot disable or weaken it. -->

### Merge policy override (optional)

<!-- Optional. If this subsection is absent, the MFD contract's merge policy
applies unmodified: agents may merge an ordinary PR into `dev` without asking
only in a repo with a v2 profile, with tests covering the change, the `unit`
tier and every required check green on the current head, and no sensitive
class touched. Merges to `main` always need the owner's confirmation. Code for
auth/authz, security and CI infrastructure is not a sensitive class: it merges
to `dev` on the same bar unless the packet's Live-settings change field is YES,
which requires the operator gate in the Approval section. Secrets, production
infrastructure, deployment and release always need the gate. An override may
only ADD restrictions; it can never remove the always-approval categories below
or the `unit` tier, and the integration branch can never be
`main`, `master`, or a release/production branch. The required `@codex review`
on every PR from the integration branch (dev) to main cannot be switched off or
weakened, and its P0/P1 findings always block promotion. -->

- Override integration branch: INTEGRATION_BRANCH
- Override required checks: REQUIRED_CHECKS
- Override test tiers: unit=REQUIRED_YES_OR_NO, integration=REQUIRED_YES_OR_NO, automation=REQUIRED_YES_OR_NO
- Auto-merge allowed: YES_OR_NO
- Extra approval paths: EXTRA_APPROVAL_PATH_GLOBS_OR_NONE
- Additional Codex review restrictions (add-only; e.g. also review PRs into the integration branch, extra reviewers, more blocking severities; cannot disable or weaken the dev-to-main `@codex review` or P0/P1 blocking): ADDITIONAL_CODEX_RESTRICTIONS_OR_NONE
- Always-approval categories (fixed, cannot be removed by an override): Secrets, Production infrastructure, Deployment, Release. Conditional, gated only when Live-settings change (auth/security/CI) is YES: Auth, Security, CI infrastructure

### Drift and replan

<!-- Own-library version bumps (PG.Core.Maui and other lancer1977 /
Polyhydra-Games packages) are added to this packet and tracked on an
auto-opened issue by bots, without asking first — worked carefully, to the
full merge bar (tests green, required checks pass, validation recorded, no
unresolved review threads or P0/P1 findings). Scope changes, new milestones,
and third-party major-version upgrades are NOT auto-handled; route those to
Christopher as a decision before implementation. -->

- Own-library auto-bump scope: OWN_LIBRARY_PACKAGES_OR_NONE (e.g.
  PG.Core.Maui)
- Auto-opened tracking issue: ISSUE_URL_OR_PENDING
- Last reconciled version: LAST_RECONCILED_VERSION_OR_NONE

#### TBD: version-update monitor hook

<!-- Placeholder only. Event source for "a tracked own-library shipped a new
version" is not yet defined — Agent Tools Bot is drafting that packet. Do
not treat any value below as live until that source lands; replace this
whole block in place when it does. -->

- Event source: TBD (Agent Tools Bot drafting)
- Event payload / fields: TBD
- Trigger condition: TBD

## Delivery map

| Order | GitHub issue / card | Requirement / scenario | Dependencies | Validation |
| --- | --- | --- | --- | --- |
| 1 | ISSUE_URL | R1 / S1 | None | COMMAND_OR_CHECK |

### Rollout and rollback

<!-- Describe rollout, migration, rollback, and operational ownership. -->

### Risks and unresolved decisions

| Item | Owner | Resolution or escalation condition |
| --- | --- | --- |
| RISK_OR_DECISION | OWNER | RESOLUTION |

## Acceptance criteria

Testable checklist. Each criterion names the test or check that proves it, written
before implementation. A PR merging under the project's `merge_policy` carries
tests covering these criteria.

Tests: Pending. Name the tests added or changed with this work, or state why
none apply, and for UI controls the component-level tests. See [testing@v1](https://github.com/lancer1977/workstation-kit/blob/dev/standards/testing/v1/STANDARD.md) (T5 and T6).

- [ ] Criterion: Pending. Proof: Pending

## Blockers

| Blocker | Owner | Unblock condition |
| --- | --- | --- |
| None | None | None |

## Future requirements

Needs that are known but not part of this packet: secrets (name the Infisical path
and owner only, never inline values), infrastructure, and hardware.

| Requirement | Kind | Owner | Needed by |
| --- | --- | --- | --- |
| None | None | None | None |

## Open decisions

| Decision | Options | Recommendation | Owner |
| --- | --- | --- | --- |
| None | None | None | None |

## Approval

- Live-settings change (auth/security/CI): YES_OR_NO
- Always-approval category touched (secrets/production infrastructure/deployment/release): YES_OR_NO
<!-- Live-settings: YES only when the change alters live auth, security or CI
settings (not code for them). Always-approval: YES when the change touches
secrets, production infrastructure, deployment or release. Code-only
auth/security/CI work (both NO, and no deployment) merges to `dev` on the merge
bar with no operator gate, and its Decision below may stay Pending; either YES,
or Deployment applicability "Applies", requires the Decision below to be
recorded as an approval (Approved...). -->
- Product owner: OWNER
- Decision: Pending
- Date: Pending
- Approved commit or immutable revision: Pending
- Approval evidence: Pending
- Approval brief: Pending

Approval plus a satisfied `.mfd/project.yaml` v2 `merge_policy` authorizes
agents to merge ordinary changes to the `dev` integration branch after Tier 1
checks pass ([two-speed/v1](https://github.com/lancer1977/workstation-kit/blob/dev/standards/two-speed/v1/STANDARD.md), [ci-tier/v1](https://github.com/lancer1977/workstation-kit/blob/dev/standards/ci-tier/v1/STANDARD.md)). Changes touching secrets, authentication or authorization,
security, production infrastructure, deployment, or release promotion require
the owner's explicit OK (see the [security-remediation pattern](https://github.com/lancer1977/workstation-kit/blob/dev/docs/security-remediation-pattern.md) for security work). Every merge to protected `main` requires the owner's explicit OK and a green `dev` smoke test. Approval to
merge into `main` names the repository, the target, and the exact head SHA, and
is void if the head changes; it must then be re-given. Worker-to-milestone
acceptance and milestone-to-integration promotion are separate merge targets,
each needing its own recorded authority naming the repository and target,
current base and head evidence, exact-SHA validation, and resolved blocking
findings. "Done" means merged green into `dev`; "shipped" means promoted to
`main` after the milestone retrospective and QA. Approval does not authorize
deployment, issue closure, secret access or rotation, external communication,
or a production-success claim.

The project profile is `.mfd/project.yaml` with `schema_version: 2` and
`merge_policy: {integration_branch: dev, protected_branch: main,
required_checks: [real CI check names], test_tiers: {unit|integration|automation|smoke:
{command, required_for: [dev|main]}}, require_pr_tests: bool, test_paths: [globs], escalate_paths: [globs],
escalate_labels: [labels]}`. `test_tiers` entries specify a command and one or
both branches where it is required. Missing or unsatisfied profile policy blocks
agent merge to `dev`. A PR qualifies only if (1) it adds or updates tests covering the behavior it changes, or states why none apply (pure docs or pure config), and (2) the PR gate runs the profile's general `unit` tier with every required check green on the current head.

## Deviations

| Date | Requirement / boundary | Decision | Approver | Follow-up |
| --- | --- | --- | --- | --- |
| None | None | None | None | None |

## Release controls and closeout evidence

- Target branch: `dev` (the integration branch). Use `main` only for an explicit, separately approved promotion.
- Pull request: Pending
- Required reviewers: Pending
- CI and validation evidence: Pending
- Deployment authority: Separately required when applicable
- Live verification: Required for every feature-shaped requirement — a
  post-build smoke test run with a live-capable tool (browser automation,
  target device/emulator, or equivalent). Pending, or Not applicable with a
  reason for requirements with no live surface.
- Rollback evidence: Pending or not applicable with reason
- Deferred follow-ups: None yet

### Deployment contract

- Deployment applicability: APPLIES_OR_NOT_APPLICABLE_WITH_REASON
- Target environments: TARGET_ENVIRONMENTS
- Deployment authority (separate from approval): DEPLOYMENT_AUTHORITY
- Source commit: SOURCE_COMMIT
- Immutable artifact / digest: IMMUTABLE_ARTIFACT_OR_DIGEST
- Rollout record: ROLLOUT_RECORD
- Authenticated smoke proof: AUTHENTICATED_SMOKE_PROOF
- Rollback target: ROLLBACK_TARGET

### Release closeout record

- Live verification result: LIVE_VERIFICATION_RESULT
- Deferred drift / follow-up issue: DEFERRED_DRIFT_OR_FOLLOW_UP_ISSUE
