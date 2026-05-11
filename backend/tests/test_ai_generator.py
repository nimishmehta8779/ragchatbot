"""Tests for AIGenerator in backend/ai_generator.py — focuses on tool-call path."""
import pytest
from unittest.mock import MagicMock, call, patch
from ai_generator import AIGenerator
from .conftest import make_text_response, make_tool_use_response, FakeToolUseBlock


DUMMY_API_KEY = "sk-ant-test-key"
DUMMY_MODEL = "claude-test-model"

TOOL_DEFINITIONS = [
    {
        "name": "search_course_content",
        "description": "Search course materials",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }
]


@pytest.fixture
def generator(mock_anthropic_client):
    return AIGenerator(api_key=DUMMY_API_KEY, model=DUMMY_MODEL)


class TestDirectResponse:

    def test_direct_response_returned_as_text(self, generator, mock_anthropic_client):
        """When Claude answers directly (no tool call), the text is returned."""
        mock_anthropic_client.messages.create.return_value = make_text_response("Paris is the capital of France.")

        result = generator.generate_response(query="What is the capital of France?")

        assert result == "Paris is the capital of France."

    def test_direct_response_does_not_call_tool_manager(self, generator, mock_anthropic_client):
        """Non-tool response must not invoke the tool_manager."""
        mock_anthropic_client.messages.create.return_value = make_text_response("Some answer.")
        tool_manager = MagicMock()

        generator.generate_response(query="General question", tool_manager=tool_manager)

        tool_manager.execute_tool.assert_not_called()


class TestToolUsePath:

    def test_tool_use_calls_tool_manager_with_correct_name_and_input(
        self, generator, mock_anthropic_client
    ):
        """On tool_use stop reason, execute_tool is called with name + input."""
        tool_input = {"query": "decorators"}
        first_response = make_tool_use_response("search_course_content", tool_input)
        second_response = make_text_response("Decorators are wrappers around functions.")
        mock_anthropic_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "Content about decorators."

        generator.generate_response(
            query="What are decorators?",
            tools=TOOL_DEFINITIONS,
            tool_manager=tool_manager,
        )

        tool_manager.execute_tool.assert_called_once_with("search_course_content", query="decorators")

    def test_tool_result_included_in_second_api_call_messages(
        self, generator, mock_anthropic_client
    ):
        """The second API call's messages must contain a tool_result block."""
        tool_input = {"query": "decorators"}
        first_response = make_tool_use_response("search_course_content", tool_input)
        second_response = make_text_response("Answer based on tool result.")
        mock_anthropic_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "Found: content about decorators."

        generator.generate_response(
            query="What are decorators?",
            tools=TOOL_DEFINITIONS,
            tool_manager=tool_manager,
        )

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]
        # Last message should be the user message containing the tool_result
        tool_result_msg = messages[-1]
        assert tool_result_msg["role"] == "user"
        assert isinstance(tool_result_msg["content"], list)
        result_block = tool_result_msg["content"][0]
        assert result_block["type"] == "tool_result"
        assert result_block["content"] == "Found: content about decorators."

    def test_tool_call_final_api_includes_tools(self, generator, mock_anthropic_client):
        """The synthesis API call must include tools (Anthropic requires it when messages contain tool_result blocks)."""
        tool_input = {"query": "MCP servers"}
        first_response = make_tool_use_response("search_course_content", tool_input)
        second_response = make_text_response("MCP stands for Model Context Protocol.")
        mock_anthropic_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "MCP content here."

        generator.generate_response(
            query="What is MCP?",
            tools=TOOL_DEFINITIONS,
            tool_manager=tool_manager,
        )

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1].kwargs
        assert "tools" in second_call_kwargs, (
            "BUG: 'tools' is missing from the second API call in _handle_tool_execution. "
            "The Anthropic API requires tools to be present when messages contain "
            "tool_result blocks."
        )

    def test_tool_use_returns_final_text(self, generator, mock_anthropic_client):
        """The synthesized text from the second API call is returned to the caller."""
        tool_input = {"query": "decorators"}
        first_response = make_tool_use_response("search_course_content", tool_input)
        second_response = make_text_response("Decorators wrap functions.")
        mock_anthropic_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "Content about decorators."

        result = generator.generate_response(
            query="Explain decorators",
            tools=TOOL_DEFINITIONS,
            tool_manager=tool_manager,
        )

        assert result == "Decorators wrap functions."


class TestTwoRoundToolCalls:

    def test_two_rounds_executes_both_tools(self, generator, mock_anthropic_client):
        """When Claude makes 2 sequential tool calls, execute_tool is called twice."""
        r1 = make_tool_use_response("search_course_content", {"query": "outline of Course X"}, block_id="toolu_01")
        r2 = make_tool_use_response("search_course_content", {"query": "topic from lesson 4"}, block_id="toolu_02")
        r3 = make_text_response("Here is the answer.")
        mock_anthropic_client.messages.create.side_effect = [r1, r2, r3]

        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = ["Outline result.", "Content result."]

        generator.generate_response(
            query="Find a course on the same topic as lesson 4 of Course X",
            tools=TOOL_DEFINITIONS,
            tool_manager=tool_manager,
        )

        assert tool_manager.execute_tool.call_count == 2
        tool_manager.execute_tool.assert_any_call("search_course_content", query="outline of Course X")
        tool_manager.execute_tool.assert_any_call("search_course_content", query="topic from lesson 4")

    def test_second_round_messages_include_first_results(self, generator, mock_anthropic_client):
        """The 3rd API call's messages contain all prior tool interactions (5 messages total)."""
        r1 = make_tool_use_response("search_course_content", {"query": "step one"}, block_id="toolu_01")
        r2 = make_tool_use_response("search_course_content", {"query": "step two"}, block_id="toolu_02")
        r3 = make_text_response("Final answer.")
        mock_anthropic_client.messages.create.side_effect = [r1, r2, r3]

        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = ["Result one.", "Result two."]

        generator.generate_response(
            query="Two-step query",
            tools=TOOL_DEFINITIONS,
            tool_manager=tool_manager,
        )

        third_call_kwargs = mock_anthropic_client.messages.create.call_args_list[2].kwargs
        messages = third_call_kwargs["messages"]
        # user / assistant(r1 tool_use) / user(tool_result r1) / assistant(r2 tool_use) / user(tool_result r2)
        assert len(messages) == 5
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"][0]["type"] == "tool_result"
        assert messages[2]["content"][0]["content"] == "Result one."
        assert messages[3]["role"] == "assistant"
        assert messages[4]["role"] == "user"
        assert messages[4]["content"][0]["type"] == "tool_result"
        assert messages[4]["content"][0]["content"] == "Result two."

    def test_max_rounds_stops_after_two(self, generator, mock_anthropic_client):
        """With 3 consecutive tool_use responses, only 3 total API calls are made (no infinite loop)."""
        r1 = make_tool_use_response("search_course_content", {"query": "q1"}, block_id="toolu_01")
        r2 = make_tool_use_response("search_course_content", {"query": "q2"}, block_id="toolu_02")
        r3 = make_tool_use_response("search_course_content", {"query": "q3"}, block_id="toolu_03")
        mock_anthropic_client.messages.create.side_effect = [r1, r2, r3]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "Some result."

        result = generator.generate_response(
            query="Multi-step query",
            tools=TOOL_DEFINITIONS,
            tool_manager=tool_manager,
        )

        assert mock_anthropic_client.messages.create.call_count == 3
        assert isinstance(result, str)

    def test_tool_error_injects_error_content_and_returns_text(self, generator, mock_anthropic_client):
        """When execute_tool raises, an [ERROR] tool_result is sent and a text response is returned."""
        r1 = make_tool_use_response("search_course_content", {"query": "broken query"}, block_id="toolu_01")
        r2 = make_text_response("I was unable to retrieve that information.")
        mock_anthropic_client.messages.create.side_effect = [r1, r2]

        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = RuntimeError("connection timeout")

        result = generator.generate_response(
            query="A query that causes a tool error",
            tools=TOOL_DEFINITIONS,
            tool_manager=tool_manager,
        )

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]
        tool_result_block = messages[-1]["content"][0]
        assert tool_result_block["type"] == "tool_result"
        assert "[ERROR]" in tool_result_block["content"]
        assert isinstance(result, str)
