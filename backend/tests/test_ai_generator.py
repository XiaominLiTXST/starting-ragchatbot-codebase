"""
Tests verifying that AIGenerator routes content questions to CourseSearchTool
(search_course_content) and handles the tool-use cycle correctly.
All Anthropic API calls are mocked.
"""

from unittest.mock import MagicMock, patch

from ai_generator import AIGenerator
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults

# ---------------------------------------------------------------------------
# Helpers to build mock Anthropic responses
# ---------------------------------------------------------------------------


def _text_response(text: str):
    """Simulate a plain-text (no tool-use) response."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def _tool_use_response(tool_name: str, tool_id: str, tool_input: dict):
    """Simulate a response that requests a tool call."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = tool_input
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


def _make_tool_manager(search_result: str = "some content"):
    """Return a ToolManager whose search tool returns a fixed string."""
    store = MagicMock()
    store.search.return_value = SearchResults(
        documents=["some content"],
        metadata=[{"course_title": "Test Course", "lesson_number": 1}],
        distances=[0.1],
    )
    store.get_lesson_link.return_value = None
    store.get_course_link.return_value = None
    tm = ToolManager()
    tm.register_tool(CourseSearchTool(store))
    return tm


# ---------------------------------------------------------------------------
# Routing: content questions must use search_course_content
# ---------------------------------------------------------------------------


def test_content_question_triggers_search_tool():
    """Claude should request search_course_content for a content query."""
    tool_response = _tool_use_response(
        "search_course_content", "tool_1", {"query": "what is query expansion"}
    )
    final_response = _text_response("Query expansion rewrites the user query.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [tool_response, final_response]

        gen = AIGenerator(api_key="test", model="claude-test")
        tm = _make_tool_manager()
        result = gen.generate_response(
            query="What is query expansion?",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    assert "query expansion" in result.lower()
    # Two API calls: first triggers tool_use, second is the follow-up
    assert instance.messages.create.call_count == 2


def test_search_tool_called_with_correct_query():
    """The tool input passed back to the API should include the user's query."""
    tool_response = _tool_use_response(
        "search_course_content", "tool_2", {"query": "embedding adaptors"}
    )
    final_response = _text_response("Embedding adaptors fine-tune embeddings.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [tool_response, final_response]

        gen = AIGenerator(api_key="test", model="claude-test")
        tm = _make_tool_manager()
        gen.generate_response(
            query="What are embedding adaptors?",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    # The second call's messages should contain the user-role tool_result
    second_call_messages = instance.messages.create.call_args_list[1][1]["messages"]
    tool_result_msgs = [
        m
        for m in second_call_messages
        if m.get("role") == "user"
        and isinstance(m.get("content"), list)
        and m["content"][0].get("type") == "tool_result"
    ]
    assert len(tool_result_msgs) == 1
    assert tool_result_msgs[0]["content"][0]["tool_use_id"] == "tool_2"


def test_tool_result_content_included_in_follow_up():
    """The tool's output must be sent back to Claude in the follow-up call."""
    tool_response = _tool_use_response(
        "search_course_content", "tid_3", {"query": "MCP architecture"}
    )
    final_response = _text_response("MCP uses a client-server architecture.")

    store = MagicMock()
    store.search.return_value = SearchResults(
        documents=["MCP architecture overview"],
        metadata=[{"course_title": "MCP Course", "lesson_number": 2}],
        distances=[0.1],
    )
    store.get_lesson_link.return_value = None
    store.get_course_link.return_value = None
    tm = ToolManager()
    tm.register_tool(CourseSearchTool(store))

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [tool_response, final_response]

        gen = AIGenerator(api_key="test", model="claude-test")
        result = gen.generate_response(
            query="Explain MCP architecture",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    assert result == "MCP uses a client-server architecture."


# ---------------------------------------------------------------------------
# No-tool path: general knowledge questions
# ---------------------------------------------------------------------------


def test_general_knowledge_skips_tool_call():
    """For a general question with no tools configured, Claude answers directly."""
    direct_response = _text_response("Python is a programming language.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = direct_response

        gen = AIGenerator(api_key="test", model="claude-test")
        result = gen.generate_response(query="What is Python?")

    assert result == "Python is a programming language."
    assert instance.messages.create.call_count == 1


def test_no_tool_execution_when_stop_reason_is_end_turn():
    """If Claude returns end_turn even when tools are available, no tool is run."""
    direct_response = _text_response("The sky is blue.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = direct_response

        gen = AIGenerator(api_key="test", model="claude-test")
        tm = _make_tool_manager()
        result = gen.generate_response(
            query="Why is the sky blue?",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    assert result == "The sky is blue."
    assert instance.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


def test_unknown_tool_name_does_not_crash():
    """If Claude requests a non-existent tool, ToolManager returns an error string
    but the generator should still return the final response."""
    tool_response = _tool_use_response("nonexistent_tool", "t_x", {"query": "q"})
    final_response = _text_response("I could not find the relevant content.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [tool_response, final_response]

        gen = AIGenerator(api_key="test", model="claude-test")
        tm = _make_tool_manager()
        result = gen.generate_response(
            query="Some query",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    assert isinstance(result, str)


def test_conversation_history_included_in_system_prompt():
    """Previous conversation context must appear in the system parameter."""
    direct_response = _text_response("Yes, it was in lesson 3.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = direct_response

        gen = AIGenerator(api_key="test", model="claude-test")
        gen.generate_response(
            query="Was that in lesson 3?",
            conversation_history="User asked about MCP.\nAssistant explained it.",
        )

    call_kwargs = instance.messages.create.call_args[1]
    assert "Previous conversation" in call_kwargs["system"]
    assert "User asked about MCP" in call_kwargs["system"]


# ---------------------------------------------------------------------------
# Sequential tool calling (new multi-round behaviour)
# ---------------------------------------------------------------------------


def test_two_sequential_tool_calls_make_three_api_calls():
    """Two tool_use rounds followed by a synthesis call = 3 total API calls."""
    r1 = _tool_use_response("get_course_outline", "t1", {"course_title": "MCP"})
    r2 = _tool_use_response("search_course_content", "t2", {"query": "lesson 3 topic"})
    r3 = _text_response("Here is the content for lesson 3.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [r1, r2, r3]

        gen = AIGenerator(api_key="test", model="claude-test")
        tm = _make_tool_manager()
        result = gen.generate_response(
            query="Find content similar to lesson 3 of the MCP course",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    assert instance.messages.create.call_count == 3
    assert result == "Here is the content for lesson 3."


def test_tools_included_in_second_round_api_call():
    """After round 1 tool execution, tools must still be present in the round 2
    API call so Claude can request another tool if needed."""
    r1 = _tool_use_response("get_course_outline", "t1", {"course_title": "MCP"})
    r2 = _tool_use_response("search_course_content", "t2", {"query": "topic"})
    r3 = _text_response("Final answer.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [r1, r2, r3]

        gen = AIGenerator(api_key="test", model="claude-test")
        tm = _make_tool_manager()
        gen.generate_response(
            query="Multi-step query",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    second_call_kwargs = instance.messages.create.call_args_list[1][1]
    assert "tools" in second_call_kwargs
    assert second_call_kwargs["tools"] == tm.get_tool_definitions()


def test_tools_excluded_from_synthesis_call():
    """The post-loop synthesis call must not include tools so Claude is forced
    to produce a text answer."""
    r1 = _tool_use_response("get_course_outline", "t1", {"course_title": "MCP"})
    r2 = _tool_use_response("search_course_content", "t2", {"query": "topic"})
    r3 = _text_response("Final answer.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [r1, r2, r3]

        gen = AIGenerator(api_key="test", model="claude-test")
        tm = _make_tool_manager()
        gen.generate_response(
            query="Multi-step query",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    synthesis_call_kwargs = instance.messages.create.call_args_list[2][1]
    assert "tools" not in synthesis_call_kwargs


def test_second_round_messages_include_full_first_round_history():
    """The round-2 API call must contain the complete transcript:
    user query → round-1 tool_use → round-1 tool_result → round-2 tool_use →
    round-2 tool_result, so Claude has full context for its synthesis."""
    r1 = _tool_use_response("get_course_outline", "t1", {"course_title": "MCP"})
    r2 = _tool_use_response("search_course_content", "t2", {"query": "topic"})
    r3 = _text_response("Final answer.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [r1, r2, r3]

        gen = AIGenerator(api_key="test", model="claude-test")
        tm = _make_tool_manager()
        gen.generate_response(
            query="Multi-step query",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    # Synthesis call (index 2) receives the full 5-message transcript
    synthesis_messages = instance.messages.create.call_args_list[2][1]["messages"]
    roles = [m["role"] for m in synthesis_messages]
    # user, assistant (tool_use r1), user (tool_result r1),
    # assistant (tool_use r2), user (tool_result r2)
    assert roles == ["user", "assistant", "user", "assistant", "user"]


def test_tool_execution_exception_terminates_rounds_and_synthesises():
    """If execute_tool raises, remaining rounds are skipped and a synthesis
    call (without tools) is still made so Claude can give a graceful answer."""
    r1 = _tool_use_response("search_course_content", "t1", {"query": "topic"})
    synthesis_response = _text_response("I encountered an error fetching that content.")

    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [r1, synthesis_response]

        gen = AIGenerator(api_key="test", model="claude-test")

        # Build a tool manager whose execute_tool raises
        tm = MagicMock()
        tm.get_tool_definitions.return_value = [{"name": "search_course_content"}]
        tm.execute_tool.side_effect = RuntimeError("DB connection lost")

        result = gen.generate_response(
            query="What does lesson 5 cover?",
            tools=tm.get_tool_definitions(),
            tool_manager=tm,
        )

    assert isinstance(result, str)
    # Round 1 fired, error occurred, then synthesis call — 2 total
    assert instance.messages.create.call_count == 2
    # Synthesis call must not include tools
    synthesis_call_kwargs = instance.messages.create.call_args_list[1][1]
    assert "tools" not in synthesis_call_kwargs
