# 🤖 Autonomous Multi-Agent Software Development Platform

[![Status: Architecture & Initial Development](https://img.shields.io/badge/Status-Architecture%20%26%20Initial%20Development-orange?style=for-the-badge)](https://github.com/Yashu068/AutoDev-Agentic-Project)
[![Tech Stack: FastAPI & LangGraph](https://img.shields.io/badge/Tech--Stack-FastAPI%20%7C%20LangGraph-blue?style=for-the-badge)](https://github.com/Yashu068/AutoDev-Agentic-Project)
[![Budget: ₹0](https://img.shields.io/badge/Budget-%E2%82%B90%20(Free%20Tier)-green?style=for-the-badge)](https://github.com/Yashu068/AutoDev-Agentic-Project)

## 📋 Overview

This project is a **B2B SaaS autonomous software development platform** that converts plain English requirements into complete working software applications without human coding. 

The system utilizes a highly coordinated team of **six specialized AI agents** that perform research, planning, code generation, testing, debugging, and code review automatically.

A user submits a Product Requirement Document (PRD) in natural language, and the platform generates a complete, production-ready codebase that can be downloaded as a ZIP file or stored for future access.

---

## 🎯 Project Goals

### Primary Goal
Build an autonomous software engineering system capable of:
*   **Understanding** user requirements (PRDs).
*   **Researching** technologies and documentation.
*   **Designing** robust project architecture.
*   **Generating** high-quality source code.
*   **Writing** comprehensive unit tests.
*   **Running** tests in a secure, isolated sandbox.
*   **Fixing** execution/logical errors automatically.
*   **Reviewing** code quality, formatting, and performance.
*   **Delivering** final, complete, working projects.

### Target Users
*   Software agencies
*   Startup founders
*   Small businesses
*   Freelancers
*   Internal engineering teams

---

## 🔄 Core Workflow

The system utilizes a structured state-machine workflow orchestrating the agents. Here is the visual flow of execution:

```mermaid
graph TD
    UserRequirement["User Requirement"] --> ResearchAgent["Research Agent"]
    ResearchAgent --> PlannerAgent["Planner Agent"]
    PlannerAgent --> CoderAgent["Coder Agent"]
    CoderAgent --> TesterAgent["Tester Agent"]
    TesterAgent --> TestsPassed{"Tests Passed?"}
    
    TestsPassed -- Yes --> Reviewer["Reviewer"]
    TestsPassed -- No --> Debugger["Debugger"]
    
    Reviewer --> ZIPDelivery["ZIP Delivery"]
    ZIPDelivery --> DatabaseStorage["Database Storage"]
    DatabaseStorage --> Completed["Completed"]
    
    Debugger --> Retry{"Retry < 3 ?"}
    Retry -- Yes --> CoderAgent

    style UserRequirement fill:#f9f,stroke:#333,stroke-width:1px
    style TestsPassed fill:#bbf,stroke:#333,stroke-width:1px
    style Retry fill:#ffb,stroke:#333,stroke-width:1px
    style Completed fill:#9f9,stroke:#333,stroke-width:1px
```

---

## 🧠 Multi-Agent Architecture

The system contains six autonomous agents, each having a dedicated and isolated responsibility:

### 🔬 Agent 1: Research Agent
*   **Purpose**: Collect technical knowledge required for implementation.
*   **Responsibilities**:
    *   Search web resources.
    *   Read documentation.
    *   Analyze third-party APIs.
    *   Gather implementation details.
    *   Generate structured research output.
*   **LLM**: `Gemma 4 31B` (via OpenRouter)
*   **Tools**: Tavily, Firecrawl, BeautifulSoup
*   **Output Shape**:
    ```json
    {
      "tech_stack": [],
      "libraries": [],
      "api_docs": [],
      "implementation_notes": []
    }
    ```

### 📅 Agent 2: Planner Agent
*   **Purpose**: Convert research into a structured implementation plan.
*   **Responsibilities**:
    *   Analyze research output.
    *   Create project architecture.
    *   Create folder and file structures.
    *   Define implementation order.
    *   Generate file blueprints.
*   **LLM**: `Nemotron 3 Super` (via OpenRouter) | *Fallback*: `gpt-oss-120b`
*   **Validation**: Pydantic validation
*   **Output Shape**:
    ```json
    {
      "folders": [],
      "files": [],
      "dependencies": [],
      "execution_order": []
    }
    ```

### 💻 Agent 3: Coder Agent
*   **Purpose**: Generate production-ready source code.
*   **Responsibilities**:
    *   Create project files.
    *   Generate optimized code.
    *   Maintain a growing code context.
    *   Strictly follow planner instructions.
*   **LLM**: `Poolside Laguna M.1` (via OpenRouter) | *Fallback*: `gpt-oss-120b`
*   **Tools**: `os`, `pathlib`, `tempfile`
*   **Important Rule**: 
    > [!IMPORTANT]
    > **Growing Context Strategy**: Every new file receives context from all previously generated files. This ensures consistency and correctness of imports across the project.

### 🧪 Agent 4: Tester Agent
*   **Purpose**: Validate generated code.
*   **Responsibilities**:
    *   Generate pytest/unit tests.
    *   Execute tests.
    *   Collect failure traces.
    *   Produce execution reports.
*   **LLM**: `Llama 3.3 70B` (via OpenRouter)
*   **Tools**: Docker Sandbox, Pytest
*   **Security Constraints**:
    *   *Internet Access*: Disabled
    *   *RAM Limit*: 256 MB
    *   *Timeout*: 30 Seconds
    *   *Execution Environment*: Isolated Container

### 🛠️ Agent 5: Debugger Agent
*   **Purpose**: Repair failed code.
*   **Responsibilities**:
    *   Analyze stack traces and errors.
    *   Identify root causes.
    *   Fix exactly one file at a time.
    *   Retry execution.
*   **LLM**: `Nemotron 3 Super` (via OpenRouter) | *Fallback*: `gpt-oss-120b`
*   **Validation**: AST Parsing
*   **Retry Policy**:
    *   *Maximum Retries* = 3
    *   *After three failed attempts*: **Human Escalation / RunStatus.ESCALATED**

### 🔎 Agent 6: Reviewer Agent
*   **Purpose**: Perform final quality review.
*   **Responsibilities**:
    *   Lint code.
    *   Review architecture.
    *   Generate quality score and report.
    *   Package ZIP.
    *   Save metadata.
*   **LLM**: `Gemma 4 31B` (via OpenRouter)
*   **Tools**: Ruff, ESLint, ZIP Packaging, PostgreSQL

---

## 💾 Shared State Management

All agents communicate through a single, central shared state object using `LangGraph`:

```python
class AutoDevState(TypedDict):
    # Identity
    run_id: str
    user_id: str
    prd_text: str

    # Agent Outputs
    research_output: dict
    task_plan: dict
    code_files: dict
    sandbox_folder: str

    # Testing & Debugging
    test_code: str
    test_results: dict
    retry_count: int
    error_trace: str

    # Review & Delivery
    review_result: dict
    download_url: str

    # Metadata & Tracking
    status: str
    logs: list
    total_tokens: int
```

---

## 🛠️ Technology Stack

| Component | Technology / Tool |
| :--- | :--- |
| **Backend** | Python 3.11, FastAPI, LangGraph, LangSmith, Redis, PostgreSQL |
| **Frontend** | React, Vite |
| **Database** | PostgreSQL, pgAdmin |
| **Sandbox** | Docker |
| **LLM Gateway** | OpenRouter |

---

## 🔑 Environment Variables

Create a `.env` file in the root directory and add the following keys:

```bash
# LLM & Third Party API Keys
OPENROUTER_API_KEY=your_openrouter_api_key
TAVILY_API_KEY=your_tavily_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
LANGSMITH_API_KEY=your_langsmith_api_key

# PostgreSQL Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=agentic

# Database & Cache URLs
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql+asyncpg://postgres:secure_password@localhost:5432/agentic
```

---

## 📂 Folder Structure

```text
project/
│
├── backend/
│   ├── agents/
│   │   ├── research_agent.py
│   │   ├── planner_agent.py
│   │   ├── coder_agent.py
│   │   ├── tester_agent.py
│   │   ├── debugger_agent.py
│   │   └── reviewer_agent.py
│   │
│   ├── graph/
│   │   ├── state.py
│   │   └── orchestrator.py
│   │
│   ├── tools/
│   │   ├── smart_scraper/
│   │   ├── docker_runner/
│   │   ├── smart_linter/
│   │   ├── zip_delivery/
│   │   └── db_delivery/
│   │
│   ├── api/
│   │   ├── main.py
│   │   └── routes/
│   │
│   ├── db/
│   │   ├── models.py
│   │   └── database.py
│   │
│   └── config.py
│
├── frontend/
│
├── docker/
│   └── sandbox/
│
├── tests/
│
├── .env
│
└── README.md
```

---

## 📐 Design Constraints

> [!WARNING]
> These decisions are final, structural guidelines and **must not be changed**.

### Fixed Requirements
1. **All LLMs** must be accessed through **OpenRouter**.
2. A single OpenRouter API key must be used.
3. **Docker sandbox** is strictly mandatory for test execution.
4. **Pydantic validation** is required for inputs and schema integrity.
5. **AST validation** is required for all debugger actions.
6. **Ruff** for Python code linting.
7. **ESLint** for JS/TS code linting.
8. **Growing Context** code generation strategy is required.
9. **Maximum debugger retries** is set to 3.
10. **PostgreSQL** must be used for final storage.
11. **Budget = ₹0** (Use only free-tier services).

---

## 🚀 Deployment

*   **Backend**: Railway
*   **Frontend**: Vercel
*   **Database**: PostgreSQL Docker Container
*   **Administration**: pgAdmin Docker Container

---

## 📊 Development Status

*   **Current Status**: 🛠️ In Active Development
*   **Phase**: Architecture & Initial Development
*   **Progress**: `0%`
*   **Implementation Started**: No
*   **Production Ready**: No

---

