# Portkey Gateway Tester

Portkey Gateway Tester is a command-line utility that verifies whether a Portkey API key can reach the models you expect. It runs small real requests through the Portkey gateway, reports the resolved provider/model, and exposes trace identifiers so that you can follow the traffic inside Portkey's dashboard.

## What it does

- Sends minimal chat or embedding requests against each model slug you specify.
- Forces the desired endpoint with `--endpoint` or chooses automatically when left as `auto`.
- Validates routing with `--expect-model` / `--expect-provider` substrings and marks mismatches as failures.
- Prints a Rich table for humans or JSON for scripts/CI, always including the Portkey trace and span IDs.
- Exits with deterministic codes so automation can detect authentication errors or routing issues.

## When you might use it

- Smoke-testing that a new Portkey key or config is live before wiring it into production.
- Auditing that Portkey routes a slug to the intended upstream provider.
- Building CI checks that break the build when routing expectations are not met.
- Capturing trace IDs to debug misrouted or failing requests inside Portkey.

## Installation

Install the package into a Python 3.10+ environment. Pipx is recommended for isolated CLI installs.

```bash
# inside a virtual environment
pip install .

# or install globally via pipx
pipx install .
```

An `install.sh` helper is available if you prefer a venv managed by the repository:

```bash
source ./install.sh
```

## Quick start

Provide the API key, optional config, and the models you want to probe. Values can be passed through flags, environment variables, or interactively via prompts.

```bash
portkey-tester \
  --api-key $PORTKEY_API_KEY \
  --models mistral-large,text-embedding-3-small \
  --expect-model mistral \
  --expect-provider openai
```

If you omit `--api-key`, the CLI reads `PORTKEY_API_KEY`, then STDIN, and finally falls back to an interactive password prompt.

## CLI reference

| Flag | Description |
| ---- | ----------- |
| `--api-key` | Portkey API key. Falls back to `PORTKEY_API_KEY`, piped stdin, then a secure prompt. |
| `--config-id` | Optional Portkey config. Also reads `PORTKEY_CONFIG_ID`. |
| `--model` / `--models` | Repeatable flag or comma-separated list of slugs to test. Defaults to `PORTKEY_MODELS` when set. |
| `--endpoint` | One of `auto` (default), `chat`, `embeddings`. Forced values disable heuristic fallback. |
| `--expect-model` | Expected substring in the resolved `response.model`. Repeatable. |
| `--expect-provider` | Expected substring found in provider headers. Repeatable. |
| `--timeout` | Request timeout in seconds (default `10`). |
| `--format` | Output format: `table` (default) or `json`. |
| `--quiet` | Suppress progress UI and intermediate logging. |

Run `portkey-tester --help` for the full Typer-generated help text.

## Output formats

### Table view

Default output renders a Rich table plus a summary and detailed failure panels:

```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Slug               ┃ Endpoint  ┃ Resolved Model     ┃ Provider  ┃ Latency (ms)┃ Tokens ┃ Status ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ mistral-large      │ chat      │ mistral-large-2411 │ openai    │ 812         │ 27     │ PASS   │
│ text-embedding-…   │ embeddings│ text-embedding-3…  │ openai    │ 542         │ -      │ FAIL   │
└────────────────────┴───────────┴────────────────────┴───────────┴─────────────┴────────┴────────┘
┌ Summary ───────────────────────────────────────────────────────────────────────────────────────┐
│ Passed: 1  Failed: 1  Total: 2                                                                   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ text-embedding-3-small ──────────────────────────────────────────────────────────────────────────┐
│ Reason: Provider did not contain 'openai'                                                        │
│ Trace ID: 1c3f3f4e-...                                                                            │
│ Span ID: d845e538-...                                                                             │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### JSON view

Enable machine-readable output with `--format json` and optional `--quiet` for scripts:

```bash
portkey-tester --models mistral-large --format json --quiet
```

```json
{
  "ok": true,
  "summary": {"passed": 1, "failed": 0, "total": 1},
  "runs": [
    {
      "slug": "mistral-large",
      "endpoint": "chat",
      "resolved_model": "mistral-large-2411",
      "provider": "openai",
      "config": "config_123",
      "latency_ms": 812.37,
      "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
      "status": "pass",
      "trace_id": "1c3f3f4e-...",
      "span_id": "d845e538-...",
      "headers": {"x-portkey-provider": "openai"}
    }
  ],
  "trace_id": "2bff73c0-..."
}
```

## Exit codes

| Code | Meaning |
| ---- | ------- |
| `0` | All models authenticated and met expectations. |
| `2` | At least one model failed authentication or expectation checks. |
| `5` | Unexpected Portkey/SDK/network error. |

## Request payloads

To minimise cost, the CLI uses fixed minimal payloads:

- Chat endpoint: `[{"role": "user", "content": "ping"}]` with `max_tokens=1`
- Embeddings endpoint: `input=["ok"]`

Each request attaches generated `x-portkey-trace-id` and `x-portkey-span-id` headers so you can line them up with Portkey dashboard logs.

## Related files

- `src/portkeytester/cli.py` contains the Typer application and request logic.
- `test_portkey.py` forwards to the packaged CLI for people accustomed to running `python test_portkey.py`.
- `NEXT_STEPS.md` documents potential future improvements.

The CLI targets the [Portkey Inference API](https://portkey.ai/docs/api-reference/inference-api/introduction) and assumes valid Portkey credentials.
