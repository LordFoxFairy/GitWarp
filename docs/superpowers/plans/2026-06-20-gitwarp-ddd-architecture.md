# GitWarp DDD Architecture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor GitWarp into a production-grade DDD-inspired architecture while preserving CLI, Web, plugin, and JSON behavior.

**Architecture:** Introduce typed domain objects and application use cases, isolate infrastructure adapters, and split the web console into contracts/security/resources/controllers/transport/server modules. Keep compatibility shims during migration so behavior remains stable.

**Tech Stack:** Python standard library, Git CLI, unittest, setuptools package layout.

---

## Chunk 1: Architecture Guardrails

**Files:**
- Create: `src/gitwarp/domain/`
- Create: `src/gitwarp/application/`
- Create: `src/gitwarp/infrastructure/`
- Create: `src/gitwarp/webapp/`
- Modify: `tests/test_packaging.py`

- [ ] Add failing packaging tests that require real DDD package directories and webapp modules.
- [ ] Add minimal module skeletons with non-placeholder responsibilities.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_packaging.py' -v`.
- [ ] Commit `refactor: add gitwarp architecture boundaries`.

## Chunk 2: Domain Model and Policies

**Files:**
- Create: `src/gitwarp/domain/errors.py`
- Create: `src/gitwarp/domain/model.py`
- Create: `src/gitwarp/domain/policies.py`
- Modify: `src/gitwarp/foundation.py`
- Modify: `src/gitwarp/worktrees.py`
- Test: `tests/test_domain.py`

- [ ] Add tests for `WorktreeSnapshot`, `WorkspaceRecord`, `DossierRef`, `HeadDrift`, branch collision, target selection, and guarded-root policy.
- [ ] Implement immutable dataclasses plus dict mappers.
- [ ] Move pure policy functions behind `domain/policies.py` and keep root wrappers.
- [ ] Run `python3 -m unittest discover -s tests -p 'test_domain.py' -v`.
- [ ] Commit `refactor: introduce gitwarp domain model`.

## Chunk 3: Application Services

**Files:**
- Create: `src/gitwarp/application/dto.py`
- Create: `src/gitwarp/application/services.py`
- Modify: `src/gitwarp/services.py`
- Modify: `src/gitwarp/cli.py`
- Test: existing CLI and web workflow tests.

- [ ] Move web-facing use case builders from root `services.py` to `application/services.py`.
- [ ] Make root `services.py` a compatibility re-export.
- [ ] Replace duplicated `cmd_start`, `cmd_dispatch`, `cmd_handoff`, `cmd_finish`, and `cmd_collapse` workflow logic in `cli.py` with application service calls.
- [ ] Run CLI lifecycle, worktree, and web API tests.
- [ ] Commit `refactor: route gitwarp commands through application services`.

## Chunk 4: WebApp Extraction and XSS Fix

**Files:**
- Create: `src/gitwarp/webapp/contracts.py`
- Create: `src/gitwarp/webapp/security.py`
- Create: `src/gitwarp/webapp/resources.py`
- Create: `src/gitwarp/webapp/controllers.py`
- Create: `src/gitwarp/webapp/transport.py`
- Create: `src/gitwarp/webapp/server.py`
- Modify: `src/gitwarp/web.py`
- Split/Add tests: `tests/test_web_contracts.py`, `tests/test_web_security.py`, `tests/test_web_resources.py`, `tests/test_web_api.py`

- [ ] Characterize current schema, token, host validation, confirmation, and dossier behavior.
- [ ] Extract endpoint registry and request validation to `contracts.py`.
- [ ] Extract host/token/confirmation security to `security.py`.
- [ ] Extract safe dossier reads and inline HTML to `resources.py`.
- [ ] Extract route orchestration to `controllers.py`.
- [ ] Extract HTTP request handling to `transport.py`.
- [ ] Extract server lifecycle/readiness JSON to `server.py`.
- [ ] Replace inline UI `innerHTML` rendering with DOM text assignment.
- [ ] Run all web tests.
- [ ] Commit `refactor: split gitwarp web application`.

## Chunk 5: Mirror, Docs, and Verification

**Files:**
- Modify: `README.md`
- Modify: `skills/gitwarp/SKILL.md`
- Modify: `skills/gitwarp/references/install.md`

- [ ] Ensure runtime code exists only in root `src/gitwarp` and no `plugins/gitwarp/src` copy exists.
- [ ] Update docs with DDD source layout and web security/runtime behavior.
- [ ] Run py_compile, skill validation, plugin validation, full unittest, install smoke, and `git diff --check`.
- [ ] Record GitWarp handoff.
- [ ] Merge to `main` and push after verification.
