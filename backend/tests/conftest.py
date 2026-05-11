import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional
from unittest.mock import MagicMock


# Mirror the request/response models from app.py so this conftest has no import
# dependency on app.py (and therefore no StaticFiles / ChromaDB / embedding-model
# initialisation at import time).
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


@pytest.fixture
def mock_rag_system():
    """Pre-configured MagicMock that stands in for RAGSystem."""
    mock = MagicMock()
    mock.session_manager.create_session.return_value = "session_1"
    mock.query.return_value = ("Test answer", ["Course A - Lesson 1"])
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    return mock


@pytest.fixture
def test_app(mock_rag_system):
    """
    Minimal FastAPI app that mirrors the routes in app.py but:
    - does not mount StaticFiles (so ../frontend needn't exist)
    - uses mock_rag_system instead of initialising ChromaDB / embeddings
    """
    app = FastAPI()

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def client(test_app):
    """TestClient wired to the test app."""
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Shared test-data helpers
# ---------------------------------------------------------------------------

SAMPLE_COURSES = ["Introduction to Python", "MCP Fundamentals"]

SAMPLE_ANALYTICS = {
    "total_courses": len(SAMPLE_COURSES),
    "course_titles": SAMPLE_COURSES,
}
