# GitWarp Console v2 Action Queue Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `gitwarp next` action queue and surface it in the GitHub-like Web Console.

**Architecture:** Keep classification in the application layer so CLI and Web share one source of truth. CLI prints deterministic JSON, while React renders `state.next_actions` without reimplementing safety rules.

**Tech Stack:** Python standard library, unittest, React + TypeScript, Vite runtime asset mirroring.

---

## File Structure

- Create: `src/gitwarp/application/use_cases/next_actions.py` for read-only action queue classification.
- Modify: `src/gitwarp/application/use_cases/__init__.py` to export the use case.
- Modify: `src/gitwarp/adapters/cli/parser.py` to add `gitwarp next`.
- Modify: `src/gitwarp/adapters/cli/read.py` to emit the payload.
- Modify: `src/gitwarp/application/use_cases/web_state.py` to include `next_actions`.
- Modify: `src/gitwarp/webapp/contracts.py` only if Web state schema assertions need explicit command metadata.
- Modify: `web/console/src/app/types.ts` for `NextAction`.
- Modify: `web/console/src/app/components/ActionPanel.tsx` to render the queue.
- Modify: `web/console/src/app/App.tsx` to pass queue data.
- Modify: `web/console/src/styles.css` for GitHub-like action queue and hierarchy polish.
- Modify generated assets: `web/console/dist/*` and `src/gitwarp/assets/web_console/*`.
- Test: `tests/test_next_actions.py`, `tests/test_web_api.py`, `tests/test_packaging.py`.

## Chunk 1: Backend Action Queue

### Task 1: Failing CLI and Use Case Tests

- [ ] Add `tests/test_next_actions.py` covering healthy repos, merged refs, stale ledger rows, orphan dossiers, and untracked worktrees.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_next_actions.py' -v`.
- [ ] Confirm failure is due to missing `gitwarp next` / use case, not test setup.

### Task 2: Minimal Backend Implementation

- [ ] Create `src/gitwarp/application/use_cases/next_actions.py`.
- [ ] Reuse `build_matrix_payload`, `build_doctor_payload`, and `build_reconcile_payload`; do not mutate state.
- [ ] Add stable action fields: `id`, `priority`, `severity`, `safety`, `category`, `title`, `description`, `command`, `source`, `branch`, `path`.
- [ ] Add `cmd_next` and parser entry.
- [ ] Run the focused test until green.

## Chunk 2: Web State and React Console

### Task 3: Failing Web API/Packaging Tests

- [ ] Update `tests/test_web_api.py` to assert `/api/state` includes `next_actions`.
- [ ] Update `tests/test_packaging.py` to assert Web source renders action queue wording and generated assets are synced.
- [ ] Run the focused tests and confirm they fail for the missing UI/data path.

### Task 4: Web Integration

- [ ] Add `NextAction` types in `web/console/src/app/types.ts`.
- [ ] Render `next_actions` in `ActionPanel` with safety labels and recommended commands.
- [ ] Keep destructive actions visually clear but not primary.
- [ ] Ensure Code/Metadata tab switching remains state-based and does not blank existing content.
- [ ] Run `npm run build` and `npm run check:dist`.

## Chunk 3: Docs, Skill, and Release Gate

### Task 5: Documentation and Skill Copy

- [ ] Update `README.md` and `skills/gitwarp/SKILL.md` with `gitwarp next`.
- [ ] Add `gitwarp next` to relevant verification scripts only if it improves smoke coverage.
- [ ] Record progress with `gitwarp handoff`.

### Task 6: Verification

- [ ] Run `python3 -m unittest discover -s tests -p 'test_next_actions.py' -v`.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_web_api.py' -v`.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_packaging.py' -v`.
- [ ] Run `scripts/check-release.sh`.
- [ ] Finish with `gitwarp finish --status verified` and leave the worktree intact.
