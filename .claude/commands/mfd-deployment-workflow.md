Read `.mfd/deployment.yaml` and validate it with
`.mfd/tools/validate_deployment_profile.py` before proposing deployment work.

First name the target environment and its `approval_required` setting, the
deployment owner, the source path, the immutable artifact or revision, the
rollback reference, and the smoke checks. Confirm separate explicit authority
for the named environment before performing any deployment, rollback, GitOps,
or runtime action. Approval of an MFD packet, a merged PR, or a chat request
does not provide deployment authority.

Keep merged, deployed, and live-verified as separate evidence states. If the
GitOps or runtime state drifts from `.mfd/deployment.yaml`, report the evidence
in an owning GitHub issue instead of silently redeploying. Production actions
must remain explicit, reviewable, and attributable to the deployment owner.
