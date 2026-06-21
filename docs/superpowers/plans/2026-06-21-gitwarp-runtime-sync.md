# GitWarp Runtime Sync Plan

## Steps
1. Add tests for stale launcher detection and explicit upgrade behavior.
2. Implement `application/use_cases/runtime_sync.py` with probe, check, and write operations.
3. Wire `gitwarp upgrade` into the CLI parser and system adapter.
4. Integrate launcher capability checks into doctor recommendations.
5. Update packaging, README, and skill guidance so users know when to run upgrade.
6. Run focused tests, then the release check script.

## Verification
- `python3 -m unittest discover -s tests -p 'test_runtime_sync.py' -v`
- `python3 -m unittest discover -s tests -p 'test_doctor.py' -v`
- `python3 -m unittest discover -s tests -p 'test_packaging.py' -v`
- `scripts/check-release.sh`
