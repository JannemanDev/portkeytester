"""Command line interface for the Portkey tester."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

import typer
from portkey_ai import Portkey
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

try:  # pragma: no cover - optional import for richer error typing
    from portkey_ai._vendor.openai._exceptions import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
    )
except Exception:  # pragma: no cover - fallback if the vendor module changes
    APIConnectionError = APITimeoutError = AuthenticationError = tuple()  # type: ignore

app = typer.Typer(add_completion=False, help="Validate Portkey API keys and routing targets.")
console = Console()


@dataclass
class ModelTestResult:
    """Aggregated information for a single model probe."""

    slug: str
    endpoint: str
    resolved_model: Optional[str]
    provider: Optional[str]
    config: Optional[str]
    latency_ms: Optional[float]
    usage: Dict[str, Any] = field(default_factory=dict)
    status: str = "fail"
    reason: Optional[str] = None
    failure_category: Optional[str] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None
    trace_id: str = ""
    span_id: str = ""
    headers: Dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    @property
    def tokens_total(self) -> Optional[int]:
        total = self.usage.get("total_tokens")
        if isinstance(total, int):
            return total
        return None


def _resolve_api_key(explicit: Optional[str]) -> str:
    """Resolve the API key from options, environment, stdin, or prompt."""

    if explicit:
        return explicit

    env_key = os.getenv("PORTKEY_API_KEY")
    if env_key:
        return env_key

    if not sys.stdin.isatty():
        piped = sys.stdin.readline().strip()
        if piped:
            return piped

    try:
        from getpass import getpass

        key = getpass("Portkey API key: ").strip()
    except (EOFError, KeyboardInterrupt):  # pragma: no cover - interactive fallback
        key = ""

    if not key:
        raise typer.Exit(code=1)
    return key


def _resolve_models(models_option: Optional[str], supplied: Optional[Sequence[str]]) -> List[str]:
    if supplied:
        return [model.strip() for model in supplied if model.strip()]
    if models_option:
        return [slug.strip() for slug in models_option.split(",") if slug.strip()]
    env_models = os.getenv("PORTKEY_MODELS")
    if env_models:
        parsed = [slug.strip() for slug in env_models.split(",") if slug.strip()]
        if parsed:
            return parsed

    if not sys.stdin.isatty():
        console.print("[bold red]No models provided via flags or environment.[/bold red]")
        raise typer.Exit(code=1)

    response = console.input("Models to test (comma separated): ").strip()
    models = [slug.strip() for slug in response.split(",") if slug.strip()]
    if not models:
        raise typer.Exit(code=1)
    return models


def _detect_endpoint(model_slug: str) -> str:
    slug = model_slug.lower()
    if "embed" in slug or slug.endswith("-embedding"):
        return "embeddings"
    return "chat"


def _extract_usage(response: Any) -> Dict[str, Any]:
    usage_obj = getattr(response, "usage", None)
    if not usage_obj:
        return {}
    usage: Dict[str, Any] = {}
    for attr in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage_obj, attr, None)
        if isinstance(value, int):
            usage[attr] = value
    return usage


def _normalize_headers(response: Any) -> Dict[str, str]:
    raw_headers: Dict[str, str] = {}
    headers = getattr(response, "_headers", None)
    if headers:
        raw_headers = {str(k).lower(): str(v) for k, v in headers.items()}
    return raw_headers


def _call_chat(
    client: Portkey,
    slug: str,
    headers: Dict[str, str],
    timeout: float,
) -> Any:
    return client.chat.completions.create(
        model=slug,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
        extra_headers=headers,
        timeout=timeout,
    )


def _call_embeddings(
    client: Portkey,
    slug: str,
    headers: Dict[str, str],
    timeout: float,
) -> Any:
    return client.embeddings.create(
        model=slug,
        input=["ok"],
        extra_headers=headers,
        timeout=timeout,
    )


def _provider_from_headers(headers: Dict[str, str]) -> Optional[str]:
    for key in ("x-portkey-provider", "x-portkey-provider-name", "x-portkey-vendor"):
        if key in headers:
            return headers[key]
    provider_values = [value for key, value in headers.items() if "provider" in key]
    if provider_values:
        return provider_values[0]
    return None


def _config_from_headers(headers: Dict[str, str]) -> Optional[str]:
    for key in ("x-portkey-config", "x-portkey-config-id"):
        if key in headers:
            return headers[key]
    return None


def _should_retry_endpoint(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    return bool(status_code and int(status_code) == 404)


def _categorize_failure(error: Exception) -> str:
    status_code = getattr(error, "status_code", None)
    if status_code in {401, 403} or isinstance(error, AuthenticationError):
        return "auth"
    if status_code and 500 <= int(status_code) < 600:
        return "server"
    if isinstance(error, (APITimeoutError, APIConnectionError)):
        return "sdk"
    return "client"


def _format_reason(prefix: str, expectation: str) -> str:
    return f"{prefix} '{expectation}'"


def _run_single_test(
    client: Portkey,
    slug: str,
    endpoint_preference: str,
    expect_models: Sequence[str],
    expect_providers: Sequence[str],
    timeout: float,
    session_trace_id: str,
) -> ModelTestResult:
    span_id = str(uuid.uuid4())
    trace_id = session_trace_id
    request_headers = {
        "x-portkey-trace-id": trace_id,
        "x-portkey-span-id": span_id,
    }

    primary_endpoint = endpoint_preference
    if primary_endpoint == "auto":
        primary_endpoint = _detect_endpoint(slug)

    endpoints_to_try: List[str] = [primary_endpoint]
    if endpoint_preference == "auto":
        fallback = "embeddings" if primary_endpoint == "chat" else "chat"
        endpoints_to_try.append(fallback)

    last_error: Optional[Exception] = None
    for idx, endpoint in enumerate(endpoints_to_try):
        start = time.perf_counter()
        try:
            if endpoint == "chat":
                response = _call_chat(client, slug, request_headers, timeout)
            else:
                response = _call_embeddings(client, slug, request_headers, timeout)
            latency_ms = (time.perf_counter() - start) * 1000
            headers = _normalize_headers(response)
            resolved_model = getattr(response, "model", None)
            provider = _provider_from_headers(headers)
            config = _config_from_headers(headers)
            usage = _extract_usage(response)

            status = "pass"
            reason: Optional[str] = None
            failure_category: Optional[str] = None

            lower_model = (resolved_model or "").lower()
            for expectation in expect_models:
                if expectation.lower() not in lower_model:
                    status = "fail"
                    reason = _format_reason("Model did not contain", expectation)
                    failure_category = "expectation"
                    break

            provider_blob = " ".join(headers.get(key, "") for key in headers if "provider" in key)
            if status == "pass":
                for expectation in expect_providers:
                    if expectation.lower() not in provider_blob.lower():
                        status = "fail"
                        reason = _format_reason("Provider did not contain", expectation)
                        failure_category = "expectation"
                        break

            return ModelTestResult(
                slug=slug,
                endpoint=endpoint,
                resolved_model=resolved_model,
                provider=provider,
                config=config,
                latency_ms=latency_ms,
                usage=usage,
                status=status,
                reason=reason,
                failure_category=failure_category,
                error_message=None,
                status_code=200,
                trace_id=trace_id,
                span_id=span_id,
                headers=headers,
            )
        except Exception as error:  # pragma: no cover - network heavy
            last_error = error
            failure_category = _categorize_failure(error)
            status_code = getattr(error, "status_code", None)
            message = getattr(error, "message", None) or str(error)
            should_stop = (
                endpoint_preference != "auto"
                or idx == len(endpoints_to_try) - 1
                or not _should_retry_endpoint(error)
            )
            if should_stop:
                return ModelTestResult(
                    slug=slug,
                    endpoint=endpoint,
                    resolved_model=None,
                    provider=None,
                    config=None,
                    latency_ms=None,
                    usage={},
                    status="fail",
                    reason=None,
                    failure_category=failure_category,
                    error_message=message,
                    status_code=status_code,
                    trace_id=trace_id,
                    span_id=span_id,
                    headers={},
                )
    assert last_error is not None  # pragma: no cover - logical guard
    message = getattr(last_error, "message", None) or str(last_error)
    failure_category = _categorize_failure(last_error)
    status_code = getattr(last_error, "status_code", None)
    return ModelTestResult(
        slug=slug,
        endpoint=endpoints_to_try[-1],
        resolved_model=None,
        provider=None,
        config=None,
        latency_ms=None,
        usage={},
        status="fail",
        reason=None,
        failure_category=failure_category,
        error_message=message,
        status_code=status_code,
        trace_id=trace_id,
        span_id=span_id,
        headers={},
    )


def _build_table(results: Iterable[ModelTestResult]) -> Table:
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Slug", style="bold")
    table.add_column("Endpoint", style="cyan")
    table.add_column("Resolved Model", style="green")
    table.add_column("Provider", style="magenta")
    table.add_column("Latency (ms)", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Status", style="bold")

    for result in results:
        status_style = "[green]PASS" if result.ok else "[red]FAIL"
        latency = f"{result.latency_ms:.0f}" if result.latency_ms is not None else "-"
        tokens = str(result.tokens_total) if result.tokens_total is not None else "-"
        table.add_row(
            result.slug,
            result.endpoint,
            result.resolved_model or "-",
            result.provider or "-",
            latency,
            tokens,
            status_style,
        )
    return table


def _results_to_json(
    results: Sequence[ModelTestResult],
    session_trace_id: str,
) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.ok)
    failed = total - passed
    return {
        "ok": failed == 0,
        "summary": {"passed": passed, "failed": failed, "total": total},
        "runs": [
            {
                "slug": r.slug,
                "endpoint": r.endpoint,
                "resolved_model": r.resolved_model,
                "provider": r.provider,
                "config": r.config,
                "latency_ms": r.latency_ms,
                "usage": r.usage,
                "status": r.status,
                "reason": r.reason,
                "failure_category": r.failure_category,
                "error": r.error_message,
                "status_code": r.status_code,
                "trace_id": r.trace_id,
                "span_id": r.span_id,
                "headers": r.headers,
            }
            for r in results
        ],
        "trace_id": session_trace_id,
    }


def _determine_exit_code(results: Sequence[ModelTestResult]) -> int:
    exit_code = 0
    for result in results:
        if result.ok:
            continue
        if result.failure_category in {"server", "sdk"}:
            return 5
        exit_code = max(exit_code, 2)
    return exit_code


@app.command()
def main(
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Portkey API key."),
    config_id: Optional[str] = typer.Option(None, "--config-id", help="Optional Portkey config identifier."),
    models: Optional[str] = typer.Option(None, "--models", "-m", help="Comma separated list of model slugs."),
    model: Optional[List[str]] = typer.Option(None, "--model", help="Repeatable single model slug option."),
    endpoint: str = typer.Option("auto", "--endpoint", help="Endpoint to target: auto, chat, or embeddings."),
    expect_model: Optional[List[str]] = typer.Option(None, "--expect-model", help="Expected substring in resolved model."),
    expect_provider: Optional[List[str]] = typer.Option(None, "--expect-provider", help="Expected substring in provider headers."),
    timeout: float = typer.Option(10.0, "--timeout", help="Request timeout in seconds."),
    output_format: str = typer.Option("table", "--format", help="Output format: table or json."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress per-model progress output."),
) -> None:
    endpoint = endpoint.lower()
    if endpoint not in {"auto", "chat", "embeddings"}:
        raise typer.BadParameter("Endpoint must be one of auto, chat, or embeddings.")

    output_format = output_format.lower()
    if output_format not in {"table", "json"}:
        raise typer.BadParameter("Format must be table or json.")

    resolved_key = _resolve_api_key(api_key)
    resolved_models = _resolve_models(models, model)
    resolved_config = config_id or os.getenv("PORTKEY_CONFIG_ID")
    expect_models = expect_model or []
    expect_providers = expect_provider or []

    client_kwargs: Dict[str, Any] = {"api_key": resolved_key}
    if resolved_config:
        client_kwargs["config"] = resolved_config

    client = Portkey(**client_kwargs)

    session_trace_id = str(uuid.uuid4())
    results: List[ModelTestResult] = []

    use_progress = not quiet and output_format == "table"
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    )

    if use_progress:
        task_id = progress.add_task("Testing models", total=len(resolved_models))
        progress.start()
    else:
        task_id = None

    try:
        for slug in resolved_models:
            if use_progress and task_id is not None:
                progress.update(task_id, description=f"Testing {slug}")
            result = _run_single_test(
                client=client,
                slug=slug,
                endpoint_preference=endpoint,
                expect_models=expect_models,
                expect_providers=expect_providers,
                timeout=timeout,
                session_trace_id=session_trace_id,
            )
            results.append(result)
            if use_progress and task_id is not None:
                progress.advance(task_id)
    finally:
        if use_progress:
            progress.stop()

    if output_format == "json":
        payload = _results_to_json(results, session_trace_id)
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        table = _build_table(results)
        console.print(table)
        passed = sum(1 for r in results if r.ok)
        failed = len(results) - passed
        summary_style = "green" if failed == 0 else "red"
        summary_panel = Panel(
            f"Passed: {passed}  Failed: {failed}  Total: {len(results)}",
            title="Summary",
            border_style=summary_style,
        )
        console.print(summary_panel)

        for result in results:
            if result.ok:
                continue
            detail_lines = []
            if result.reason:
                detail_lines.append(f"Reason: {result.reason}")
            if result.error_message:
                detail_lines.append(f"Error: {result.error_message}")
            if result.status_code:
                detail_lines.append(f"HTTP Status: {result.status_code}")
            detail_lines.append(f"Trace ID: {result.trace_id}")
            detail_lines.append(f"Span ID: {result.span_id}")
            console.print(
                Panel(
                    "\n".join(detail_lines),
                    title=f"[red]{result.slug}[/red]",
                    border_style="red",
                )
            )

    raise typer.Exit(code=_determine_exit_code(results))


if __name__ == "__main__":  # pragma: no cover
    app()
