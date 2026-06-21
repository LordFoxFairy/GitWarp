---
artifact: prd
version: "1.0"
created: 2026-06-21
status: draft
---

# PRD: GitWarp Console v2 and Action Queue

## Overview

### Problem Statement
GitWarp can already inspect Git refs, live worktrees, ledger rows, dossiers, and health findings, but the current experience still asks humans and agents to interpret too many raw surfaces. The Web Console should feel like a familiar repository manager: open a project, choose a base branch, inspect its task worktrees, and see the next safe actions without reading every diagnostic page.

### Solution Summary
Add a read-only `gitwarp next` command that converts matrix, reconcile, and doctor findings into a prioritized action queue. Surface the same queue in Web Console v2 through a GitHub-like project detail flow with base/task hierarchy, clear action safety, and no hidden destructive behavior.

### Target Users
Human maintainers supervising concurrent Codex or Claude Code worktrees, plus agents that need deterministic JSON guidance before switching, adopting, pruning, or cleaning up workspaces.

## Goals & Success Metrics

### Goals
1. Make the next safe maintenance step obvious from CLI and Web.
2. Keep all cleanup and destructive decisions human-confirmed.
3. Preserve one source of truth for action classification across CLI and Web.

### Success Metrics

| Metric | Current Baseline | Target | Timeline |
|--------|------------------|--------|----------|
| Time to identify active vs cleanup work | Manual matrix interpretation | Under 30 seconds from Web project detail | v2 launch |
| Destructive action ambiguity | Mixed across panels | Every destructive action shows safety and command | v2 launch |
| Rule duplication | Web interprets several payloads | Web consumes `next_actions` from backend | v2 launch |

### Non-Goals
- Automatically merge, push, remove, collapse, or prune branches.
- Replace `matrix`, `branches`, `doctor`, or `reconcile`.
- Manage remote GitHub/GitLab pull requests.

## User Stories

| ID | User Story | Priority |
|----|------------|----------|
| US-1 | As a maintainer, I want a prioritized action queue so I can see what needs attention first. | P0 |
| US-2 | As a maintainer, I want worktrees grouped by base branch so task ownership is understandable. | P0 |
| US-3 | As an agent, I want deterministic JSON next actions so I can avoid unsafe Git operations. | P0 |
| US-4 | As a maintainer, I want branch cleanup to remain explicit and confirmable. | P1 |

## Scope

### In Scope
- `gitwarp next` as a read-only single-line JSON command.
- Application-level action queue classification with severity, safety, source, command, and explanation.
- Web state includes `next_actions`.
- Web Console adds a project-first action panel and base/task grouping affordances.
- Tests for CLI output, Web API state, and UI source/runtime asset sync.

### Out of Scope
- Background process execution or automatic agent dispatch.
- Remote repository integrations.
- Multi-repository discovery outside the current Git repository.

### Future Considerations
- `gitwarp cleanup --plan` can consume next actions and produce a typed confirmation flow.
- `gitwarp run` can use next actions to decide when a task sandbox is safe to launch or retire.

## Solution Design

### Functional Requirements

#### Action Queue
- FR-1: `gitwarp next` must not mutate Git, ledger, dossiers, or branch refs.
- FR-2: Each action must include `id`, `priority`, `severity`, `safety`, `category`, `title`, `description`, `command`, and `source`.
- FR-3: Actions must be sorted by priority, with unsafe or human-review items before low-risk informational items.
- FR-4: Matrix categories such as `merged_task`, `merged_ref`, `stale_ledger`, `orphan_dossier`, and `untracked_worktree` must map to explicit next actions.

#### Web Console
- FR-5: Web state must include the same `next_actions` payload returned by `gitwarp next`.
- FR-6: Project detail must show next actions without requiring users to open Health first.
- FR-7: Worktrees must be understandable as base/task relationships, not an undifferentiated list.
- FR-8: Destructive operations must remain behind existing confirmation flows.

### User Experience
Use a restrained GitHub-like layout: project directory first, repository detail second, tabbed Code/Metadata/Branches/Health views, and a right-side action queue. The signature interaction is selecting a base or task in one place and seeing Code, Metadata, and next actions update around that selection.

### Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Invalid ledger | `gitwarp next` returns a review action pointing to ledger repair guidance, without mutation. |
| Clean healthy repo | Action queue returns an empty list plus summary counts. |
| Merged task still mounted | Queue recommends explicit `finish --collapse-merged`, marked destructive and confirmation-required. |
| Merged task has dirty files | Queue recommends inspection first and must not show a collapse command. |
| Merged local ref not mounted | Queue recommends `prune-branch`, marked destructive and confirmation-required. |
| Untracked worktree | Queue recommends `adopt`, marked non-destructive but human-review. |

## Technical Considerations

### Constraints
- Use Python standard library for backend behavior.
- Keep DDD boundaries: action classification belongs in `application/use_cases`, CLI in `adapters/cli`, Web state in `application/use_cases/web_state.py`.
- React source remains in `web/console`; generated runtime assets are mirrored into `src/gitwarp/assets/web_console`.

### Integration Points
- Matrix: source of Git/GitWarp control-plane rows.
- Doctor/Reconcile: source of health and drift findings.
- Web API state: transport payload for React Console.

### Data Requirements
No data migration. `next_actions` is derived state and must not be persisted.

## Dependencies & Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Web duplicates backend rules | Medium | High | Web only renders `next_actions`; backend owns classification. |
| Action wording implies automation | Medium | Medium | Copy must say "recommended command" and preserve confirmation language. |
| Queue gets noisy | Medium | Medium | Use priority and limit visual prominence to actionable findings. |

## Timeline & Milestones

| Milestone | Description | Target Date |
|-----------|-------------|-------------|
| M1 | PRD, implementation plan, and failing tests | 2026-06-21 |
| M2 | Backend `gitwarp next` and Web state integration | 2026-06-21 |
| M3 | React Console action panel and asset regeneration | 2026-06-21 |
| Launch | Release gate passes and handoff recorded | 2026-06-21 |

## Open Questions

- [ ] Should future Web support multiple known repositories, or stay scoped to current repo until a registry exists? Owner: product.
- [ ] Should action queue default to showing only P0/P1 items when more than ten findings exist? Owner: product.

## Appendix

### Related Documents
- `docs/superpowers/specs/2026-06-19-gitwarp-web-console-design.md`
- `docs/superpowers/specs/2026-06-20-gitwarp-ddd-architecture-design.md`
- `docs/superpowers/specs/2026-06-21-gitwarp-agent-task-inbox-design.md`

### Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-21 | Codex | Initial draft |
