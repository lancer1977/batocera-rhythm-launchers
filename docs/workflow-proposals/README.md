# Workflow proposals

Files in this directory are source documents only. GitHub does not activate
them as Actions workflows; there are no active `.github/workflows` changes in
this proposal.

## Fixture validation proposal

`fixture-validation.yml` describes a future workflow for same-repository pull
requests targeting `main` and pushes to `main`. The checkout action is pinned
to `9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0`; the checked-out repository revision
is the exact triggering PR head or push SHA. It disables credential persistence,
grants only `contents: read`, and has a 15-minute timeout. The action revision
must never be used as this repository's source ref.

The job proposes these runner labels:

```text
self-hosted, Linux, X64, pr-validation, batocera-rhythm-launchers-validation
```

These labels are proposed, not verified as registered or capable. Activation
is blocked until the exact labels and runner capabilities are verified, the
runner environment is reviewed, and separate operational approval is given.
This document does not register a runner or authorize activation.

Fork pull requests explicitly skip the job. There is no paid GitHub-hosted
fallback; an untrusted-code lane needs a separate reviewed proposal.

The commands include the five original shell suites and the explicit validator
integration wrapper. The proposal checks out public `lancer1977/stepmania-song-validator`
at immutable `d0353debe1610527f922714c79fde28834d44014` into `.validator-source`
(with credential persistence disabled), and supplies its `src` as
`RHYTHM_VALIDATOR_SOURCE`. No package installation or provider fallback is needed.

```sh
bash tests/install-config-preservation.sh
bash tests/test-fd-ancestry.sh
bash tests/test-versioned-extract.sh
bash tests/test-pack-preview.sh
bash tests/test-pack-transaction.sh
bash tests/test-validator-integration.sh
```

The integration wrapper refuses an absent provider and runs the reporting and
real-validator transaction Python suites. It is also found by the workspace's
`tests/*.sh` selector, so local workspace validation must explicitly export
`RHYTHM_VALIDATOR_SOURCE` to the trusted validator `src` checkout. An absent
provider is unavailable evidence, never a passing synthetic fallback.

They use synthetic temporary fixtures. They are not NAS, device, installed
library, or production validation. The template directs temporary files to a
task-private directory under the runner's `runner.temp`, created before tests
run; it does not rely on `/tmp`.

Before any activation, review exact triggering-head checkout, runner labels and
capabilities, environment isolation, fork behavior, and current test contents.
Copying this proposal into `.github/workflows` is a separate operational action
and is not authorized by this source-only change.
