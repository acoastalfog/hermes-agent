# Guided KB Review Sessions Boundary

This note tracks the Hermes side of Guided KB Review Sessions and Decision
Cards. It supports hermes-agent issues #35, #36, #37, and #38.

## Current Runtime Boundary

Hermes owns the mobile/runtime presentation layer:

- Telegram `/kb` interception and compact KB cockpit rendering.
- Generic Decision Card button registration and callback dispatch.
- Telegram-specific text fallback, expired button copy, and compact receipts.
- Guided queue card layout, Details, Ask LLM, Skip, preview, confirm, receipt,
  and restore affordances.
- Publication, workflow, report handoff, meeting handoff, and closeout card
  rendering when kb-engine descriptors provide the canonical route.

kb-engine owns durable KB semantics:

- `dashboard_action_descriptor.v2` shape and descriptor provenance.
- Guided review session packets, preview leases, cursor ids, decision scopes,
  receipts, restore hints, and request lifecycle state.
- Preview-only and confirmed write tools such as `queue.decision_preview`,
  `queue.batch_decide_confirmed`, publication confirmed routes, report admission
  routes, and restore routes.
- Redaction and durable source/KB provenance. Hermes must not become a parallel
  write path.

NOC owns deployment/runtime posture:

- Installed Hermes ref, desired ref, rollback ref, host placement, Telegram
  environment, model gateway/provider posture, canaries, and release-alignment
  gates.
- Route selection between `helix` for Hermes/Telegram and `helix-vpn` for
  `kb_engine_prod`.

Skills own behavioral guidance only:

- Review posture, user-intent patterns, and goal-prompt guidance.
- Skills can remind Hermes/Codex to preview first and keep advisory guidance
  non-authoritative, but they cannot enforce preview leases, callback auth,
  route placement, or confirmed write policy.

## Portability Classification

| Bucket | Hermes behavior | Direction |
| --- | --- | --- |
| KB plugin-owned | `/kb` journeys, KB dashboard/workbench rendering, queue review cards, publication cards, report/meeting handoff cards, receipts, restore actions, and advisory guidance cards. | Extract to an out-of-tree KB Hermes plugin after the descriptor/session runtime is stable. |
| Upstream candidate | Opaque callback ids, TTL, chat/topic scoping, action-card send/follow-up, expired callback handling, and generic text fallback. | Generalize names beyond KB and upstream if mainline wants the primitive. |
| kb-engine contract | Descriptors, sessions, cursors, preview leases, decision scopes, confirmed envelopes, receipts, and restore hints. | Keep in kb-engine; Hermes consumes packets and calls canonical tools only. |
| NOC config/deploy | Runtime pins, host placement, app env, canaries, rollout/rollback, route/IP validation. | Keep in NOC; Hermes code must not encode deployment facts. |
| Skill guidance | Anthony/KB review style, mobile cockpit expectations, advisory-only guidance language. | Keep as skills and docs; never rely on prose for safety. |
| Fork debt | Legacy `/kbqueue` aliases, KB-specific callback names in generic gateway primitives, deprecated live-dashboard bridge, Hermes-side config writes that should be NOC-owned. | Retire after plugin extraction and upstream/mainline classification. |

## Near-Term Extraction Plan

1. Finish Hermes #23/#24/#26 on the current in-tree plugin so behavior is
   tested before code moves.
2. Keep the public kb-engine contracts unchanged: Hermes receives descriptors
   and sessions, then calls preview/confirmed routes with returned leases.
3. Split `plugins/kb_journeys` into an out-of-tree KB plugin with the same
   tests and canary scenarios.
4. Rename or wrap `tools/kb_callback_registry.py` only after the generic
   callback primitive has an upstreamable API shape.
5. Retire legacy command aliases and deprecated bridge code only after NOC
   canaries prove the new plugin path and rollback ref.

## Acceptance Notes

- Advisory guidance buttons must never confirm writes, mint preview leases, or
  call confirmed tools.
- Telegram callback ids must stay opaque, one-shot, scoped, and TTL-bound.
- Hidden queue items must never be affected by visible-window actions unless a
  backend preview explicitly names the wider scope and affected ids/count.
- Expired/stale callback and preview-lease states must tell the operator to
  refresh the guided review surface, not to memorize raw command syntax.
