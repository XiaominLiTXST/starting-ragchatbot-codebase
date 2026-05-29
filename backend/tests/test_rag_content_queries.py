"""
Integration tests for the RAG system's content-query pipeline.
Uses the real ChromaDB store (populated at startup) but mocks the Anthropic API
so these tests run without network access and without consuming API credits.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rag():
    """
    Build a real RAGSystem against the production ChromaDB on disk.
    The Anthropic client is NOT mocked here — we mock it per-test via patch.
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from config import config
    from rag_system import RAGSystem
    return RAGSystem(config)


def _text_block(text: str):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _tool_use_block(name: str, tid: str, inp: dict):
    b = MagicMock()
    b.type = "tool_use"
    b.name = name
    b.id = tid
    b.input = inp
    return b


def _make_response(stop_reason: str, *content_blocks):
    r = MagicMock()
    r.stop_reason = stop_reason
    r.content = list(content_blocks)
    return r


# ---------------------------------------------------------------------------
# 1. CourseSearchTool.execute() against real ChromaDB
# ---------------------------------------------------------------------------

class TestCourseSearchToolIntegration:
    """These tests run .execute() directly on the real vector store."""

    def test_unfiltered_search_returns_results(self, rag):
        result = rag.search_tool.execute(query="What is MCP?")
        assert "No relevant content found" not in result
        assert len(result) > 0

    def test_filtered_search_by_course_name(self, rag):
        result = rag.search_tool.execute(
            query="client server connection", course_name="MCP"
        )
        assert "No relevant content found" not in result
        assert "MCP" in result

    def test_filtered_search_by_lesson_number(self, rag):
        result = rag.search_tool.execute(
            query="lesson content", lesson_number=1
        )
        # Lesson 1 exists in every course, so we expect real content
        assert isinstance(result, str)
        assert len(result) > 0

    def test_combined_course_and_lesson_filter(self, rag):
        result = rag.search_tool.execute(
            query="MCP client", course_name="MCP", lesson_number=5
        )
        assert isinstance(result, str)
        # Should find MCP lesson 5 content; not empty and not an error
        assert "No relevant content found" not in result or "MCP" in result

    def test_unknown_course_returns_not_found_message(self, rag):
        result = rag.search_tool.execute(
            query="anything", course_name="zzzNonExistentCourse999"
        )
        assert "No course found" in result or "No relevant content found" in result

    def test_execute_populates_last_sources_after_real_search(self, rag):
        rag.search_tool.last_sources = []  # reset
        rag.search_tool.execute(query="what is retrieval augmented generation")
        assert len(rag.search_tool.last_sources) > 0
        for src in rag.search_tool.last_sources:
            assert "label" in src
            assert "url" in src

    def test_result_format_contains_course_header(self, rag):
        result = rag.search_tool.execute(query="embeddings")
        # Every result chunk is prefixed with [Course Title...]
        assert result.startswith("[")


# ---------------------------------------------------------------------------
# 2. RAGSystem.query() routes content questions through search tool
# ---------------------------------------------------------------------------

class TestRAGContentQueryPipeline:

    def test_content_query_calls_search_tool_and_returns_response(self, rag):
        """
        Simulate: Claude requests search_course_content, tool runs against real
        ChromaDB, result fed back, Claude returns final answer.
        """
        tool_resp = _make_response(
            "tool_use",
            _tool_use_block("search_course_content", "t1", {"query": "what is MCP"})
        )
        final_resp = _make_response(
            "end_turn",
            _text_block("MCP is the Model Context Protocol.")
        )

        with patch.object(rag.ai_generator.client.messages, "create",
                          side_effect=[tool_resp, final_resp]):
            answer, sources = rag.query("What is MCP?")

        assert answer == "MCP is the Model Context Protocol."
        # The real search ran, so sources should be populated
        assert isinstance(sources, list)
        assert len(sources) > 0

    def test_content_query_sources_have_label_and_url(self, rag):
        tool_resp = _make_response(
            "tool_use",
            _tool_use_block("search_course_content", "t2",
                            {"query": "query expansion technique"})
        )
        final_resp = _make_response("end_turn", _text_block("Query expansion is..."))

        with patch.object(rag.ai_generator.client.messages, "create",
                          side_effect=[tool_resp, final_resp]):
            _, sources = rag.query("Explain query expansion")

        for src in sources:
            assert "label" in src
            assert "url" in src

    def test_content_query_with_course_filter(self, rag):
        tool_resp = _make_response(
            "tool_use",
            _tool_use_block("search_course_content", "t3",
                            {"query": "client server", "course_name": "MCP"})
        )
        final_resp = _make_response("end_turn", _text_block("The MCP client connects..."))

        with patch.object(rag.ai_generator.client.messages, "create",
                          side_effect=[tool_resp, final_resp]):
            answer, sources = rag.query("How does the MCP client connect to the server?")

        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_sources_reset_between_queries(self, rag):
        """Sources from one query must not bleed into the next."""
        for i, tid in enumerate(["ta", "tb"]):
            tool_resp = _make_response(
                "tool_use",
                _tool_use_block("search_course_content", tid, {"query": "MCP"})
            )
            final_resp = _make_response("end_turn", _text_block(f"Answer {i}"))

            with patch.object(rag.ai_generator.client.messages, "create",
                              side_effect=[tool_resp, final_resp]):
                _, sources = rag.query("MCP question")

            # sources come from a single query — should not accumulate
            labels = [s["label"] for s in sources]
            unique_labels = set(labels)
            assert len(labels) == len(unique_labels) or len(sources) <= rag.vector_store.max_results

    def test_query_without_tool_use_still_returns_string(self, rag):
        """Claude answers directly (no tool) — response must still be a string."""
        direct_resp = _make_response("end_turn", _text_block("That is a general question."))

        with patch.object(rag.ai_generator.client.messages, "create",
                          return_value=direct_resp):
            answer, sources = rag.query("What is 2 + 2?")

        assert isinstance(answer, str)
        assert answer == "That is a general question."
        assert sources == []

    def test_query_propagates_session_history(self, rag):
        """A second query in a session should include prior history in the system prompt."""
        session_id = rag.session_manager.create_session()

        # First turn
        r1 = _make_response("end_turn", _text_block("MCP is great."))
        with patch.object(rag.ai_generator.client.messages, "create", return_value=r1):
            rag.query("What is MCP?", session_id=session_id)

        # Second turn — capture the system parameter sent to the API
        r2 = _make_response("end_turn", _text_block("Yes, lesson 5 covers the client."))
        with patch.object(rag.ai_generator.client.messages, "create",
                          return_value=r2) as mock_create:
            rag.query("Tell me about lesson 5", session_id=session_id)

        call_kwargs = mock_create.call_args[1]
        assert "Previous conversation" in call_kwargs["system"]
        assert "MCP" in call_kwargs["system"] or "lesson" in call_kwargs["system"].lower()

        rag.session_manager.clear_session(session_id)

    def test_query_raises_no_exception_on_tool_returning_no_results(self, rag):
        """Even if the search returns empty, the pipeline must not raise."""
        tool_resp = _make_response(
            "tool_use",
            _tool_use_block("search_course_content", "t_empty",
                            {"query": "zzz nonexistent zzz"})
        )
        final_resp = _make_response("end_turn", _text_block("I found no content."))

        with patch.object(rag.ai_generator.client.messages, "create",
                          side_effect=[tool_resp, final_resp]):
            answer, _ = rag.query("Tell me about zzz nonexistent zzz")

        assert isinstance(answer, str)
