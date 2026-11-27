Read `.mfd/deployment.yaml` and validate it with
`.mfd/tools/validate_deployment_profile.py` before reconciling release status.

Report evidence separately for each state: merged (the exact commit is in the
target branch), deployed (the declared environment references the intended
immutable artifact or revision), and live-verified (the profile's applicable
smoke checks have current results). Do not infer deployed from merged, or
live-verified from deployed.

This command is read-only: do not deploy, roll back, change GitOps, access
secrets, or claim production success. Compare the declared GitOps/runtime state
with the profile's drift contract. When drift is found, record the evidence and
open or update an owning GitHub issue; do not silently redeploy.

Repository authority clarification: for a read-only request, report proposed
issue updates rather than writing them. Create/edit tracking only when the
user has separately authorized those writes.
