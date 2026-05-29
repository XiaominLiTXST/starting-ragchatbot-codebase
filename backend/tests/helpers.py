"""
Shared test helpers: mock RAGSystem factory and test FastAPI app builder.
Imported by conftest.py (fixtures) and directly by test modules that need
fine-grained control over the mock's behaviour.
"""
from unittest.mock import MagicMock
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pydantic models (mirrored from app.py — no StaticFiles dependency)
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    source_links: List[Optional[str]] = []
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# ---------------------------------------------------------------------------
# Mock factory
# ---------------------------------------------------------------------------

def make_mock_rag(
    answer: str = "Test answer",
    sources=None,
    course_titles=None,
    raise_on_query: Exception = None,
    raise_on_analytics: Exception = None,
):
    """Return a MagicMock satisfying the RAGSystem interface used by API endpoints."""
    if sources is None:
        sources = [{"label": "Course A - Lesson 1", "url": "https://example.com/1"}]
    if course_titles is None:
        course_titles = ["Course A", "Course B"]

    rag = MagicMock()

    if raise_on_query:
        rag.query.side_effect = raise_on_query
    else:
        rag.query.return_value = (answer, sources)

    rag.session_manager.create_session.return_value = "test-session-id"
    rag.session_manager.clear_session.return_value = None

    if raise_on_analytics:
        rag.get_course_analytics.side_effect = raise_on_analytics
    else:
        rag.get_course_analytics.return_value = {
            "total_courses": len(course_titles),
            "course_titles": course_titles,
        }

    return rag


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def make_test_app(rag=None):
    """
    Build a minimal FastAPI app with the same API routes as app.py but without
    the StaticFiles mount, so tests run without a frontend build present.
    """
    if rag is None:
        rag = make_mock_rag()

    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @test_app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id or rag.session_manager.create_session()
            answer, raw_sources = rag.query(request.query, session_id)
            source_labels = [s["label"] if isinstance(s, dict) else s for s in raw_sources]
            source_links = [s.get("url") if isinstance(s, dict) else None for s in raw_sources]
            return QueryResponse(
                answer=answer,
                sources=source_labels,
                source_links=source_links,
                session_id=session_id,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @test_app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        rag.session_manager.clear_session(session_id)
        return {"status": "cleared", "session_id": session_id}

    @test_app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @test_app.get("/")
    async def root():
        return {"status": "ok"}

    return test_app
