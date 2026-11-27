#!/usr/bin/env python3
"""MFD issue lifecycle: pending-main -> released, and the milestone close rule (#1911).

Lifecycle (see core/mfd-contract.md, "Issue lifecycle"):
  1. PRs into dev link their issue with `Refs #N` (or `Closes #N`).
  2. After QA passes in dev, the issue is closed as completed and gets `pending-main`.
  3. The dev-to-main promotion PR lists every `pending-main` issue it carries. Once it
     merges to main, each of those issues swaps `pending-main` for `released`.
     A failed main re-test reopens the issue and adds `main-regression` (manual today).
  4. A milestone closes only when all of its issues are closed and none still carry
     `pending-main`.

Subcommands (every mutating one is a dry run unless --apply; one line per action):
  ensure-labels     create pending-main, released, main-regression if missing
  check-labels      exit 1 if any lifecycle label is missing from the repo
  audit             exit 1 if any issue's state contradicts its lifecycle labels
  dev-qa-pass       close one OPEN issue as completed and add pending-main (step 2)
  pending           print `Refs #N` for every closed pending-main issue (promotion body)
  release           swap pending-main -> released for issues the promotion carried,
                    then close milestones that now satisfy the rule (step 3 + 4)
  check-milestone   exit 1 if a milestone may not close yet; prints the blockers
  close-milestones  close the given milestones that satisfy the rule

Every gh/git call goes through one runner function (default: subprocess), so the
tests run offline. Repo comes from GH_REPO or --repo. Standard library only, so this
file can be installed into a project as `.mfd/tools/issue_lifecycle.py`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Callable, Iterable

PENDING = "pending-main"
RELEASED = "released"
REGRESSION = "main-regression"

LABELS = [
    (PENDING, "FBCA04", "Closed after dev QA; waiting for the promotion to main"),
    (RELEASED, "0E8A16", "Promoted to main"),
    (REGRESSION, "B60205", "Reopened: failed the re-test on main"),
]
LIFECYCLE_LABELS = frozenset(name for name, _c, _d in LABELS)

MAX_ISSUE = 10**9
_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[^\n]*\n.*?^[ \t]{0,3}\1[ \t]*$", re.S | re.M)
_INLINE = re.compile(r"`[^`\n]*`")
# Same-repo links only: `Refs #N`, `Ref #N`, `Closes #N`, `Fixes #N`, `Resolves #N`.
_LINK = re.compile(
    r"(?<![\w/#.-])(?:refs?|close[sd]?|fix(?:es|ed)?|resolve[sd]?):?[ \t]+#(\d+)(?!\w)",
    re.I,
)
# Squash/merge commit subjects end with `(#PR)`; merge commits say `Merge pull request #PR`.
_SQUASH_PR = re.compile(r"\(#(\d+)\)[ \t]*$", re.M)
_MERGE_PR = re.compile(r"^Merge pull request #(\d+) ", re.M)
_ZERO_SHA = re.compile(r"^0+$")

Runner = Callable[[list[str]], subprocess.CompletedProcess]


class LifecycleError(RuntimeError):
    pass


# --- pure rules (no I/O) -------------------------------------------------------------


def _strip_code(text: str) -> str:
    return _INLINE.sub(" ", _FENCE.sub(" ", text))


def _bounded(numbers: Iterable[int]) -> list[int]:
    return sorted({n for n in numbers if 0 < n < MAX_ISSUE})


def linked_issues(text: str | None) -> list[int]:
    """Issue numbers linked with Refs/Closes/Fixes/Resolves #N (same repo, code ignored)."""
    if not text:
        return []
    return _bounded(int(m.group(1)) for m in _LINK.finditer(_strip_code(text)))


def commit_pr_numbers(text: str | None) -> list[int]:
    """PR numbers from squash `(#N)` subjects and `Merge pull request #N` commits."""
    if not text:
        return []
    found = [int(m.group(1)) for m in _SQUASH_PR.finditer(text)]
    found += [int(m.group(1)) for m in _MERGE_PR.finditer(text)]
    return _bounded(found)


def missing_labels(existing: Iterable[str]) -> list[str]:
    have = set(existing)
    return [name for name, _c, _d in LABELS if name not in have]


def issue_violations(issue: dict) -> list[str]:
    """Contradictions between an issue's state and its lifecycle labels."""
    labels = set(issue.get("labels") or [])
    state = str(issue.get("state") or "").lower()
    n = issue.get("number")
    out = []
    if PENDING in labels and RELEASED in labels:
        out.append(f"#{n}: has both {PENDING} and {RELEASED}")
    if PENDING in labels and state != "closed":
        out.append(f"#{n}: {PENDING} on an {state or 'unknown'} issue (it must be closed)")
    if RELEASED in labels and state != "closed" and REGRESSION not in labels:
        out.append(f"#{n}: {RELEASED} on an open issue without {REGRESSION}")
    if REGRESSION in labels and state == "closed":
        out.append(f"#{n}: {REGRESSION} on a closed issue (a regression is reopened)")
    return out


def milestone_blockers(issues: Iterable[dict]) -> list[str]:
    """Why a milestone may not close. Empty means every issue is closed and none is pending-main.

    Pull requests in the milestone are ignored; only issues count.
    """
    blockers = []
    for issue in issues:
        if issue.get("pr"):
            continue
        n = issue.get("number")
        if str(issue.get("state") or "").lower() != "closed":
            blockers.append(f"#{n} is open")
        elif PENDING in set(issue.get("labels") or []):
            blockers.append(f"#{n} still carries {PENDING}")
    return blockers


def release_comment(sha: str, promotion_pr: int | None) -> str:
    via = f" via promotion PR #{promotion_pr}" if promotion_pr else ""
    return (
        f"Released to `main` at {sha or 'unknown'}{via}: swapped `{PENDING}` for `{RELEASED}`.\n\n"
        "The main re-test is manual. If it fails, reopen this issue and add "
        f"`{REGRESSION}`.\n"
        f"<!-- mfd-release:v1 sha={sha or 'unknown'} pr={promotion_pr or 0} -->"
    )


# --- GitHub/git access through the injectable runner ---------------------------------

_ISSUE_JQ = ("{number, state, labels: [.labels[].name], pr: (.pull_request != null), "
             "milestone: (.milestone.number // null)}")


def default_runner(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def _run(run: Runner, argv: list[str]) -> str:
    res = run(argv)
    if res.returncode != 0:
        raise LifecycleError(f"{' '.join(argv[:3])} failed: {(res.stderr or '').strip()}")
    return res.stdout or ""


def _ndjson(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def get_issue(run: Runner, repo: str, n: int) -> dict:
    return json.loads(_run(run, ["gh", "api", f"repos/{repo}/issues/{n}", "--jq", _ISSUE_JQ]))


def repo_labels(run: Runner, repo: str) -> list[str]:
    out = _run(run, ["gh", "api", "--paginate", f"repos/{repo}/labels?per_page=100",
                     "--jq", ".[].name"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def list_issues(run: Runner, repo: str, query: str) -> list[dict]:
    out = _run(run, ["gh", "api", "--paginate", f"repos/{repo}/issues?{query}&per_page=100",
                     "--jq", f".[] | {_ISSUE_JQ}"])
    return _ndjson(out)


def milestone_state(run: Runner, repo: str, m: int) -> str:
    return _run(run, ["gh", "api", f"repos/{repo}/milestones/{m}", "--jq", ".state"]).strip()


# --- subcommands ---------------------------------------------------------------------


def ensure_labels(run: Runner, repo: str, apply: bool) -> None:
    for name, color, desc in LABELS:
        if not apply:
            print(f"dry-run: gh label create {name} -R {repo} --color {color} "
                  f"--description '{desc}'")
            continue
        res = run(["gh", "label", "create", name, "-R", repo, "--color", color,
                   "--description", desc])
        if res.returncode == 0:
            print(f"created label {name}")
        elif "already exists" in (res.stderr or "").lower():
            print(f"label {name} already exists")
        else:
            raise LifecycleError(f"label {name}: {(res.stderr or '').strip()}")


def check_labels(run: Runner, repo: str) -> int:
    missing = missing_labels(repo_labels(run, repo))
    if missing:
        print(f"missing lifecycle labels: {', '.join(missing)} (run ensure-labels --apply)")
        return 1
    print("lifecycle labels present: " + ", ".join(name for name, _c, _d in LABELS))
    return 0


def audit(run: Runner, repo: str) -> int:
    seen: dict[int, dict] = {}
    for label in sorted(LIFECYCLE_LABELS):
        for issue in list_issues(run, repo, f"state=all&labels={label}"):
            if not issue.get("pr"):
                seen[issue["number"]] = issue
    problems = [v for n in sorted(seen) for v in issue_violations(seen[n])]
    for line in problems:
        print(f"violation {line}")
    print(f"audit: {len(seen)} lifecycle issues, {len(problems)} violations")
    return 1 if problems else 0


def dev_qa_pass(run: Runner, repo: str, n: int, evidence: str, apply: bool) -> bool:
    issue = get_issue(run, repo, n)
    if issue.get("pr"):
        raise LifecycleError(f"#{n} is a pull request, not an issue")
    if str(issue.get("state")).lower() != "open":
        print(f"skip #{n}: state {issue.get('state')}")
        return False
    body = (f"Dev QA passed{': ' + evidence if evidence else ''}. Closing as completed with "
            f"`{PENDING}`; it swaps to `{RELEASED}` when the promotion to main merges.")
    if not apply:
        print(f"dry-run: close #{n} as completed, add {PENDING}")
        return True
    edit = ["gh", "issue", "edit", str(n), "-R", repo, "--add-label", PENDING]
    # A repaired regression comes back carrying `released` and `main-regression`;
    # clear them so the issue is not left in a state `audit` reports as a violation.
    stale = [name for name in (RELEASED, REGRESSION) if name in (issue.get("labels") or [])]
    if stale:
        edit += ["--remove-label", ",".join(stale)]
    _run(run, edit)
    _run(run, ["gh", "issue", "close", str(n), "-R", repo, "--reason", "completed",
               "--comment", body])
    print(f"closed #{n} with {PENDING}")
    return True


def pending(run: Runner, repo: str) -> list[int]:
    numbers = sorted(i["number"] for i in list_issues(run, repo, f"state=closed&labels={PENDING}")
                     if not i.get("pr"))
    for n in numbers:
        print(f"Refs #{n}")
    return numbers


def _pr_text(run: Runner, repo: str, pr: int) -> tuple[str, str]:
    """(body, concatenated commit messages) of a pull request."""
    meta = json.loads(_run(run, ["gh", "api", f"repos/{repo}/pulls/{pr}",
                                 "--jq", "{body: (.body // \"\")}"]))
    commits = _run(run, ["gh", "api", "--paginate", f"repos/{repo}/pulls/{pr}/commits",
                         "--jq", ".[].commit.message"])
    return meta.get("body") or "", commits


def candidate_issues(run: Runner, repo: str, promotion_pr: int | None,
                     before: str, after: str) -> list[int]:
    """Numbers linked by the promotion PR body and by the PRs it (or the push) promoted."""
    numbers: set[int] = set()
    texts: list[str] = []
    if promotion_pr:
        body, commits = _pr_text(run, repo, promotion_pr)
        numbers.update(linked_issues(body))
        texts.append(commits)
    if before and after and not _ZERO_SHA.match(before):
        texts.append(_run(run, ["git", "log", "--format=%B", f"{before}..{after}"]))
    promoted_prs: set[int] = set()
    for text in texts:
        numbers.update(linked_issues(text))
        promoted_prs.update(commit_pr_numbers(text))
    promoted_prs.discard(promotion_pr or 0)
    for pr in sorted(promoted_prs):
        try:
            body, _commits = _pr_text(run, repo, pr)
        except LifecycleError as exc:
            print(f"warning: could not read PR #{pr}: {exc}")
            continue
        numbers.update(linked_issues(body))
    numbers -= promoted_prs
    numbers.discard(promotion_pr or 0)
    return sorted(numbers)


def close_milestones(run: Runner, repo: str, milestones: Iterable[int], apply: bool) -> list[int]:
    closed = []
    for m in sorted(set(milestones)):
        if milestone_state(run, repo, m) != "open":
            print(f"milestone {m}: already closed")
            continue
        blockers = milestone_blockers(list_issues(run, repo, f"milestone={m}&state=all"))
        if blockers:
            print(f"milestone {m}: stays open ({'; '.join(blockers)})")
            continue
        if not apply:
            print(f"dry-run: close milestone {m}")
        else:
            _run(run, ["gh", "api", "-X", "PATCH", f"repos/{repo}/milestones/{m}",
                       "-f", "state=closed"])
            print(f"closed milestone {m}")
        closed.append(m)
    return closed


def check_milestone(run: Runner, repo: str, m: int) -> int:
    blockers = milestone_blockers(list_issues(run, repo, f"milestone={m}&state=all"))
    for b in blockers:
        print(f"milestone {m}: {b}")
    print(f"milestone {m}: {'may close' if not blockers else 'may not close'}")
    return 1 if blockers else 0


def release(run: Runner, repo: str, promotion_pr: int | None, before: str, after: str,
            sha: str, apply: bool) -> list[int]:
    released = []
    milestones: set[int] = set()
    for n in candidate_issues(run, repo, promotion_pr, before, after):
        try:
            issue = get_issue(run, repo, n)
        except LifecycleError as exc:
            print(f"skip #{n}: {exc}")
            continue
        labels = set(issue.get("labels") or [])
        if issue.get("pr") or PENDING not in labels:
            continue
        if str(issue.get("state")).lower() != "closed":
            print(f"skip #{n}: {PENDING} on an open issue; fix it by hand")
            continue
        if not apply:
            print(f"dry-run: #{n} {PENDING} -> {RELEASED}")
        else:
            _run(run, ["gh", "issue", "edit", str(n), "-R", repo, "--add-label", RELEASED,
                       "--remove-label", PENDING])
            _run(run, ["gh", "issue", "comment", str(n), "-R", repo,
                       "--body", release_comment(sha, promotion_pr)])
            print(f"released #{n}: {PENDING} -> {RELEASED}")
        released.append(n)
        if issue.get("milestone"):
            milestones.add(int(issue["milestone"]))
    print(f"release: {len(released)} issues {'released' if apply else 'would release'}")
    # A dry run cannot see its own label swaps, so milestones are only evaluated on --apply
    # from live state; the dry run lists which milestones it would re-check.
    if not apply:
        for m in sorted(milestones):
            print(f"dry-run: re-check milestone {m} after the swap")
    else:
        close_milestones(run, repo, milestones, apply)
    return released


def main(argv: list[str] | None = None, run: Runner | None = None) -> int:
    run = run or default_runner
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GH_REPO"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ensure-labels")
    p.add_argument("--apply", action="store_true")
    sub.add_parser("check-labels")
    sub.add_parser("audit")
    p = sub.add_parser("dev-qa-pass")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--evidence", default="")
    p.add_argument("--apply", action="store_true")
    sub.add_parser("pending")
    p = sub.add_parser("release")
    p.add_argument("--promotion-pr", type=int, default=0)
    p.add_argument("--before", default="")
    p.add_argument("--after", default="")
    p.add_argument("--sha", default="")
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("check-milestone")
    p.add_argument("--milestone", type=int, required=True)
    p = sub.add_parser("close-milestones")
    p.add_argument("--milestone", type=int, action="append", required=True)
    p.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if not args.repo:
        parser.error("set GH_REPO or pass --repo")
    try:
        if args.cmd == "ensure-labels":
            ensure_labels(run, args.repo, args.apply)
        elif args.cmd == "check-labels":
            return check_labels(run, args.repo)
        elif args.cmd == "audit":
            return audit(run, args.repo)
        elif args.cmd == "dev-qa-pass":
            dev_qa_pass(run, args.repo, args.issue, args.evidence, args.apply)
        elif args.cmd == "pending":
            pending(run, args.repo)
        elif args.cmd == "release":
            if not args.promotion_pr and not (args.before and args.after):
                parser.error("release needs --promotion-pr or --before/--after")
            release(run, args.repo, args.promotion_pr or None, args.before, args.after,
                    args.sha or args.after, args.apply)
        elif args.cmd == "check-milestone":
            return check_milestone(run, args.repo, args.milestone)
        else:
            close_milestones(run, args.repo, args.milestone, args.apply)
    except LifecycleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
