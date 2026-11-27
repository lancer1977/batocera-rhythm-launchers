# Project design scope and milestone evidence

This guide expands the behavior-map, UI-proof and delivery-map prompts in the
[MFD contract](mfd-contract.md). It does not replace that contract or grant
additional authority. Design work is part of Phase 0, not an untracked task
left for implementation.

## Select the project profile

Choose website, mobile app, game, or a combination in the build packet. For
every checklist row record **Applies** with evidence, or **Not applicable**
with a project-specific reason. A profile is a starting point, not a mandate
to invent screens. A non-UI change can mark UI proof not applicable with a
reason while retaining behavior, technical and verification maps.

| Profile | Applicable-scope checklist |
| --- | --- |
| Website | Routes/site navigation and direct links; desktop/mobile breakpoints; header/footer where used; page hierarchy and real copy; forms, validation and feedback; keyboard/focus and accessibility; loading, empty, error and recovery states. |
| Mobile app | Screen stack/tabs and deep links; platform back/dismiss; supported devices, safe areas, orientation and text scaling; keyboard/touch interactions; permission flows; offline/reconnect and background/resume; app icon and launch/splash only where used. |
| Game | Core gameplay loop and scene/menu map; onboarding/tutorial; HUD and controls for supported input devices; pause/resume, settings, save/load; win/loss/retry and loading transitions; target resolutions/aspect ratios and safe areas; art, icon, animation and audio inventory; title/splash only where used. |

For mixed projects, cover each relevant surface and shared handoffs. Mark
inapplicable items individually rather than treating an entire profile as
done. Establish the supported-device/input matrix and accessibility
requirements before selecting representative proof screens.

## Map the experience before polishing it

- **Navigation map:** identify routes/screens/scenes, entry points, destinations,
  back/cancel/exit behavior, protected paths and unavailable destinations.
- **Journey storyboard:** follow a realistic user from intent to outcome,
  showing actions, system responses, decisions and recovery. Include primary,
  interrupted/repeated and failure paths, not just a gallery of happy screens.
- **Wireframes:** show hierarchy, navigation, controls, real representative
  copy/data and content density. Include long text, empty/loading/error/
  success states, validation and disabled actions where applicable.
- **Device constraints:** annotate viewport, safe area, orientation, input
  method, keyboard/controller focus, scrolling and responsive changes. Do not
  use a desktop screenshot as proof of a mobile flow.
- **High-fidelity proof:** resolve the important visual decisions for the
  representative journeys, screens and states using the proposed styles and
  assets. Use a prototype or rendered screen evidence where interaction or
  motion matters. Identify what remains schematic; do not label a wireframe
  as final visual proof.

Use realistic but synthetic or cleared content, never private customer data
or credentials. Every artifact should identify the requirements/scenarios it
proves. Reuse an approved existing design system where suitable; document
only the changes and evidence needed for this scope.

## Establish the approved design baseline

The packet must make the following reviewable, with not-applicable reasons
where appropriate:

- Design direction and references, including the selected direction and any
  intentionally rejected alternatives needed to prevent ambiguity.
- Token names and values for semantic colors, typography (family, size,
  weight and line height), spacing, sizing, radii and elevation as applicable;
  theme, contrast, responsive and reduced-motion rules where needed.
- Component inventory and behavior: buttons, links, inputs, menus and other
  applicable controls. Show default, hover, focus, pressed/selected, disabled,
  loading, error and success states where those states exist. Touch-only
  surfaces need not invent hover behavior.
- Icons and asset inventory: source/revision, owner or license, intended use,
  formats, dimensions/density, variants, accessibility labels and readiness.
  Mark temporary assets and the milestone that replaces them.
- Splash/launch/title screens, headers and footers only for surfaces that use
  them. Record exclusions explicitly rather than adding generic decoration.

Link the navigation map, storyboards, wireframes, high-fidelity proofs,
tokens/components and asset inventory from the build packet. Use immutable
revisions or versioned exports for approval; a mutable design-tool URL alone
does not establish the approved baseline. Record access location and artifact
version so another implementer can retrieve the same evidence. Product-owner
approval remains the contract's single decision on an immutable packet.

## Plan outcome-based milestones

Keep the delivery map's issue/requirement/dependency/validation links. Add
milestone records that define:

1. **Observable outcome:** what the user can now do, rather than a list of
   activities such as "work on UI."
2. **Prerequisites:** approved packet/design revision, dependencies, assets,
   test data and authorized environment access. Assign owners for blockers.
3. **Demo:** exact journey, states and supported device/input combinations
   that will demonstrate the outcome.
4. **Acceptance:** measurable criteria, automated tests and manual checks;
   expected evidence location and responsible owner.
5. **Design comparison:** implementation screenshots/video beside the approved
   proof at matching viewport, content and state; note accessibility and
   interaction results that screenshots cannot prove.
6. **Disposition:** passing evidence, unresolved gaps, approved deviations and
   linked deferred issues. Reference the exact implementation commit.

A milestone is not complete because a demo looks good or code was pushed.
Reconcile the outcome against its tests, design and behavior evidence.
Examples: a website visitor submits a valid form and recovers from a failed
submission; a mobile user resumes an interrupted journey without data loss;
a player completes a loop, pauses and retries after failure. Apply only the
scenarios in the approved scope.

## Execute and reconcile without redundant gates

Once Phase 0 is approved, continue autonomous bounded implementation,
verification and in-scope repairs. Milestone demos are evidence checkpoints,
not automatic requests for permission to continue. Ask for a decision when
a genuine unresolved choice blocks progress, and return a focused deviation
brief when discovery changes approved observable behavior or risk boundaries
(including accessibility, security, data, cost or operations).

Record proposed deviations before treating them as accepted: affected
requirement, baseline proof, actual result, reason, risk, decision/approver
and evidence. Revise the immutable baseline after approval; do not silently
rewrite it to match the implementation.

At closeout, link milestone evidence, exact PRs/commits, comparisons, approved
deviations and deferred issues. Preserve separate review, CI, merge,
deployment, rollback and live-verification controls. Design approval,
milestone acceptance and local passing tests do not authorize deployment
or prove production success.
