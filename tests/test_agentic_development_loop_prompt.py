from src import agent_loop


def _prompt_text(messages, **kwargs):
    out, _ = agent_loop._build_system_prompt(
        messages=messages,
        model="test-model",
        active_document=None,
        mcp_mgr=None,
        relevant_tools=kwargs.pop("relevant_tools", {"bash", "read_file"}),
        **kwargs,
    )
    return "\n\n".join(m.get("content", "") or "" for m in out)


def test_development_loop_prompt_is_opt_in():
    normal = _prompt_text(
        [{"role": "user", "content": "What is a good lunch idea?"}],
        development_loop=False,
    )
    assert "Development loop contract" not in normal

    dev = _prompt_text(
        [{"role": "user", "content": "Build a trading app dashboard with Alpaca paper trading."}],
        development_loop=True,
    )
    assert "Development loop contract" in dev
    assert "local student model owns discovery" in dev
    assert "mark each subtask LOCAL or TEACHER" in dev
    assert "Ask the teacher only at high-leverage gates" in dev


def test_development_intent_detection_for_app_workspace_requests():
    assert agent_loop._detect_development_loop_intent([
        {
            "role": "user",
            "content": "Create an app workspace that displays generated dashboards and form fillers.",
        }
    ])
    assert agent_loop._detect_development_loop_intent([
        {
            "role": "user",
            "content": "Improve the agentic loop prompting for teacher loops and the student model.",
        }
    ])
    assert agent_loop._detect_development_loop_intent([
        {
            "role": "user",
            "content": "Plan and implement the auth cleanup using the student-teacher routing skill.",
        }
    ])
    assert not agent_loop._detect_development_loop_intent([
        {"role": "user", "content": "thanks, that helps"}
    ])


def test_auto_teacher_exchange_for_complex_development_not_simple_edits():
    assert agent_loop._should_auto_teacher_exchange(
        "Build an app dashboard with a secret manager, MCP integration, and security review."
    )
    assert not agent_loop._should_auto_teacher_exchange(
        "Build an app dashboard."
    )


def test_force_teacher_exchange_matches_development_loop_handoff_language():
    assert agent_loop._should_force_teacher_exchange(
        "Use the teacher/student development loop and show me the teacher handoff."
    )
    assert agent_loop._should_force_teacher_exchange(
        "Then ask the configured teacher model for review."
    )
    assert agent_loop._should_force_teacher_exchange(
        "Then ask the teacher to review the implementation checklist."
    )
    assert agent_loop._should_force_teacher_exchange(
        "Use the student-teacher routing skill for this implementation."
    )


def test_teacher_handoff_prompt_rehydrates_execution_contract():
    prompt = agent_loop._teacher_handoff_prompt(
        "Build a paper trading app with Alpaca credentials.",
        development_loop=True,
        forced=False,
    )
    assert "local student model will do implementation and verification" in prompt
    assert "Concrete checklist the student should execute next" in prompt
    assert "User goal:" in prompt
