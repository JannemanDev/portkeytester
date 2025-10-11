# Portkey AI Gateway Tester

A CLI that verifies whether your Portkey API key works and whether a given model slug routes to the provider you expect. It uses the official Portkey Python SDK, keeps requests tiny, and surfaces all of the routing headers Portkey returns.

## Highlights

- 🔐 Works non-interactively via CLI flags or environment variables (still prompts if you omit values).
- 🎯 Explicit endpoint selection with `--endpoint` (`auto`, `chat`, or `embeddings`). No hidden fallbacks when you force an endpoint.
- ✅ Routing validation via `--expect-model` / `--expect-provider` substrings – failures are reflected in the exit code.
- 📡 Correlation IDs (`x-portkey-trace-id` / `x-portkey-span-id`) are set on every request and echoed back in the output.
- 📊 Rich-powered table output for humans, or `--format json` for scripts/CI.
- 🚦 Deterministic exit codes: `0` (all pass), `2` (auth/expectation failure), `5` (SDK/server errors).

## Installation

The project ships as a normal Python package. You can install it into a virtual environment, or use the existing `install.sh` helper if you prefer.

### Option 1 – pip / pipx

```bash
# inside a venv or global (pipx is great for CLIs)
pip install .
# or
pipx install .
```

This installs the `portkey-tester` command.

### Option 2 – helper script

```bash
source ./install.sh
```

The script creates `.venv/`, installs dependencies in editable mode, and leaves the virtual environment activated.

## Usage

Run the CLI directly after installation:

```bash
portkey-tester --api-key sk_live_... --models mistral-large,claude-3-sonnet
```

Key options:

| Flag | Description |
| ---- | ----------- |
| `--api-key` | Portkey API key. Falls back to `PORTKEY_API_KEY`, piped stdin, then a secure prompt. |
| `--config-id` | Optional Portkey config to pin routing. Also reads `PORTKEY_CONFIG_ID`. |
| `--models` / `--model` | Comma separated string or repeatable flag with model slugs to probe. |
| `--endpoint` | `auto` (default), `chat`, or `embeddings`. Forced values disable fallback. |
| `--expect-model` | Expected substring in the resolved `response.model`. Repeatable. |
| `--expect-provider` | Expected substring found in provider headers. Repeatable. |
| `--timeout` | Request timeout in seconds (default `10`). |
| `--format` | `table` (default) or `json`. |
| `--quiet` | Skip progress UI and intermediate output. |

Environment variables:

- `PORTKEY_API_KEY`
- `PORTKEY_CONFIG_ID`
- `PORTKEY_MODELS` (comma separated)

### Table output example

```bash
portkey-tester --models mistral-large,text-embedding-3-small --expect-model mistral --expect-provider openai
```

```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Slug               ┃ Endpoint  ┃ Resolved Model     ┃ Provider  ┃ Latency (ms)┃ Tokens ┃ Status ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ mistral-large      │ chat      │ mistral-large-2411 │ openai    │ 812         │ 27     │ PASS   │
│ text-embedding-…   │ embeddings│ text-embedding-3…  │ openai    │ 542         │ -      │ FAIL   │
└────────────────────┴───────────┴────────────────────┴───────────┴─────────────┴────────┴────────┘
┌ Summary ────────────────────────────────────────────────────────────────────────────────────────┐
│ Passed: 1  Failed: 1  Total: 2                                                                   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ text-embedding-3-small ──────────────────────────────────────────────────────────────────────────┐
│ Reason: Provider did not contain 'openai'                                                        │
│ Trace ID: 1c3f3f4e-...                                                                            │
│ Span ID: d845e538-...                                                                             │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### JSON output example

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

### Exit codes

- `0` – every model passed validation.
- `2` – at least one model failed authentication or expectation checks.
- `5` – unexpected 5xx/SDK/network error.

## Request payloads

To keep costs negligible the CLI sends:

- Chat: `[{"role": "user", "content": "ping"}]` with `max_tokens=1`
- Embeddings: `input=["ok"]`

Both calls attach the generated `x-portkey-trace-id` / `x-portkey-span-id` headers so you can line them up with the Portkey dashboard logs.

## Additional notes

- The CLI is built on top of the [Portkey Inference API](https://portkey.ai/docs/api-reference/inference-api/introduction).
- If you prefer raw HTTP requests, you can adapt the payloads above to `curl` or any HTTP client.
- `python test_portkey.py` continues to work and simply dispatches to the packaged CLI.
