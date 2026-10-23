# Gates: migration engine code audit

OWNS: **/*

Scope: Review CSV parsing, comparison integrity, numeric bounds, UI state, privacy, and report handling.

- [x] M1: Existing UI audit and new engine regression tests pass.
  CHECK: .venv\Scripts\python.exe tests\run_audit.py
  EXPECT: MIGRATION WORKBENCH AUDIT PASSED
  EVIDENCE: automatic-evidence=v1; definition-sha256=3680cb833432abc1142788ebf75f5bb55b9731e585745d585c00f1ad97feb1fc; exit=0; EXPECT=matched; output-sha256=3500903845188003e2c1ee47e71a7aafdb03e186680680e42a0e56e4b8ebfb84; output-bytes=1955; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\bradk\erp-data-migration-checker; path=b45c073664ed/40 entries
- [x] M2: Independent engine cases pass including malformed CSV, invalid encoding, keys, tolerance and truncation.
  CHECK: .venv\Scripts\python.exe -m unittest discover -s tests -p test_engine.py
  EXPECT: OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=9ca781cc8e322a1aa1cdf2dd7174409b73c1a2ba8a6d77d08017b490166f2817; exit=0; EXPECT=matched; output-sha256=0449c08e09fa689b49d3700b5daad376c6704b67b19ed4faec918c6c9d3ee6a5; output-bytes=109; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\bradk\erp-data-migration-checker; path=b45c073664ed/40 entries
- [x] M3: Audit documents actual limits and verification.
  EVIDENCE: AUDIT-2026-10-22.md and README record six engine and 15 UI checks, parser bounds, library compatibility and ERP scope limits; skill validation passed.

M3 evidence: AUDIT-2026-10-22.md and README record six engine and 15 UI checks, parser/numeric bounds, library compatibility and ERP scope limitations. Skill quick_validate.py passed.

