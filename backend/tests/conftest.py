import sys
import os
from unittest.mock import MagicMock

# Add backend/ to sys.path so bare imports (e.g. `from vector_store import ...`) resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
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
# Fixtures
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
