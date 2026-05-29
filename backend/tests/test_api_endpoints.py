"""
Tests for the FastAPI endpoints: POST /api/query, GET /api/courses,
DELETE /api/session/{id}, and GET /.

A self-contained test app (defined in conftest.py) is used so the real app.py's
StaticFiles mount (which requires a built frontend) is never imported.
"""
import pytest
from helpers import make_mock_rag


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:

    def test_returns_200_with_valid_query(self, client, mock_rag):
        resp = client.post("/api/query", json={"query": "What is MCP?"})
        assert resp.status_code == 200

    def test_response_body_has_required_fields(self, client):
        resp = client.post("/api/query", json={"query": "What is MCP?"})
        data = resp.json()
        assert "answer" in data
        assert "sources" in data
        assert "source_links" in data
        assert "session_id" in data

    def test_answer_matches_mock_return_value(self, client):
        resp = client.post("/api/query", json={"query": "What is MCP?"})
        assert resp.json()["answer"] == "Test answer"

    def test_sources_list_matches_mock(self, client):
        resp = client.post("/api/query", json={"query": "anything"})
        assert resp.json()["sources"] == ["Course A - Lesson 1"]

    def test_source_links_list_matches_mock(self, client):
        resp = client.post("/api/query", json={"query": "anything"})
        assert resp.json()["source_links"] == ["https://example.com/1"]

    def test_session_id_created_when_not_provided(self, client):
        resp = client.post("/api/query", json={"query": "hello"})
        assert resp.json()["session_id"] == "test-session-id"

    def test_provided_session_id_is_forwarded(self, make_client):
        rag = make_mock_rag()
        c = make_client(rag)
        resp = c.post("/api/query", json={"query": "hello", "session_id": "my-session"})
        assert resp.json()["session_id"] == "my-session"
        # rag.query must have been called with the provided session id
        rag.query.assert_called_once_with("hello", "my-session")

    def test_query_field_is_forwarded_to_rag(self, make_client):
        rag = make_mock_rag()
        c = make_client(rag)
        c.post("/api/query", json={"query": "explain embeddings"})
        call_args = rag.query.call_args
        assert call_args[0][0] == "explain embeddings"

    def test_missing_query_field_returns_422(self, client):
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_rag_exception_returns_500(self, make_client):
        rag = make_mock_rag(raise_on_query=RuntimeError("DB error"))
        c = make_client(rag)
        resp = c.post("/api/query", json={"query": "anything"})
        assert resp.status_code == 500

    def test_500_detail_contains_exception_message(self, make_client):
        rag = make_mock_rag(raise_on_query=RuntimeError("DB error"))
        c = make_client(rag)
        resp = c.post("/api/query", json={"query": "anything"})
        assert "DB error" in resp.json()["detail"]

    def test_sources_are_plain_strings_in_response(self, make_client):
        rag = make_mock_rag(sources=[{"label": "Course X - Lesson 3", "url": None}])
        c = make_client(rag)
        resp = c.post("/api/query", json={"query": "q"})
        for src in resp.json()["sources"]:
            assert isinstance(src, str)

    def test_source_links_null_when_url_is_none(self, make_client):
        rag = make_mock_rag(sources=[{"label": "Course X - Lesson 3", "url": None}])
        c = make_client(rag)
        resp = c.post("/api/query", json={"query": "q"})
        assert resp.json()["source_links"] == [None]

    def test_empty_sources_list_is_valid(self, make_client):
        rag = make_mock_rag(sources=[])
        c = make_client(rag)
        resp = c.post("/api/query", json={"query": "general question"})
        assert resp.status_code == 200
        assert resp.json()["sources"] == []


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:

    def test_returns_200(self, client):
        resp = client.get("/api/courses")
        assert resp.status_code == 200

    def test_response_has_total_courses(self, client):
        resp = client.get("/api/courses")
        assert "total_courses" in resp.json()

    def test_response_has_course_titles(self, client):
        resp = client.get("/api/courses")
        assert "course_titles" in resp.json()

    def test_total_courses_matches_titles_length(self, client):
        data = client.get("/api/courses").json()
        assert data["total_courses"] == len(data["course_titles"])

    def test_course_titles_match_mock(self, client):
        data = client.get("/api/courses").json()
        assert data["course_titles"] == ["Course A", "Course B"]

    def test_rag_exception_returns_500(self, make_client):
        rag = make_mock_rag(raise_on_analytics=RuntimeError("analytics failed"))
        c = make_client(rag)
        resp = c.get("/api/courses")
        assert resp.status_code == 500

    def test_500_detail_contains_exception_message(self, make_client):
        rag = make_mock_rag(raise_on_analytics=RuntimeError("analytics failed"))
        c = make_client(rag)
        resp = c.get("/api/courses")
        assert "analytics failed" in resp.json()["detail"]

    def test_empty_course_list_is_valid(self, make_client):
        rag = make_mock_rag(course_titles=[])
        c = make_client(rag)
        resp = c.get("/api/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteSessionEndpoint:

    def test_returns_200(self, client):
        resp = client.delete("/api/session/abc-123")
        assert resp.status_code == 200

    def test_response_status_is_cleared(self, client):
        resp = client.delete("/api/session/abc-123")
        assert resp.json()["status"] == "cleared"

    def test_response_echoes_session_id(self, client):
        resp = client.delete("/api/session/my-session")
        assert resp.json()["session_id"] == "my-session"

    def test_session_manager_clear_called_with_correct_id(self, make_client):
        rag = make_mock_rag()
        c = make_client(rag)
        c.delete("/api/session/xyz-session")
        rag.session_manager.clear_session.assert_called_once_with("xyz-session")


# ---------------------------------------------------------------------------
# GET /  (health / root)
# ---------------------------------------------------------------------------

class TestRootEndpoint:

    def test_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_returns_status_ok(self, client):
        resp = client.get("/")
        assert resp.json() == {"status": "ok"}
