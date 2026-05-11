import sys
import os
from unittest.mock import MagicMock

# Add backend/ to sys.path so bare imports (e.g. `from vector_store import ...`) resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional
from vector_store import SearchResults


# ---------------------------------------------------------------------------
# Response object helpers — mimic the shape of Anthropic SDK response objects
# ---------------------------------------------------------------------------

class FakeTextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class FakeToolUseBlock:
    def __init__(self, name: str, tool_input: dict, block_id: str = "toolu_01"):
        self.type = "tool_use"
        self.name = name
        self.input = tool_input
        self.id = block_id


class FakeResponse:
    def __init__(self, stop_reason: str, content: list):
        self.stop_reason = stop_reason
        self.content = content


def make_text_response(text: str) -> FakeResponse:
    return FakeResponse(stop_reason="end_turn", content=[FakeTextBlock(text)])


def make_tool_use_response(tool_name: str, tool_input: dict, block_id: str = "toolu_01") -> FakeResponse:
    return FakeResponse(
        stop_reason="tool_use",
        content=[FakeToolUseBlock(name=tool_name, tool_input=tool_input, block_id=block_id)],
    )


# ---------------------------------------------------------------------------
# Unit-test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.search.return_value = SearchResults(
        documents=["Sample lesson content about Python decorators."],
        metadata=[{"course_title": "Intro to Python", "lesson_number": 2}],
        distances=[0.15],
    )
    store.get_lesson_link.return_value = "https://example.com/lesson/2"
    store.get_course_outline.return_value = {
        "title": "Intro to Python",
        "course_link": "https://example.com/course",
        "lessons": [{"lesson_number": 1, "lesson_title": "Basics"}, {"lesson_number": 2, "lesson_title": "Decorators"}],
    }
    store.get_existing_course_titles.return_value = ["Intro to Python"]
    return store


@pytest.fixture
def mock_anthropic_client(monkeypatch):
    """Return a mock Anthropic client and patch anthropic.Anthropic."""
    import anthropic

    client = MagicMock()
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: client)
    return client


# ---------------------------------------------------------------------------
# API / integration-test fixtures
# ---------------------------------------------------------------------------

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
