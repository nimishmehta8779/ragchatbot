"""
Tests for RAGSystem.query() — verifies how the pipeline handles content questions.

All Anthropic API calls are mocked; ChromaDB is replaced by mock_vector_store.
"""
import pytest
from unittest.mock import MagicMock, patch
from .conftest import make_text_response, make_tool_use_response


TOOL_DEFINITIONS = [
    {
        "name": "search_course_content",
        "description": "Search course materials",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }
]


@pytest.fixture
def rag_system(mock_vector_store, mock_anthropic_client):
    """Build a RAGSystem with mocked VectorStore and Anthropic client."""
    from config import Config

    cfg = Config(ANTHROPIC_API_KEY="sk-ant-test")

    with patch("rag_system.VectorStore", return_value=mock_vector_store), \
         patch("rag_system.DocumentProcessor"), \
         patch("rag_system.SessionManager") as MockSession:

        # Simple session behaviour
        MockSession.return_value.get_conversation_history.return_value = None
        MockSession.return_value.create_session.return_value = "session_1"

        from rag_system import RAGSystem
        system = RAGSystem(cfg)

    return system


class TestRAGGeneralQuestions:

    def test_general_question_no_tool_call(self, rag_system, mock_anthropic_client):
        """A general-knowledge question is answered directly without calling the search tool."""
        mock_anthropic_client.messages.create.return_value = make_text_response(
            "Paris is the capital of France."
        )

        answer, sources = rag_system.query("What is the capital of France?")

        assert answer == "Paris is the capital of France."
        assert sources == []
        # Only one API call — no tool round-trip
        assert mock_anthropic_client.messages.create.call_count == 1


class TestRAGContentQueries:

    def test_content_query_triggers_search_tool(self, rag_system, mock_anthropic_client):
        """A content question causes the search tool to be called."""
        tool_input = {"query": "Python decorators"}
        first_response = make_tool_use_response("search_course_content", tool_input)
        second_response = make_text_response("Decorators are wrappers around functions.")
        mock_anthropic_client.messages.create.side_effect = [first_response, second_response]

        answer, _ = rag_system.query("What are Python decorators?")

        assert mock_anthropic_client.messages.create.call_count == 2
        assert answer == "Decorators are wrappers around functions."

    def test_content_query_returns_sources(self, rag_system, mock_anthropic_client):
        """After a content query, sources from the search tool are returned."""
        tool_input = {"query": "Python decorators"}
        first_response = make_tool_use_response("search_course_content", tool_input)
        second_response = make_text_response("Decorators wrap functions.")
        mock_anthropic_client.messages.create.side_effect = [first_response, second_response]

        _, sources = rag_system.query("What are Python decorators?")

        assert len(sources) > 0
        assert sources[0]["label"] == "Intro to Python - Lesson 2"

    def test_content_query_second_api_call_includes_tools(
        self, rag_system, mock_anthropic_client
    ):
        """
        The second API call (synthesis after tool execution) MUST include tools.

        This mirrors test_ai_generator.py::test_tool_call_final_api_includes_tools
        at the RAGSystem integration level.  Expected to FAIL against current code.
        """
        tool_input = {"query": "MCP servers"}
        first_response = make_tool_use_response("search_course_content", tool_input)
        second_response = make_text_response("MCP stands for Model Context Protocol.")
        mock_anthropic_client.messages.create.side_effect = [first_response, second_response]

        rag_system.query("Explain MCP servers from the course.")

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1].kwargs
        assert "tools" in second_call_kwargs, (
            "BUG: 'tools' is missing from the synthesis API call. "
            "The Anthropic API requires tools when messages contain tool_result blocks."
        )


class TestRAGSessionHandling:

    def test_session_history_passed_to_ai(self, rag_system, mock_anthropic_client):
        """Existing session history is included in the system prompt sent to Claude."""
        rag_system.session_manager.get_conversation_history.return_value = (
            "User: Hi\nAssistant: Hello!"
        )
        mock_anthropic_client.messages.create.return_value = make_text_response("Answer.")

        rag_system.query("Follow-up question", session_id="session_1")

        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        assert "Hi" in call_kwargs["system"]
        assert "Hello!" in call_kwargs["system"]
