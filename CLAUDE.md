# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Install dependencies
uv sync

# Start the server (from project root)
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000
```

Requires a `.env` file in the project root (copy from `.env.example`):
```
ANTHROPIC_API_KEY=your-key-here
```

The server runs at `http://localhost:8000`. On startup it auto-ingests all `.txt/.pdf/.docx` files from `docs/` into ChromaDB, skipping any courses already stored.

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot with a FastAPI backend and plain JS frontend.

**Request flow for a user query:**
1. Frontend (`frontend/script.js`) POSTs `{ query, session_id }` to `POST /api/query`
2. `app.py` delegates to `RAGSystem.query()`
3. `RAGSystem` sends the query to Claude via `AIGenerator` with the `search_course_content` tool available
4. Claude either answers directly (general knowledge) or calls the tool (course-specific questions)
5. If tool is called: `CourseSearchTool` → `VectorStore.search()` → ChromaDB → results returned to Claude for a second synthesis call
6. Final answer + sources returned to the frontend

**Key design decisions:**
- Tool use is the *only* retrieval path — there is no unconditional pre-fetch of context. Claude decides when to search.
- ChromaDB has two separate collections: `course_catalog` (course-level metadata, used for fuzzy course name resolution) and `course_content` (text chunks, used for semantic search). Searches against content can be filtered by `course_title` and/or `lesson_number`.
- Session history is stored in-memory (lost on restart), formatted as a plain string appended to the system prompt. Capped at the last 2 exchanges (`MAX_HISTORY` in `config.py`).
- Embeddings are generated locally via `all-MiniLM-L6-v2` (sentence-transformers) — no external embedding API.

**Component responsibilities:**
- `backend/config.py` — all tuneable settings in one `Config` dataclass (model, chunk size, overlap, max results, history length, ChromaDB path)
- `backend/document_processor.py` — parses the structured course `.txt` format and splits content into sentence-aware overlapping chunks
- `backend/vector_store.py` — ChromaDB wrapper; handles collection creation, adding/searching course content and metadata
- `backend/search_tools.py` — `Tool` ABC, `CourseSearchTool` implementation, and `ToolManager` registry
- `backend/session_manager.py` — in-memory session store keyed by `session_N` IDs
- `backend/ai_generator.py` — Anthropic SDK wrapper; handles the two-turn tool-use pattern (first call may trigger tool, second call synthesizes)

## Course Document Format

Course files in `docs/` must follow this structure:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <lesson title>
Lesson Link: <url>
<lesson content...>

Lesson 1: <lesson title>
...
```

The title is used as the unique ID in ChromaDB — duplicate titles are skipped on re-ingestion.
