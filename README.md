# Students Database CRUD Application + Local AI

A Python project scaffold for a student database application built with FastAPI,
SQLite, SQLAlchemy, Pydantic, and Ollama. The planned application will support
student CRUD operations and natural-language questions about student data.

## Project status

The SQLite connection, SQLAlchemy session handling, student and user database
models, and startup table initialization are implemented. The API supports student CRUD, search, filtering, sorting, and pagination.
Student writes and the AI assistant require authentication.

By default, the application stores its database in `students.db` in the current
working directory. Set the `DATABASE_URL` environment variable to use a
different SQLAlchemy database URL.

## Setup

Create and activate the virtual environment, then install the Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the API

In the VS Code terminal, open the project folder and activate the virtual
environment with PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then start the development server from the project root:

```powershell
uvicorn app.main:app --reload
```

The API health check is available at `http://127.0.0.1:8000/health`. If PowerShell
blocks environment activation, run Uvicorn through the environment's Python
instead:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Student endpoints are `POST /students`, `GET /students`,
`GET /students/{student_id}`, `PUT /students/{student_id}`, and
`DELETE /students/{student_id}`.
`GET /students` accepts `limit` (default 100, maximum 500) and `offset`
(default 0) query parameters for pagination. It also supports case-insensitive
substring search using `search` across names and emails, `course` and `address`
filters, and sorting with `sort_by` (`student_id`, `name`, or
`enrollment_date`) and `sort_order` (`asc` or `desc`).

## Local AI assistant

Run Ollama locally and make sure the `qwen2.5:3b` model is available. The
assistant uses Ollama at `http://127.0.0.1:11434` by default; `OLLAMA_BASE_URL`
and `OLLAMA_MODEL` can override those values.

Send a question to the authenticated `POST /ai/ask` endpoint:

```json
{
  "question": "How many students are enrolled in Computer Science?"
}
```

The supported questions are the total student count, the count for one course,
and a count summary grouped by course. Course summaries contain at most 20
courses. Requests for individual students or personal details are not supported. This
endpoint requires the bearer token returned by `POST /auth/login`.
The model classifies the question into a validated intent; fixed, read-only
SQLAlchemy aggregate queries produce the answer. The model does not receive
student records, and generated SQL is never executed. Invalid/unsupported
questions return HTTP 422; an unavailable local Ollama service returns HTTP 503.

The Ollama Python package is listed in `requirements.txt`, but the integration
uses Ollama's local HTTP API through Python's standard library and does not
require installing another package.

## Authentication

Student creation, update, and deletion require a bearer access token. Student
listing and retrieval remain public. Register with `POST /auth/register`, then
log in with `POST /auth/login` using JSON containing `email` and `password`.
Use the returned `access_token` as `Authorization: Bearer <token>`.

Set `JWT_SECRET_KEY` in a project-root `.env` file before starting the API. The
file is excluded from Git and the secret must contain at least 32 bytes. On
first setup, generate the file without displaying the secret:

```powershell
& .\.venv\Scripts\python.exe -c "import secrets; from pathlib import Path; p = Path('.env'); p.exists() or p.write_text('JWT_SECRET_KEY=' + secrets.token_urlsafe(48) + '\n', encoding='utf-8')"
```

For deployments, configure a persistent secret through the hosting
environment's secret manager. `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` optionally
sets the token lifetime and defaults to 30 minutes. Do not commit or share the
contents of `.env`.
