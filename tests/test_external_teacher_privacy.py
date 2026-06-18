import asyncio

from src.external_privacy import redact_text_for_external_model
from src import ai_interaction
from src import llm_core


def test_external_redactor_masks_common_secret_and_pii_values():
    text = (
        "Email alice@example.com, SSN 123-45-6789, "
        "OPENAI_API_KEY=sk-abc123abc123abc123abc123, "
        "Authorization: Bearer nvapi-secretsecretsecretsecret, "
        "card 4242 4242 4242 4242."
    )

    report = redact_text_for_external_model(text)

    assert "alice@example.com" not in report.text
    assert "123-45-6789" not in report.text
    assert "sk-abc123abc123abc123abc123" not in report.text
    assert "nvapi-secretsecretsecretsecret" not in report.text
    assert "4242 4242 4242 4242" not in report.text
    assert report.count >= 5


def test_ask_teacher_sends_redacted_prompt_to_external_model(monkeypatch):
    seen = {}

    def fake_resolve_model(spec, owner=None):
        return "https://integrate.api.nvidia.com/v1/chat/completions", "nvidia/test", {}

    async def fake_llm_call(url, model, messages, **kwargs):
        seen["messages"] = messages
        return "Use placeholders and keep the structure."

    monkeypatch.setattr(ai_interaction, "_resolve_model", fake_resolve_model)
    monkeypatch.setattr(llm_core, "llm_call_async", fake_llm_call)

    result = asyncio.run(ai_interaction.do_ask_teacher(
        "nvidia/test\nFill the form for alice@example.com with password=hunter2secret and SSN 123-45-6789",
        owner="alice",
    ))

    outbound = seen["messages"][1]["content"]
    assert "alice@example.com" not in outbound
    assert "hunter2secret" not in outbound
    assert "123-45-6789" not in outbound
    assert "[REDACTED_EMAIL_1]" in outbound
    assert result["teacher_exchange"]["redaction_count"] >= 3
    assert result["response"] == "Use placeholders and keep the structure."


def test_chat_with_model_redacts_external_prompt(monkeypatch):
    seen = {}

    def fake_resolve_model(spec, owner=None):
        return "https://integrate.api.nvidia.com/v1/chat/completions", "nvidia/test", {}

    async def fake_llm_call(url, model, messages, **kwargs):
        seen["messages"] = messages
        return "Safe response"

    monkeypatch.setattr(ai_interaction, "_resolve_model", fake_resolve_model)
    monkeypatch.setattr(llm_core, "llm_call_async", fake_llm_call)

    result = asyncio.run(ai_interaction.do_chat_with_model(
        "nvidia/test\nImprove signup copy for alice@example.com using api_key=sk-abc123abc123abc123abc123",
        owner="alice",
    ))

    outbound = seen["messages"][0]["content"]
    assert "alice@example.com" not in outbound
    assert "sk-abc123abc123abc123abc123" not in outbound
    assert "[REDACTED_EMAIL_1]" in outbound
    assert result["privacy_redaction_count"] >= 2


def test_pipeline_redacts_local_output_before_external_step(monkeypatch):
    calls = []

    def fake_resolve_model(spec, owner=None):
        if spec == "local/test":
            return "http://127.0.0.1:11434/v1/chat/completions", "local/test", {}
        return "https://integrate.api.nvidia.com/v1/chat/completions", "nvidia/test", {}

    async def fake_llm_call(url, model, messages, **kwargs):
        calls.append({"model": model, "messages": messages})
        if model == "local/test":
            return "Draft uses password=hunter2secret and contact alice@example.com."
        return "Reviewed safely."

    monkeypatch.setattr(ai_interaction, "_resolve_model", fake_resolve_model)
    monkeypatch.setattr(llm_core, "llm_call_async", fake_llm_call)

    result = asyncio.run(ai_interaction.do_pipeline(
        "local/test | Draft the product workflow\n"
        "nvidia/test | Critique and strengthen it",
        owner="alice",
    ))

    external_messages = calls[1]["messages"]
    outbound = "\n\n".join(str(m.get("content", "")) for m in external_messages)
    assert "hunter2secret" not in outbound
    assert "alice@example.com" not in outbound
    assert "[REDACTED_SECRET_1]" in outbound
    assert "[REDACTED_EMAIL_1]" in outbound
    assert result["privacy_redaction_count"] >= 2
