"""LLM provider abstraction for /staff scripts.

Three concrete providers ship today; selection is by env var STAFF_LLM:

  STAFF_LLM=codex    (default)  - codex exec subprocess
  STAFF_LLM=claude               - claude --print subprocess
  STAFF_LLM=local                - HTTP POST to an OpenAI-compatible endpoint
                                   (set STAFF_LLM_URL + STAFF_LLM_MODEL,
                                   optionally STAFF_LLM_API_KEY)

Failure is loud — provider unavailable, timeout, malformed output all raise
LLMError. Callers decide whether to retry or fail the operation. There is
no silent fallback to a different provider, which would surprise users.

The abstraction is deliberately small: prompt + system + structured-output
schema (optional). If a future provider needs streaming, multimodal, or
tool-use, those go in subclasses, not the base interface.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LLMError(RuntimeError):
    """Raised when an LLM provider fails (unavailable, timeout, parse error)."""


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str | None = None
    raw: Any = None


class LLMProvider(ABC):
    """Single-shot prompt → response. No streaming, no tools, no multi-turn."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def call(
        self,
        prompt: str,
        system: str | None = None,
        json_schema: dict | None = None,
        timeout_sec: int = 120,
    ) -> LLMResponse: ...


class CodexCLIProvider(LLMProvider):
    """Default: codex exec --sandbox read-only --output-last-message <tmp>."""

    @property
    def name(self) -> str:
        return "codex-cli"

    def call(
        self,
        prompt: str,
        system: str | None = None,
        json_schema: dict | None = None,
        timeout_sec: int = 120,
    ) -> LLMResponse:
        if shutil.which("codex") is None:
            raise LLMError("codex CLI not found on PATH")

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            last_msg = tmp / "last.txt"
            cmd = [
                "codex", "exec",
                "--sandbox", "read-only",
                "--skip-git-repo-check",
                "--output-last-message", str(last_msg),
            ]
            if json_schema is not None:
                schema_path = tmp / "schema.json"
                schema_path.write_text(json.dumps(json_schema), encoding="utf-8")
                cmd.extend(["--output-schema", str(schema_path)])

            full_prompt = prompt if system is None else f"{system}\n\n{prompt}"
            cmd.append(full_prompt)
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout_sec, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise LLMError(f"codex CLI timed out after {timeout_sec}s") from exc

            if result.returncode != 0:
                raise LLMError(
                    f"codex CLI exited {result.returncode}: {result.stderr.strip()[:500]}"
                )
            if not last_msg.exists():
                raise LLMError("codex CLI did not write --output-last-message file")
            text = last_msg.read_text(encoding="utf-8").strip()
            if not text:
                raise LLMError("codex CLI returned empty output")
            return LLMResponse(text=text, provider=self.name, model=None, raw=None)


class ClaudeCLIProvider(LLMProvider):
    """Fallback: claude --print --output-format json [--json-schema ...]."""

    @property
    def name(self) -> str:
        return "claude-cli"

    def call(
        self,
        prompt: str,
        system: str | None = None,
        json_schema: dict | None = None,
        timeout_sec: int = 120,
    ) -> LLMResponse:
        if shutil.which("claude") is None:
            raise LLMError("claude CLI not found on PATH")

        cmd = ["claude", "--print", "--output-format", "json"]
        if system is not None:
            cmd.extend(["--append-system-prompt", system])
        if json_schema is not None:
            cmd.extend(["--json-schema", json.dumps(json_schema)])

        try:
            result = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                timeout=timeout_sec, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LLMError(f"claude CLI timed out after {timeout_sec}s") from exc

        if result.returncode != 0:
            raise LLMError(
                f"claude CLI exited {result.returncode}: {result.stderr.strip()[:500]}"
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise LLMError(f"claude CLI returned non-JSON output: {exc}") from exc
        text = payload.get("result") or payload.get("text") or ""
        if not text:
            raise LLMError(f"claude CLI returned empty result; payload keys: {list(payload.keys())}")
        return LLMResponse(
            text=str(text).strip(),
            provider=self.name,
            model=payload.get("model"),
            raw=payload,
        )


class OpenAICompatibleProvider(LLMProvider):
    """Local LLM via OpenAI-compatible HTTP API (ollama, vLLM, llama.cpp server, OpenAI itself).

    Configure with STAFF_LLM_URL (e.g. http://beelink:11434/v1), STAFF_LLM_MODEL
    (e.g. qwen2.5-coder:14b), and optionally STAFF_LLM_API_KEY."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "openai-compatible"

    def call(
        self,
        prompt: str,
        system: str | None = None,
        json_schema: dict | None = None,
        timeout_sec: int = 120,
    ) -> LLMResponse:
        messages: list[dict] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }
        if json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": json_schema, "strict": True},
            }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/chat/completions"
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise LLMError(f"HTTP call to {url} failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMError(f"HTTP response not valid JSON: {exc}") from exc

        choices = payload.get("choices") or []
        if not choices:
            raise LLMError(f"no choices in response; keys={list(payload.keys())}")
        text = (choices[0].get("message") or {}).get("content", "").strip()
        if not text:
            raise LLMError("response.choices[0].message.content was empty")
        return LLMResponse(text=text, provider=self.name, model=self.model, raw=payload)


def get_provider(override: str | None = None) -> LLMProvider:
    """Resolve the LLM provider from STAFF_LLM (or override)."""
    name = (override or os.environ.get("STAFF_LLM") or "codex").lower()

    if name in ("codex", "codex-cli"):
        return CodexCLIProvider()
    if name in ("claude", "claude-cli"):
        return ClaudeCLIProvider()
    if name in ("local", "openai", "openai-compatible", "http"):
        url = os.environ.get("STAFF_LLM_URL")
        model = os.environ.get("STAFF_LLM_MODEL")
        if not url or not model:
            raise LLMError(
                "openai-compatible provider requires STAFF_LLM_URL and STAFF_LLM_MODEL"
            )
        return OpenAICompatibleProvider(url, model, os.environ.get("STAFF_LLM_API_KEY"))

    raise LLMError(f"unknown STAFF_LLM provider: {name!r}")


def call_with_json(
    provider: LLMProvider,
    prompt: str,
    schema: dict,
    *,
    system: str | None = None,
    timeout_sec: int = 120,
    retries: int = 1,
) -> dict:
    """Wrapper that calls the provider, parses the response as JSON, and
    optionally retries once with explicit reinforcement if the response is
    not valid JSON."""
    last_exc: Exception | None = None
    reinforcement = (
        "Your previous response was not valid JSON. "
        "Output ONLY a JSON object matching the schema. No prose, no markdown fences."
    )
    for attempt in range(retries + 1):
        effective_prompt = prompt if attempt == 0 else f"{prompt}\n\n{reinforcement}"
        resp = provider.call(
            effective_prompt, system=system, json_schema=schema, timeout_sec=timeout_sec,
        )
        text = resp.text.strip()
        # Strip leading/trailing markdown fences if the model added them
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            last_exc = exc
    assert last_exc is not None  # for type checkers
    raise LLMError(f"provider returned non-JSON after {retries + 1} attempts: {last_exc}")
