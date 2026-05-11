"""Tests for CourseSearchTool.execute() in backend/search_tools.py"""
import pytest
from unittest.mock import MagicMock, call
from vector_store import SearchResults
from search_tools import CourseSearchTool


class TestCourseSearchToolExecute:

    def test_execute_returns_formatted_results(self, mock_vector_store):
        """Results are formatted with course title and lesson number header."""
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="Python decorators")

        assert "Intro to Python" in result
        assert "Lesson 2" in result
        assert "Sample lesson content about Python decorators." in result

    def test_execute_returns_error_message_on_store_error(self, mock_vector_store):
        """When store.search() returns an error, that error string is returned."""
        mock_vector_store.search.return_value = SearchResults.empty("Search error: connection refused")
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="anything")

        assert result == "Search error: connection refused"

    def test_execute_returns_no_content_message_when_empty(self, mock_vector_store):
        """Empty results (no error) produce a 'No relevant content found' message."""
        mock_vector_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="obscure topic")

        assert result.startswith("No relevant content found")

    def test_execute_no_content_message_includes_filters(self, mock_vector_store):
        """Empty results message mentions the applied course and lesson filters."""
        mock_vector_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="obscure topic", course_name="Intro to Python", lesson_number=3)

        assert "Intro to Python" in result
        assert "3" in result

    def test_execute_passes_filters_to_store(self, mock_vector_store):
        """course_name and lesson_number are forwarded to store.search()."""
        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="decorators", course_name="Intro to Python", lesson_number=2)

        mock_vector_store.search.assert_called_once_with(
            query="decorators", course_name="Intro to Python", lesson_number=2
        )

    def test_execute_populates_last_sources(self, mock_vector_store):
        """After a successful search, last_sources is populated."""
        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="decorators")

        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["label"] == "Intro to Python - Lesson 2"

    def test_execute_includes_lesson_link_in_sources(self, mock_vector_store):
        """get_lesson_link is called and the URL is stored in sources."""
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson/2"
        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="decorators")

        assert tool.last_sources[0]["url"] == "https://example.com/lesson/2"
        mock_vector_store.get_lesson_link.assert_called_once_with("Intro to Python", 2)

    def test_execute_multiple_results_all_formatted(self, mock_vector_store):
        """All returned documents appear in the formatted output."""
        mock_vector_store.search.return_value = SearchResults(
            documents=["Content A", "Content B"],
            metadata=[
                {"course_title": "Course 1", "lesson_number": 1},
                {"course_title": "Course 1", "lesson_number": 2},
            ],
            distances=[0.1, 0.2],
        )
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="something")

        assert "Content A" in result
        assert "Content B" in result
