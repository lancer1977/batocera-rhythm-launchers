# Mapped-Frontier Development (MFD)

MFD, also called STDD, makes the approved product boundary explicit before
material implementation and reconciles delivery against that boundary.

## Authority and small changes

1. Identify or create the owning GitHub issue before planning material work.
2. Record the small-change rationale on the issue when MFD is not needed.
3. GitHub remains the authority for issues, pull requests, review, CI, merge,
   releases, and delivery state.

## Phase 0: map and approve

Build a packet covering intent and non-goals, testable acceptance criteria,
current behavior, primary and failure-state journeys, UI proof where
applicable, technical/security/data/operational boundaries, requirement-to-
validation traceability, the repository's per-project merge policy (required
checks and unit/integration/automation test tiers, mirroring
`.mfd/project.yaml`), delivery and rollback, blockers with an owner and
unblock condition, future requirements (secrets sourced via Security Bot /
Infisical — never an inline secret value — plus infrastructure and
hardware), and open decisions with options and a recommendation.

Submit one concise approval brief on the owning issue. It must name an
immutable packet revision. The product owner records exactly one decision:
`Approve`, `Request changes`, or `Reject`.

Approval authorizes scoped implementation only. It does **not** authorize
merge, deployment, issue closure, secret access, external communication, or a
production-success claim.

## Execute

Stay inside the approved observable behavior and risk boundaries. Return a
focused deviation brief if discovery changes user-visible behavior, API/auth/
security, data, deployment, rollback, availability, cost, or accessibility.

Use normal exact-head review, CI, release authority, and live-verification
controls. Local passing tests are evidence, not delivery completion.

### Merge policy

Approval of a packet still does not authorize merge or deployment by itself
(see above). The only standing exception is the owner's MFD `dev` merge
pre-authorization (mapped-frontier-development#49): in a repository with a
valid `.mfd/project.yaml` v2 `merge_policy` and an approved Phase 0 packet, an
agent may merge an ordinary PR into the declared integration branch (`dev`)
without a per-merge confirmation only when all of these hold:

1. the PR adds or updates tests covering the behavior it changes, or states
   why none apply (pure docs or config);
2. the PR gate runs the profile's `unit` tier and every required check is
   green on the current PR head; and
3. the change does not touch secrets or live production infrastructure,
   deployment, or release promotion. Code for auth/authz, security and CI
   infrastructure merges to `dev` on the same bar (owner decision
   2026-11-23, workstation-kit#2829).

Everything else still needs the owner's explicit confirmation: any merge to
`main` or another default/release branch (which also needs a green `dev`
smoke test), changes to secrets or live production infrastructure,
deployment or release promotion, repositories without a v2 profile,
and milestone branches. After merging, verify the post-merge run and fix or
revert red before any other merge.

This contract grants no deployment authority. Existing dev-environment
deployment grants remain bounded, recorded per project, and separately
verified; no override can create or widen one.

### Codex review

PRs into the integration branch (dev) merge on the merge bar alone — no
Codex review is requested. Every PR from dev to main gets an "@codex review"
comment, and its P0/P1 findings block promotion to main. This is a floor: a
packet's **Merge policy override** subsection may only add Codex review
restrictions on top of it (for example, also request Codex review on PRs into
the integration branch, require extra reviewers, or treat additional finding
severities as blocking). It can never disable or weaken the `@codex review` on
PRs from dev to main, and P0/P1 findings from that review always block
promotion.

A packet's **Merge policy override** subsection is optional. When present it
may only add restrictions to the rule above: it may name an integration branch
other than `dev` (never `main`, `master`, or a release or production branch),
add required checks, require more test tiers (never drop `unit`), set
auto-merge to `no`, list extra path globs that need explicit approval,
require additional review, and add Codex review restrictions (add-only). It can never drop or weaken the always-approval
categories, the `unit` tier, or the Codex review on promotion to `main`. When
the subsection is absent, the rule above applies unmodified.

### Drift and replan

When a library Christopher owns (`PG.Core.Maui` and other
`lancer1977`/`Polyhydra-Games` packages) ships a new version, bots add the
version bump to the project's MFD packet and open the tracking issue
automatically — no approval ask. They work the bump carefully: keep the
merge bar in full (tests green, required checks pass, validation recorded,
no unresolved review threads or P0/P1 findings) before it lands.

Scope changes, new milestones, and third-party major-version upgrades are not
covered by this automatic path — those still go to Christopher as a decision
before implementation starts.

Version-update monitor events (the trigger that detects a new own-library
release and files the bump) are **TBD**: event source not yet wired up —
Agent Tools Bot is drafting that packet. See the `### TBD: version-update
monitor hook` block in `tools/mfd/templates/mfd-build-packet.md` for the
placeholder a packet should carry until that source is defined.

### Issue lifecycle

Issues move through dev and main with three labels: `pending-main`,
`released`, and `main-regression`.

1. PRs into the integration branch (`dev`) link their issue with `Refs #N`,
   not `Closes #N`. The PR gate's linked-issue check accepts either.
2. After QA passes in `dev`, the issue is closed as completed and gets
   `pending-main`.
3. The dev-to-main promotion PR lists every `pending-main` issue it carries
   (`Refs #N`). After it merges to `main` and `main` is re-tested, each of
   those issues swaps `pending-main` for `released`. A failed main re-test
   reopens the issue and adds `main-regression`.
4. A milestone closes only when all of its issues are closed and none still
   carry `pending-main`.

The re-test on `main` is manual for now: the swap fires on the main merge,
and a regression is reopened by hand or by a QA agent. Tooling, the opt-in
reusable workflow, and the rollout steps are in `tools/mfd/ISSUE-LIFECYCLE.md`
(workstation-kit) and `.mfd/tools/issue_lifecycle.py` once installed. Closing
an issue is still an action that needs its own authority; this lifecycle
says when, not who.

## Closeout

Reconcile the approved packet against the exact PRs, validations, live evidence
when relevant, approved deviations, rollback evidence, and deferred follow-up
issues before declaring the work complete.
