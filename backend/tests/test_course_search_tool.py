"""
Tests for CourseSearchTool.execute() in search_tools.py.
All vector store interactions are mocked so no ChromaDB connection is needed.
"""

from unittest.mock import MagicMock

from search_tools import CourseSearchTool
from vector_store import SearchResults

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_store(documents=None, metadata=None, error=None):
    """Return a VectorStore mock whose search() returns controlled results."""
    store = MagicMock()
    results = SearchResults(
        documents=documents or [],
        metadata=metadata or [],
        distances=[0.1] * len(documents or []),
        error=error,
    )
    store.search.return_value = results
    store.get_lesson_link.return_value = "https://example.com/lesson"
    store.get_course_link.return_value = "https://example.com/course"
    return store


# ---------------------------------------------------------------------------
# Basic execution paths
# ---------------------------------------------------------------------------


def test_execute_returns_formatted_results():
    store = make_store(
        documents=["MCP stands for Model Context Protocol."],
        metadata=[{"course_title": "MCP Course", "lesson_number": 1}],
    )
    tool = CourseSearchTool(store)
    result = tool.execute(query="What is MCP?")

    assert "MCP Course" in result
    assert "Lesson 1" in result
    assert "MCP stands for Model Context Protocol." in result


def test_execute_returns_empty_message_when_no_results():
    store = make_store(documents=[], metadata=[])
    tool = CourseSearchTool(store)
    result = tool.execute(query="nonexistent topic")

    assert "No relevant content found" in result
    assert result.endswith(".")


def test_execute_returns_error_message_when_store_errors():
    store = make_store(error="ChromaDB connection failed")
    tool = CourseSearchTool(store)
    result = tool.execute(query="anything")

    assert "ChromaDB connection failed" in result


# ---------------------------------------------------------------------------
# Filter forwarding
# ---------------------------------------------------------------------------


def test_execute_passes_course_name_to_store():
    store = make_store(documents=[], metadata=[])
    tool = CourseSearchTool(store)
    tool.execute(query="embeddings", course_name="Chroma")

    store.search.assert_called_once_with(
        query="embeddings",
        course_name="Chroma",
        lesson_number=None,
    )


def test_execute_passes_lesson_number_to_store():
    store = make_store(documents=[], metadata=[])
    tool = CourseSearchTool(store)
    tool.execute(query="client", lesson_number=5)

    store.search.assert_called_once_with(
        query="client",
        course_name=None,
        lesson_number=5,
    )


def test_execute_passes_both_filters_to_store():
    store = make_store(documents=[], metadata=[])
    tool = CourseSearchTool(store)
    tool.execute(query="prompt", course_name="MCP", lesson_number=3)

    store.search.assert_called_once_with(
        query="prompt",
        course_name="MCP",
        lesson_number=3,
    )


def test_execute_empty_message_includes_course_filter_info():
    store = make_store(documents=[], metadata=[])
    tool = CourseSearchTool(store)
    result = tool.execute(query="something", course_name="MCP Course")

    assert "MCP Course" in result


def test_execute_empty_message_includes_lesson_filter_info():
    store = make_store(documents=[], metadata=[])
    tool = CourseSearchTool(store)
    result = tool.execute(query="something", lesson_number=7)

    assert "lesson 7" in result.lower() or "7" in result


# ---------------------------------------------------------------------------
# Source tracking
# ---------------------------------------------------------------------------


def test_execute_populates_last_sources_on_results():
    store = make_store(
        documents=["content here"],
        metadata=[{"course_title": "MCP Course", "lesson_number": 2}],
    )
    tool = CourseSearchTool(store)
    tool.execute(query="MCP client")

    assert len(tool.last_sources) == 1
    src = tool.last_sources[0]
    assert src["label"] == "MCP Course - Lesson 2"
    assert src["url"] is not None


def test_execute_last_sources_empty_on_no_results():
    store = make_store(documents=[], metadata=[])
    tool = CourseSearchTool(store)
    tool.execute(query="nothing")

    assert tool.last_sources == []


def test_execute_last_sources_empty_on_error():
    store = make_store(error="some error")
    tool = CourseSearchTool(store)
    tool.execute(query="fail")

    # sources should not be updated when there's an error
    assert tool.last_sources == []


def test_execute_last_sources_falls_back_to_course_link_when_no_lesson():
    store = make_store(
        documents=["content"],
        metadata=[{"course_title": "Chroma Course"}],  # no lesson_number key
    )
    store.get_lesson_link.return_value = None
    store.get_course_link.return_value = "https://example.com/course"
    tool = CourseSearchTool(store)
    tool.execute(query="embeddings")

    src = tool.last_sources[0]
    assert src["url"] == "https://example.com/course"
    assert src["label"] == "Chroma Course"


# ---------------------------------------------------------------------------
# Multi-result formatting
# ---------------------------------------------------------------------------


def test_execute_multiple_results_separated_by_blank_lines():
    store = make_store(
        documents=["doc one", "doc two"],
        metadata=[
            {"course_title": "Course A", "lesson_number": 1},
            {"course_title": "Course B", "lesson_number": 2},
        ],
    )
    tool = CourseSearchTool(store)
    result = tool.execute(query="topic")

    assert "Course A" in result
    assert "Course B" in result
    assert "\n\n" in result  # separator between results


def test_execute_result_header_format():
    store = make_store(
        documents=["body text"],
        metadata=[{"course_title": "My Course", "lesson_number": 4}],
    )
    tool = CourseSearchTool(store)
    result = tool.execute(query="q")

    assert "[My Course - Lesson 4]" in result
