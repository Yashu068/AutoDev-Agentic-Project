# AutoDev Backend API & Architecture Explanation

This document provides a detailed walkthrough of the backend API entry point ([main.py](file:///Users/sarv/Documents/Agentic_project/backend/api/main.py)), the endpoint routes ([runs.py](file:///Users/sarv/Documents/Agentic_project/backend/api/routes/runs.py)), the database layer, and how they orchestrate the LangGraph agentic pipeline.

---

## 1. High-Level Architecture & Lifecycle

The backend is built using **FastAPI** for high-performance async web capabilities, **SQLAlchemy** for database operations, and **LangGraph** for orchestrating a multi-agent workflow.

### ── System Component Flow ──

```mermaid
graph TD
    %% Define Styling
    classDef client fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef fastapi fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef database fill:#fff8e1,stroke:#ff8f00,stroke-width:2px;
    classDef agentic fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px;

    Client["React Frontend (Client)<br/>(Port: 5173)"]:::client
    FastAPI["FastAPI Web Server<br/>(Uvicorn on Port: 8000)"]:::fastapi
    Postgres["PostgreSQL Database<br/>(tables: users, runs)"]:::database
    LangGraph["LangGraph Orchestrator<br/>(agents.orchestrator:pipeline)"]:::agentic

    Client -->|HTTP Request| FastAPI
    FastAPI -->|Queries / Updates| Postgres
    FastAPI -->|Spawns Background Task| LangGraph
    LangGraph -->|Read/Write State| Postgres
```

---

## 2. Entry Point: `main.py`

The entry point of the FastAPI application is located in [main.py](file:///Users/sarv/Documents/Agentic_project/backend/api/main.py). 

### ── Core Responsibilities of `main.py` ──

1. **Lifespan Event Management**:
   - Uses `@asynccontextmanager` to execute code during startup and shutdown.
   - **Startup**: Validates environment variables and initializes the Postgres database schema (creating tables if they do not exist).
   - **Shutdown**: Performs clean-ups (logging the shutdown sequence).
2. **App Instantiation**: Creates the FastAPI instance with platform metadata.
3. **CORS Configuration**: Adds middleware to allow cross-origin requests from the frontend developer server (e.g. `http://localhost:5173`).
4. **Route Registration**: Mounts the REST routes from `api.routes.runs` under the `/api/v1` path prefix.

### ── App Startup Lifecycle ──

```mermaid
sequenceDiagram
    autonumber
    participant Host as Host Process (Uvicorn)
    participant App as FastAPI App
    participant Env as Config (config.py)
    participant DB as Database (db/database.py)

    Host->>App: Start App Lifecycle (uvicorn api.main:app)
    activate App
    App->>Env: validate_environment()
    note over Env: Verify presence of keys:<br/>GEMINI_API_KEY, GROQ_API_KEY, or<br/>OPENROUTER_API_KEY (at least one),<br/>TAVILY_API_KEY, LANGCHAIN_API_KEY
    Env-->>App: Environment OK
    App->>DB: init_db()
    activate DB
    note over DB: Executes Base.metadata.create_all<br/>to generate 'users' & 'runs' tables
    DB-->>App: Tables Initialized
    deactivate DB
    App-->>Host: Server ready to accept requests on Port 8000
    deactivate App
```

---

## 3. Endpoints Layer: `routes/runs.py`

This router, located in [runs.py](file:///Users/sarv/Documents/Agentic_project/backend/api/routes/runs.py), defines the endpoints controlling project runs as outlined in the **Master Project Specification**.

### ── Request / Response Schema Models ──

The route handler uses **Pydantic** models to validate payload data and format JSON responses:
* **`CreateProjectRequest`**:
  * `prd` (str, min length: 10): The natural language software requirement.
  * `user_id` (Optional str): The client-provided user ID (defaults to `00000000-0000-0000-0000-000000000000` if anonymous).
* **`CreateProjectResponse`**:
  * `success` (bool): `True` if successfully queued.
  * `run_id` (str): UUID uniquely identifying this execution pipeline.
* **`RunStatusResponse`**:
  * `run_id` (str): Run identifier.
  * `status` (str): Current status of the run.

---

### ── Detailed Endpoint Registry ──

| Method | Path | Description | Input / Parameters | Response Schema | DB Actions |
|:---|:---|:---|:---|:---|:---|
| **POST** | `/api/v1/projects/create` | Kick off a new multi-agent pipeline | Body: `CreateProjectRequest` | `CreateProjectResponse` | Upserts `User`, registers `Run` with status `pending` |
| **GET** | `/api/v1/projects/history` | List all historical pipeline runs | None | `{"projects": [{"run_id": str, "status": str}]}` | Selects run IDs, statuses, and creation time ordered by `created_at DESC` |
| **GET** | `/api/v1/projects/{run_id}` | Fetch the current state status | Path: `run_id` | `RunStatusResponse` | Queries Run record |
| **GET** | `/api/v1/projects/{run_id}/logs` | Fetch real-time run-time logging | Path: `run_id` | `{"logs": List[str]}` | Queries logs column of Run record |
| **GET** | `/api/v1/projects/{run_id}/download` | Fetch project artifact download link | Path: `run_id` | `{"download_url": str}` | Queries `download_url` column of Run |
| **GET** | `/api/v1/health` | Health Check probe | None | `{"status": "healthy"}` | None |

---

### ── Detailed Sequence Flow of `POST /projects/create` ──

When a client submits a new project description (PRD), the following async workflow occurs:

```mermaid
sequenceDiagram
    autonumber
    actor Client as Frontend Client
    participant API as FastAPI (runs.py)
    participant DB as Postgres DB
    participant Graph as LangGraph Orchestrator (orchestrator.py)

    Client->>API: POST /api/v1/projects/create (prd_text, user_id)
    activate API
    API->>API: Generate unique run_id (UUID v4)
    API->>DB: _ensure_user_exists(user_id)
    note over DB: Inserts user row if missing
    DB-->>API: User Verified

    API->>API: create_initial_state(run_id, user_id, prd_text)
    note over API: Generates blank dictionary conforming to AutoDevState

    API->>DB: save_state_to_db(state)
    DB-->>API: Initial record saved (pending)

    API->>API: Spawn background asyncio task<br/>_run_pipeline_background(run_id, state)
    
    API-->>Client: Return CreateProjectResponse(success=True, run_id=run_id)
    deactivate API

    %% Background activity
    note over API: Background thread resumes execution
    activate API
    API->>Graph: run_pipeline(state)
    activate Graph
    note over Graph: Triggers Agents:<br/>Research -> Planner -> Coder -> Tester -> (Debug/Reviewer)
    Graph->>DB: save_state_to_db(state) [For each stage transition]
    Graph-->>API: Returns final_state
    deactivate Graph
    API->>DB: save_state_to_db(final_state) [completed / failed / escalated]
    deactivate API
```

---

## 4. The Agent Pipeline Connection

FastAPI and the LangGraph orchestrator communicate through a shared state structure called `AutoDevState` (defined in [state.py](file:///Users/sarv/Documents/Agentic_project/backend/graph/state.py)). 

### ── State Transition Diagram ──

Here is how the pipeline status transitions inside the background task from node to node:

```mermaid
stateDiagram-v2
    [*] --> pending : Initial Insertion in runs.py

    state background_pipeline {
        pending --> researching : research_node starts
        researching --> planning : planner_node starts
        planning --> coding : coder_node starts
        coding --> testing : tester_node starts
        
        testing --> reviewer : Tests Pass
        testing --> debugger : Tests Fail (Retries < 5)
        testing --> escalate : Tests Fail (Retries >= 5)

        debugger --> coding : Loops back to Coder to fix code
    }

    reviewer --> completed : Final ZIP generated & DB saved
    escalate --> escalated : Waiting for developer intervention
    background_pipeline --> failed : Code execution crashed / fatal exception

    completed --> [*]
    escalated --> [*]
    failed --> [*]
```

### ── Schema Mapping between `AutoDevState` and PostgreSQL ──

When `save_state_to_db` is called, the fields in the Python `AutoDevState` dict are mapped to the columns of the `runs` table (managed in [db/models.py](file:///Users/sarv/Documents/Agentic_project/backend/db/models.py)):

* **Identity**: `run_id` ➔ `id` (PK), `user_id` ➔ `user_id` (FK to `users.id`), `prd_text` ➔ `prd_text` (Text)
* **Progress Status**: `status` ➔ `status` (String)
* **Agent Context (JSONB Columns)**:
  * `research_output` (JSONB): Web search results, tech stack notes, reference URLs.
  * `task_plan` (JSONB): File structure blueprint, implementation order.
  * `code_files` (JSONB): Complete source code dictionary `{file_path: file_content}`.
  * `test_results` (JSONB): Outcome of `pytest` execution (`passed`, `failures`, `exit_code`).
  * `review_result` (JSONB): Linter output (`Ruff`/`ESLint`), quality score.
* **Delivery & Logs**:
  * `download_url` ➔ `download_url` (presigned zip link)
  * `logs` ➔ `logs` (Postgres string Array `Text[]`)
  * `total_tokens` ➔ `total_tokens` (Int)
  * Timestamps (`created_at`, `updated_at`, `completed_at`) are computed automatically.
