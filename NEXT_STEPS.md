# Recommended Next Steps

1. **Restore a slim interactive entry point**  
   Some users preferred the original `test_portkey.py` workflow where prompts appeared immediately without additional installation steps. Consider keeping the Typer CLI as the core but add a small shim that mirrors the original prompts and forwards arguments explicitly so long-time users are not surprised by the new UX.

2. **Add regression coverage for endpoint routing**  
   The `_detect_endpoint` helper in `src/portkeytester/cli.py` still falls back to substring heuristics ("embed" or "-embedding"). Creating tests that exercise embeddings without those substrings will surface the need to let users specify endpoints per-model rather than globally.

3. **Split formatting from transport logic**  
   The CLI currently interleaves API calls, result aggregation, and Rich rendering in a single module. Moving transport helpers into a separate module would make it easier to unit test logic without invoking Rich, and to expose a pure-Python API for downstream automation.

4. **Document machine-readable exit codes with examples**  
   Although `README.md` lists exit codes, adding concrete shell snippets that demonstrate using the exit codes in CI scripts (e.g., `set -e`, GitHub Actions) would help users adopt the tool programmatically. Pair the documentation with automated tests that assert the Typer command returns the expected codes for mocked pass/fail scenarios.

5. **Capture per-model correlation identifiers**  
   Each `ModelTestResult` already stores `trace_id` and `span_id`, but only a request-level identifier is returned in JSON. Enrich the JSON schema so that every run includes the identifiers that Portkey expects for log correlation. Provide a README example showing how to paste one into the Portkey dashboard.

