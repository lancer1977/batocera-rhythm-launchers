# MFD workflow

When a request involves a material product, architecture, security, deployment,
data, API, or operational change, read `.mfd/core/mfd-contract.md` before
planning or implementation. Use `.mfd/templates/` for Phase 0 packets and
approval briefs.
For deployment-aware work, read and maintain `.mfd/deployment.yaml`; validate
it with `.mfd/tools/validate_deployment_profile.py` before relying on its
ownership, approval, smoke-check, rollback, or drift contracts.

Do not treat a chat summary or moving branch as approval. Require an owning
issue and an immutable packet revision. Do not merge, deploy, close issues,
access secrets, or claim production success without separate explicit authority
and evidence.
