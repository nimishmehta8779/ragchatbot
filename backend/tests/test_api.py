"""
API endpoint tests for the RAG chatbot backend.

Uses the `client` fixture from conftest.py, which spins up a lightweight
FastAPI app with a mocked RAGSystem — no ChromaDB, no embeddings, no
static-file directory required.
"""


class TestQueryEndpoint:
    """POST /api/query"""

    def test_returns_200_with_answer_and_sources(self, client):
        response = client.post("/api/query", json={"query": "What is Python?"})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test answer"
        assert data["sources"] == ["Course A - Lesson 1"]

    def test_auto_creates_session_when_none_provided(self, client, mock_rag_system):
        response = client.post("/api/query", json={"query": "What is Python?"})
        assert response.status_code == 200
        assert response.json()["session_id"] == "session_1"
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_uses_provided_session_id(self, client, mock_rag_system):
        response = client.post(
            "/api/query",
            json={"query": "What is Python?", "session_id": "existing_session"},
        )
        assert response.status_code == 200
        assert response.json()["session_id"] == "existing_session"
        # Should not create a new session
        mock_rag_system.session_manager.create_session.assert_not_called()
        mock_rag_system.query.assert_called_once_with("What is Python?", "existing_session")

    def test_response_shape(self, client):
        response = client.post("/api/query", json={"query": "hello"})
        data = response.json()
        assert set(data.keys()) == {"answer", "sources", "session_id"}
        assert isinstance(data["sources"], list)
        assert isinstance(data["answer"], str)
        assert isinstance(data["session_id"], str)

    def test_missing_query_field_returns_422(self, client):
        response = client.post("/api/query", json={})
        assert response.status_code == 422

    def test_empty_query_string_is_accepted(self, client):
        # Validation only checks that the field exists, not that it's non-empty
        response = client.post("/api/query", json={"query": ""})
        assert response.status_code == 200

    def test_rag_error_returns_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = Exception("RAG failure")
        response = client.post("/api/query", json={"query": "trigger error"})
        assert response.status_code == 500
        assert "RAG failure" in response.json()["detail"]

    def test_session_creation_error_returns_500(self, client, mock_rag_system):
        mock_rag_system.session_manager.create_session.side_effect = Exception("session error")
        response = client.post("/api/query", json={"query": "hello"})
        assert response.status_code == 500


class TestCoursesEndpoint:
    """GET /api/courses"""

    def test_returns_200_with_course_stats(self, client):
        response = client.get("/api/courses")
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 2
        assert data["course_titles"] == ["Course A", "Course B"]

    def test_response_shape(self, client):
        response = client.get("/api/courses")
        data = response.json()
        assert "total_courses" in data
        assert "course_titles" in data
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

    def test_analytics_error_returns_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = Exception("DB error")
        response = client.get("/api/courses")
        assert response.status_code == 500
        assert "DB error" in response.json()["detail"]

    def test_empty_catalog_returns_zero_courses(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        response = client.get("/api/courses")
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_calls_rag_system_analytics(self, client, mock_rag_system):
        client.get("/api/courses")
        mock_rag_system.get_course_analytics.assert_called_once()
