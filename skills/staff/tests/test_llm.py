#!/usr/bin/env python3
"""Tests for the LLM provider abstraction.

Mocks subprocess (codex/claude) and urllib (openai-compatible) so tests don't
hit a real LLM. Real-LLM coverage is exercised by eval_suggest_accuracy.py.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "skills/staff/scripts"))
import _llm  # type: ignore  # noqa: E402


class TestGetProvider(unittest.TestCase):
    def test_default_is_codex(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STAFF_LLM", None)
            p = _llm.get_provider()
            self.assertEqual(p.name, "codex-cli")

    def test_codex_alias(self) -> None:
        for v in ("codex", "codex-cli", "CODEX"):
            with patch.dict(os.environ, {"STAFF_LLM": v}):
                self.assertEqual(_llm.get_provider().name, "codex-cli")

    def test_claude_alias(self) -> None:
        for v in ("claude", "claude-cli"):
            with patch.dict(os.environ, {"STAFF_LLM": v}):
                self.assertEqual(_llm.get_provider().name, "claude-cli")

    def test_local_requires_url_and_model(self) -> None:
        with patch.dict(os.environ, {"STAFF_LLM": "local"}):
            os.environ.pop("STAFF_LLM_URL", None)
            os.environ.pop("STAFF_LLM_MODEL", None)
            with self.assertRaises(_llm.LLMError):
                _llm.get_provider()

    def test_local_constructs_with_url_and_model(self) -> None:
        with patch.dict(os.environ, {
            "STAFF_LLM": "local",
            "STAFF_LLM_URL": "http://localhost:11434/v1",
            "STAFF_LLM_MODEL": "qwen2.5",
        }):
            p = _llm.get_provider()
            self.assertEqual(p.name, "openai-compatible")

    def test_unknown_provider_raises(self) -> None:
        with patch.dict(os.environ, {"STAFF_LLM": "garbage"}):
            with self.assertRaises(_llm.LLMError):
                _llm.get_provider()

    def test_override_wins(self) -> None:
        with patch.dict(os.environ, {"STAFF_LLM": "codex"}):
            self.assertEqual(_llm.get_provider("claude").name, "claude-cli")


class TestCodexCLIProvider(unittest.TestCase):
    def test_missing_codex_binary_raises(self) -> None:
        p = _llm.CodexCLIProvider()
        with patch("_llm.shutil.which", return_value=None):
            with self.assertRaises(_llm.LLMError) as cm:
                p.call("hello")
            self.assertIn("codex", str(cm.exception).lower())

    def test_codex_writes_output_to_last_message_file(self) -> None:
        p = _llm.CodexCLIProvider()

        def fake_run(cmd, **kwargs):  # type: ignore
            # Find the --output-last-message arg and write to it
            idx = cmd.index("--output-last-message")
            Path(cmd[idx + 1]).write_text("hi", encoding="utf-8")
            return MagicMock(returncode=0, stderr="", stdout="")

        with patch("_llm.shutil.which", return_value="/usr/bin/codex"), \
             patch("_llm.subprocess.run", side_effect=fake_run):
            resp = p.call("test")
        self.assertEqual(resp.text, "hi")
        self.assertEqual(resp.provider, "codex-cli")

    def test_codex_nonzero_exit_raises(self) -> None:
        p = _llm.CodexCLIProvider()
        with patch("_llm.shutil.which", return_value="/usr/bin/codex"), \
             patch("_llm.subprocess.run",
                   return_value=MagicMock(returncode=1, stderr="boom", stdout="")):
            with self.assertRaises(_llm.LLMError) as cm:
                p.call("x")
            self.assertIn("exited 1", str(cm.exception))

    def test_codex_empty_output_raises(self) -> None:
        p = _llm.CodexCLIProvider()

        def fake_run(cmd, **kwargs):  # type: ignore
            idx = cmd.index("--output-last-message")
            Path(cmd[idx + 1]).write_text("", encoding="utf-8")
            return MagicMock(returncode=0, stderr="", stdout="")

        with patch("_llm.shutil.which", return_value="/usr/bin/codex"), \
             patch("_llm.subprocess.run", side_effect=fake_run):
            with self.assertRaises(_llm.LLMError) as cm:
                p.call("x")
            self.assertIn("empty", str(cm.exception).lower())

    def test_codex_timeout_raises(self) -> None:
        p = _llm.CodexCLIProvider()
        with patch("_llm.shutil.which", return_value="/usr/bin/codex"), \
             patch("_llm.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("codex", 30)):
            with self.assertRaises(_llm.LLMError) as cm:
                p.call("x", timeout_sec=30)
            self.assertIn("timed out", str(cm.exception).lower())

    def test_codex_with_schema_writes_schema_file(self) -> None:
        p = _llm.CodexCLIProvider()
        captured: dict = {}

        def fake_run(cmd, **kwargs):  # type: ignore
            idx = cmd.index("--output-last-message")
            Path(cmd[idx + 1]).write_text('{"k":"v"}', encoding="utf-8")
            if "--output-schema" in cmd:
                captured["schema_path"] = cmd[cmd.index("--output-schema") + 1]
                captured["schema_content"] = Path(captured["schema_path"]).read_text()
            return MagicMock(returncode=0, stderr="", stdout="")

        schema = {"type": "object", "properties": {"k": {"type": "string"}}}
        with patch("_llm.shutil.which", return_value="/usr/bin/codex"), \
             patch("_llm.subprocess.run", side_effect=fake_run):
            p.call("x", json_schema=schema)
        self.assertIn("schema_content", captured)
        self.assertEqual(json.loads(captured["schema_content"]), schema)


class TestClaudeCLIProvider(unittest.TestCase):
    def test_missing_claude_binary_raises(self) -> None:
        p = _llm.ClaudeCLIProvider()
        with patch("_llm.shutil.which", return_value=None):
            with self.assertRaises(_llm.LLMError):
                p.call("x")

    def test_claude_parses_json_result(self) -> None:
        p = _llm.ClaudeCLIProvider()
        payload = {"result": "the answer", "model": "claude-opus-4-7"}
        with patch("_llm.shutil.which", return_value="/usr/bin/claude"), \
             patch("_llm.subprocess.run",
                   return_value=MagicMock(returncode=0,
                                          stdout=json.dumps(payload),
                                          stderr="")):
            resp = p.call("x")
        self.assertEqual(resp.text, "the answer")
        self.assertEqual(resp.model, "claude-opus-4-7")

    def test_claude_non_json_output_raises(self) -> None:
        p = _llm.ClaudeCLIProvider()
        with patch("_llm.shutil.which", return_value="/usr/bin/claude"), \
             patch("_llm.subprocess.run",
                   return_value=MagicMock(returncode=0,
                                          stdout="not json",
                                          stderr="")):
            with self.assertRaises(_llm.LLMError):
                p.call("x")

    def test_claude_empty_result_raises(self) -> None:
        p = _llm.ClaudeCLIProvider()
        with patch("_llm.shutil.which", return_value="/usr/bin/claude"), \
             patch("_llm.subprocess.run",
                   return_value=MagicMock(returncode=0,
                                          stdout=json.dumps({"result": ""}),
                                          stderr="")):
            with self.assertRaises(_llm.LLMError):
                p.call("x")

    def test_claude_nonzero_exit_raises(self) -> None:
        p = _llm.ClaudeCLIProvider()
        with patch("_llm.shutil.which", return_value="/usr/bin/claude"), \
             patch("_llm.subprocess.run",
                   return_value=MagicMock(returncode=2, stdout="", stderr="oops")):
            with self.assertRaises(_llm.LLMError):
                p.call("x")


class TestOpenAICompatibleProvider(unittest.TestCase):
    def test_call_posts_to_chat_completions(self) -> None:
        p = _llm.OpenAICompatibleProvider("http://localhost:8080/v1", "qwen", api_key="sk-test")
        sent: dict = {}
        body = json.dumps({
            "choices": [{"message": {"content": "hello back"}}],
        }).encode("utf-8")

        def fake_urlopen(req, timeout):  # type: ignore
            sent["url"] = req.full_url
            sent["headers"] = dict(req.header_items())
            sent["body"] = json.loads(req.data.decode("utf-8"))
            return io.BytesIO(body)

        with patch("_llm.urllib.request.urlopen", side_effect=fake_urlopen):
            resp = p.call("greetings", system="be terse")
        self.assertEqual(resp.text, "hello back")
        self.assertEqual(sent["url"], "http://localhost:8080/v1/chat/completions")
        self.assertEqual(sent["body"]["model"], "qwen")
        self.assertEqual(sent["body"]["messages"][0]["role"], "system")
        self.assertEqual(sent["body"]["messages"][1]["content"], "greetings")
        self.assertIn("Bearer sk-test", sent["headers"].get("Authorization", ""))

    def test_call_no_choices_raises(self) -> None:
        p = _llm.OpenAICompatibleProvider("http://x/v1", "m")
        body = json.dumps({"choices": []}).encode("utf-8")
        with patch("_llm.urllib.request.urlopen", return_value=io.BytesIO(body)):
            with self.assertRaises(_llm.LLMError):
                p.call("x")

    def test_call_http_error_raises(self) -> None:
        import urllib.error
        p = _llm.OpenAICompatibleProvider("http://x/v1", "m")
        with patch("_llm.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("connection refused")):
            with self.assertRaises(_llm.LLMError):
                p.call("x")

    def test_call_with_json_schema_includes_response_format(self) -> None:
        p = _llm.OpenAICompatibleProvider("http://x/v1", "m")
        sent: dict = {}
        body = json.dumps({
            "choices": [{"message": {"content": '{"k": "v"}'}}],
        }).encode("utf-8")

        def fake_urlopen(req, timeout):  # type: ignore
            sent["body"] = json.loads(req.data.decode("utf-8"))
            return io.BytesIO(body)

        schema = {"type": "object", "properties": {"k": {"type": "string"}}}
        with patch("_llm.urllib.request.urlopen", side_effect=fake_urlopen):
            p.call("x", json_schema=schema)
        self.assertEqual(sent["body"]["response_format"]["type"], "json_schema")
        self.assertEqual(sent["body"]["response_format"]["json_schema"]["schema"], schema)


class TestCallWithJson(unittest.TestCase):
    def _make_provider_returning(self, text: str) -> _llm.LLMProvider:
        provider = MagicMock(spec=_llm.LLMProvider)
        provider.name = "fake"
        provider.call.return_value = _llm.LLMResponse(text=text, provider="fake")
        return provider

    def test_call_with_json_parses_clean_object(self) -> None:
        p = self._make_provider_returning('{"reply": "hi"}')
        result = _llm.call_with_json(p, "x", {"type": "object"})
        self.assertEqual(result, {"reply": "hi"})

    def test_call_with_json_strips_markdown_fences(self) -> None:
        p = self._make_provider_returning('```json\n{"k": 1}\n```')
        result = _llm.call_with_json(p, "x", {"type": "object"})
        self.assertEqual(result, {"k": 1})

    def test_call_with_json_retries_on_bad_output(self) -> None:
        provider = MagicMock(spec=_llm.LLMProvider)
        provider.name = "fake"
        provider.call.side_effect = [
            _llm.LLMResponse(text="not json", provider="fake"),
            _llm.LLMResponse(text='{"k": 1}', provider="fake"),
        ]
        result = _llm.call_with_json(provider, "x", {"type": "object"}, retries=1)
        self.assertEqual(result, {"k": 1})
        self.assertEqual(provider.call.call_count, 2)

    def test_call_with_json_raises_after_retries(self) -> None:
        p = self._make_provider_returning("still not json")
        with self.assertRaises(_llm.LLMError):
            _llm.call_with_json(p, "x", {"type": "object"}, retries=1)


class TestSuggestLLMPath(unittest.TestCase):
    """In-process tests for suggest.py's LLM-mode functions. Coverage for
    build_llm_prompt + llm_proposals — the subprocess-based test_suggest.py
    only exercises --no-llm (deterministic) by design."""

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(REPO_ROOT / "skills/staff/scripts"))
        import suggest  # noqa: E402
        cls.suggest = suggest

    def _fake_manifest(self) -> dict:
        return {
            "agents": {
                "alpha": {
                    "file": "engineering/alpha.md",
                    "category": "engineering",
                    "description": "alpha description",
                    "description_summary": "alpha is for alpha tasks",
                    "project_hints": {"files": [], "regex": []},
                },
                "beta": {
                    "file": "engineering/beta.md",
                    "category": "engineering",
                    "description": "beta description",
                    "description_summary": "",  # falls back to description prefix
                    "project_hints": {"files": [], "regex": []},
                },
            }
        }

    def test_build_prompt_summary_strategy(self) -> None:
        m = self._fake_manifest()
        prompt = self.suggest.build_llm_prompt(
            project_root=Path("/tmp/proj"),
            manifest=m,
            deterministic_proposals=[],
            doc_files={"README.md": "Hello world"},
            strategy="summary",
        )
        self.assertIn("alpha is for alpha tasks", prompt)
        self.assertIn("beta description", prompt)  # fallback when no summary
        self.assertIn("Hello world", prompt)

    def test_build_prompt_full_strategy_uses_full_descriptions(self) -> None:
        m = self._fake_manifest()
        prompt = self.suggest.build_llm_prompt(
            project_root=Path("/tmp/proj"),
            manifest=m,
            deterministic_proposals=[],
            doc_files={},
            strategy="full",
        )
        # "full" path should include the full description, not the summary
        self.assertIn("alpha description", prompt)
        self.assertIn("(no CLAUDE.md / README / AGENTS.md present)", prompt)

    def test_llm_proposals_filters_unknown_ids(self) -> None:
        m = self._fake_manifest()
        provider = MagicMock(spec=_llm.LLMProvider)
        provider.name = "fake"
        provider.call.return_value = _llm.LLMResponse(
            text=json.dumps({
                "suggested": [
                    {"id": "alpha", "reason": "fits"},
                    {"id": "ghost", "reason": "doesn't exist in manifest"},
                ]
            }),
            provider="fake",
        )
        out = self.suggest.llm_proposals(
            project_root=Path("/tmp"),
            manifest=m,
            deterministic_proposals=[],
            provider=provider,
        )
        ids = [p["id"] for p in out]
        self.assertEqual(ids, ["alpha"])
        self.assertEqual(out[0]["source"], "llm")
        self.assertTrue(any("fits" in r for r in out[0]["reasons"]))

    def test_llm_proposals_merges_with_deterministic(self) -> None:
        m = self._fake_manifest()
        det = [{
            "id": "alpha",
            "category": "engineering",
            "matches": [{"type": "file", "pattern": "alpha.toml", "paths": ["alpha.toml"]}],
            "reasons": ["file: alpha.toml → alpha.toml"],
        }]
        provider = MagicMock(spec=_llm.LLMProvider)
        provider.name = "fake"
        provider.call.return_value = _llm.LLMResponse(
            text=json.dumps({"suggested": [{"id": "alpha", "reason": "regex confirms"}]}),
            provider="fake",
        )
        out = self.suggest.llm_proposals(
            project_root=Path("/tmp"), manifest=m,
            deterministic_proposals=det, provider=provider,
        )
        self.assertEqual(out[0]["source"], "llm+deterministic")
        # deterministic reason preserved + LLM reason appended
        self.assertEqual(len(out[0]["matches"]), 1)
        self.assertTrue(any("file: alpha.toml" in r for r in out[0]["reasons"]))
        self.assertTrue(any("llm: regex confirms" in r for r in out[0]["reasons"]))

    def test_llm_proposals_dedups_repeated_ids(self) -> None:
        m = self._fake_manifest()
        provider = MagicMock(spec=_llm.LLMProvider)
        provider.name = "fake"
        provider.call.return_value = _llm.LLMResponse(
            text=json.dumps({
                "suggested": [
                    {"id": "alpha", "reason": "first"},
                    {"id": "alpha", "reason": "duplicate"},
                ]
            }),
            provider="fake",
        )
        out = self.suggest.llm_proposals(
            project_root=Path("/tmp"), manifest=m,
            deterministic_proposals=[], provider=provider,
        )
        self.assertEqual(len(out), 1)

    def test_doc_excerpts_caps_size(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            big_text = "x" * 100_000
            (tmp / "README.md").write_text(big_text)
            excerpts = self.suggest.doc_excerpts(tmp)
            self.assertIn("README.md", excerpts)
            self.assertLessEqual(len(excerpts["README.md"]), self.suggest.DOC_EXCERPT_BYTES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
