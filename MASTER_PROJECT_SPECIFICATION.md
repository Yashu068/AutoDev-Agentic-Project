# MASTER PROJECT SPECIFICATION

## Autonomous Multi-Agent Software Development Platform

Version: 1.0

Status: Architecture & Initial Development

Owner: Yashu Kumar

Document Type: Master Source of Truth

Purpose: This document contains the complete product, architecture, engineering, and AI development specifications for the Autonomous Multi-Agent Software Development Platform. Any AI system, developer, contributor, or automation tool working on this project must treat this document as the primary source of truth.

---

# 1. Executive Summary

## Product Type

B2B SaaS Autonomous Software Development Platform

## Product Goal

The goal of this platform is to automate the complete software development lifecycle using a team of specialized AI agents.

A user submits software requirements in natural language and receives a fully generated software project including:

* Source code
* Tests
* Documentation
* Quality review
* Downloadable ZIP package

without manually writing code.

---

# 2. Vision Statement

Build a virtual software engineering company powered entirely by AI agents.

The platform should be capable of performing:

* Requirement analysis
* Technical research
* Software planning
* Code generation
* Test generation
* Automated debugging
* Quality review
* Software delivery

with minimal human intervention.

---

# 3. Problem Statement

Software development is expensive, slow, repetitive, and highly dependent on human engineers.

Organizations frequently face:

* Long development cycles
* Expensive engineering teams
* Repetitive coding work
* Manual testing
* Slow debugging
* Knowledge bottlenecks
* Difficult onboarding

The platform aims to reduce these problems through autonomous AI collaboration.

---

# 4. Product Objectives

## Primary Objectives

### OBJ-001

Generate software automatically from natural language requirements.

### OBJ-002

Reduce software delivery time.

### OBJ-003

Reduce development costs.

### OBJ-004

Increase engineering productivity.

### OBJ-005

Create a scalable autonomous development system.

---

## Secondary Objectives

### OBJ-006

Provide project history.

### OBJ-007

Provide execution transparency.

### OBJ-008

Support future scalability.

### OBJ-009

Enable reusable software generation workflows.

---

# 5. Target Customers

## Software Agencies

Needs:

* Faster project delivery
* Reduced staffing requirements
* Improved margins

---

## Startups

Needs:

* Rapid MVP creation
* Lower development costs
* Faster validation

---

## Freelancers

Needs:

* Faster project completion
* Reduced boilerplate work

---

## Internal Engineering Teams

Needs:

* Prototype generation
* Internal tooling
* Development automation

---

# 6. User Personas

## Startup Founder

Goals:

* Launch products rapidly
* Reduce costs
* Validate ideas

Success Criteria:

* Working MVP generated quickly

---

## Agency Owner

Goals:

* Increase throughput
* Reduce delivery time

Success Criteria:

* More projects completed per month

---

## Freelance Developer

Goals:

* Increase productivity
* Reduce repetitive coding

Success Criteria:

* Faster project delivery

---

# 7. Product Scope

## In Scope

### Requirement Analysis

* Natural language PRD processing
* Requirement understanding
* Requirement validation

### Research

* Technology research
* Documentation gathering
* Best practice discovery

### Planning

* Project structure planning
* File planning
* Dependency planning

### Development

* Source code generation
* Configuration generation
* Project scaffolding

### Testing

* Test generation
* Automated execution
* Result collection

### Debugging

* Error analysis
* Automatic fixes

### Review

* Code quality review
* Linting review

### Delivery

* ZIP generation
* Database storage

---

## Out Of Scope

### Version 1

* Mobile application generation
* Infrastructure provisioning
* Production deployment
* Kubernetes generation
* Real-time collaboration
* Custom model training

---

# 8. Product Workflow

Step 1

User submits PRD.

↓

Step 2

Run ID created.

↓

Step 3

Research Agent executes.

↓

Step 4

Planner Agent executes.

↓

Step 5

Coder Agent executes.

↓

Step 6

Tester Agent executes.

↓

Tests Pass?

YES → Reviewer Agent

NO → Debugger Agent

↓

Retry Count < 3

YES → Return to Coder

NO → Escalate Failure

↓

Reviewer Agent

↓

ZIP Generation

↓

Database Storage

↓

Completed

---

# 9. Functional Requirements

## FR-001

System shall accept natural language project requirements.

## FR-002

System shall generate unique run identifiers.

## FR-003

System shall execute the Research Agent.

## FR-004

System shall execute the Planner Agent.

## FR-005

System shall execute the Coder Agent.

## FR-006

System shall execute the Tester Agent.

## FR-007

System shall execute the Debugger Agent.

## FR-008

System shall execute the Reviewer Agent.

## FR-009

System shall generate downloadable ZIP files.

## FR-010

System shall store completed runs.

## FR-011

System shall maintain run history.

## FR-012

System shall provide execution logs.

## FR-013

System shall provide run status updates.

## FR-014

System shall support retry workflows.

## FR-015

System shall support project downloads.

---

# 10. Non-Functional Requirements

## Performance

NFR-001

API response time < 500ms.

NFR-002

Workflow startup time < 10 seconds.

---

## Reliability

NFR-003

System should complete the majority of valid runs successfully.

---

## Security

NFR-004

Generated code must never execute on the host machine.

---

## Availability

NFR-005

System should remain operational during normal workloads.

---

## Maintainability

NFR-006

All modules must remain independently maintainable.

---

## Observability

NFR-007

Every agent action must be logged.

---

# 11. Success Metrics

Business Metrics:

* Total Projects Generated
* Active Users
* Monthly Runs
* Retention Rate

Engineering Metrics:

* Run Success Rate
* Test Pass Rate
* Average Execution Time
* Average Retry Count
* ZIP Generation Success Rate

---

# 12. Constraints

Budget:

₹0

Only free-tier tools may be used.

---

LLM Access:

All models must be accessed through OpenRouter.

---

Sandbox:

Docker is mandatory.

---

Database:

PostgreSQL is mandatory.

---

Architecture:

Six-agent architecture is mandatory.

---

# End Of Part 1



# PART 2 — SYSTEM ARCHITECTURE & AGENT DESIGN

---

# 13. System Architecture Overview

The platform follows a Multi-Agent Architecture powered by LangGraph.

Each agent has a single responsibility and communicates through a centralized shared state object called AutoDevState.

The workflow is deterministic.

Agents execute in a predefined sequence and modify shared state as execution progresses.

---

# 14. High-Level Architecture

```text
User
 │
 ▼
Frontend (React + Vite)
 │
 ▼
FastAPI Backend
 │
 ▼
LangGraph Orchestrator
 │
 ▼
Research Agent
 │
 ▼
Planner Agent
 │
 ▼
Coder Agent
 │
 ▼
Tester Agent
 │
 ├── PASS ──► Reviewer Agent
 │
 └── FAIL ──► Debugger Agent
                    │
                    ▼
               Retry < 3
                    │
                    ▼
               Coder Agent
                    │
                    ▼
              Tester Agent
                    │
                    ▼
              Reviewer Agent
                    │
                    ▼
              ZIP Delivery
                    │
                    ▼
              PostgreSQL Storage
```

---

# 15. Core Architecture Principles

## Principle 1

Single Shared State

Every agent reads from and writes to the same state object.

No direct agent-to-agent communication is allowed.

Agents communicate only through AutoDevState.

---

## Principle 2

Deterministic Execution

Agent order must remain fixed.

Research

↓

Planner

↓

Coder

↓

Tester

↓

Debugger (if needed)

↓

Reviewer

---

## Principle 3

Isolated Execution

Generated code must never run on the host machine.

All code execution must occur inside Docker.

---

## Principle 4

Retry Safety

Infinite retry loops are prohibited.

Maximum retries = 3

---

## Principle 5

State Traceability

Every state update must be logged.

---

# 16. LangGraph Workflow Design

## Entry Node

Research Agent

---

## Intermediate Nodes

Planner Agent

Coder Agent

Tester Agent

Debugger Agent

Reviewer Agent

---

## Terminal Nodes

Completed

Failed

Escalated

---

## Workflow Logic

```text
Research
   ↓
Planner
   ↓
Coder
   ↓
Tester
   ↓
Tests Pass?

YES
 ↓
Reviewer
 ↓
Delivery
 ↓
Completed

NO
 ↓
Debugger
 ↓
Retry Count < 3 ?

YES
 ↓
Coder

NO
 ↓
Escalated
```

---

# 17. Shared State Design

The entire system revolves around a shared state object.

Name:

AutoDevState

---

## AutoDevState Schema

```python
class AutoDevState(TypedDict):

    # Identity

    run_id: str
    user_id: str

    # Input

    prd_text: str

    # Research

    research_output: dict

    # Planning

    task_plan: dict

    # Code Generation

    code_files: dict
    sandbox_folder: str

    # Testing

    test_code: str
    test_results: dict

    # Debugging

    retry_count: int
    error_trace: str

    # Review

    review_result: dict

    # Delivery

    download_url: str

    # Metadata

    status: str
    logs: list
    total_tokens: int
```

---

# 18. State Ownership Rules

Research Agent may modify:

* research_output

---

Planner Agent may modify:

* task_plan

---

Coder Agent may modify:

* code_files
* sandbox_folder

---

Tester Agent may modify:

* test_code
* test_results

---

Debugger Agent may modify:

* code_files
* retry_count
* error_trace

---

Reviewer Agent may modify:

* review_result
* download_url

---

All Agents may append logs.

---

# 19. Agent Specifications

---

## Agent 1 — Research Agent

### Purpose

Gather implementation knowledge before coding begins.

---

### Model

Gemma 4 31B

---

### Tools

Tavily

Firecrawl

BeautifulSoup

---

### Responsibilities

Search relevant technologies.

Read documentation.

Analyze frameworks.

Collect implementation references.

Generate structured research.

---

### Input

```json
{
  "prd_text": "..."
}
```

---

### Output

```json
{
  "tech_stack": [],
  "libraries": [],
  "implementation_notes": [],
  "api_docs": []
}
```

---

### Updates State

research_output

---

# Agent 2 — Planner Agent

### Purpose

Convert research into implementation blueprint.

---

### Model

Nemotron 3 Super

Fallback:

gpt-oss-120b

---

### Validation

Pydantic

---

### Responsibilities

Create file structure.

Define implementation order.

Identify dependencies.

Create development roadmap.

---

### Input

research_output

---

### Output

```json
{
  "folders": [],
  "files": [],
  "dependencies": [],
  "execution_order": []
}
```

---

### Updates State

task_plan

---

# Agent 3 — Coder Agent

### Purpose

Generate source code.

---

### Model

Poolside Laguna M.1

Fallback:

gpt-oss-120b

---

### Tools

os

pathlib

tempfile

---

### Responsibilities

Generate project files.

Generate application code.

Generate configuration files.

Follow planner instructions exactly.

---

### Growing Context Strategy

Every new file must receive context from all previously generated files.

This prevents import mismatches and architectural inconsistencies.

---

### Input

task_plan

---

### Output

code_files

---

### Updates State

code_files

sandbox_folder

---

# Agent 4 — Tester Agent

### Purpose

Validate generated code.

---

### Model

Llama 3.3 70B

---

### Tools

Pytest

Docker Sandbox

---

### Responsibilities

Generate tests.

Run tests.

Collect failures.

Generate reports.

---

### Input

code_files

---

### Output

```json
{
  "passed": true,
  "failed_tests": [],
  "logs": []
}
```

---

### Updates State

test_code

test_results

---

# Agent 5 — Debugger Agent

### Purpose

Repair failed code.

---

### Model

Nemotron 3 Super

Fallback:

gpt-oss-120b

---

### Validation

AST Parsing

---

### Responsibilities

Read failures.

Identify root cause.

Fix exactly one file.

Return modified code.

---

### Retry Policy

Maximum Retries = 3

---

### Input

error_trace

test_results

code_files

---

### Updates State

retry_count

error_trace

code_files

---

# Agent 6 — Reviewer Agent

### Purpose

Final quality validation.

---

### Model

Gemma 4 31B

---

### Tools

Ruff

ESLint

ZIP Generator

PostgreSQL

---

### Responsibilities

Run linting.

Review architecture.

Generate review report.

Package ZIP.

Store metadata.

---

### Output

```json
{
  "quality_score": 95,
  "issues": [],
  "recommendations": []
}
```

---

### Updates State

review_result

download_url

---

# 20. Agent Model Registry

```python
AGENT_MODELS = {

    "research":
        "google/gemma-4-31b",

    "planner":
        "nvidia/nemotron-3-super",

    "planner_fallback":
        "openai/gpt-oss-120b",

    "coder":
        "poolside/laguna-m1",

    "coder_fallback":
        "openai/gpt-oss-120b",

    "tester":
        "meta-llama/llama-3.3-70b",

    "debugger":
        "nvidia/nemotron-3-super",

    "debugger_fallback":
        "openai/gpt-oss-120b",

    "reviewer":
        "google/gemma-4-31b"
}
```

---

# End Of Part 2


# PART 3 — DATABASE, STORAGE, API CONTRACTS & DELIVERY ARCHITECTURE

---

# 21. Data Architecture

The platform requires persistent storage for:

* Users
* Project Runs
* Generated Files
* ZIP Packages
* Agent Logs
* Review Reports
* Execution Metrics

PostgreSQL is the primary database.

Redis is used for temporary workflow coordination and caching.

---

# 22. Database Design

## Database Name

```text
agentic_platform
```

---

# 23. Core Database Tables

## users

Stores user account information.

### Fields

```sql
id UUID PRIMARY KEY

email VARCHAR(255) UNIQUE NOT NULL

password_hash TEXT NOT NULL

created_at TIMESTAMP

updated_at TIMESTAMP
```

---

## project_runs

Stores every generated project execution.

### Fields

```sql
id UUID PRIMARY KEY

run_id VARCHAR(255) UNIQUE

user_id UUID

status VARCHAR(50)

prd_text TEXT

started_at TIMESTAMP

completed_at TIMESTAMP

created_at TIMESTAMP
```

---

## generated_projects

Stores generated project metadata.

### Fields

```sql
id UUID PRIMARY KEY

run_id VARCHAR(255)

project_name VARCHAR(255)

zip_path TEXT

download_url TEXT

created_at TIMESTAMP
```

---

## generated_files

Stores generated source files.

### Fields

```sql
id UUID PRIMARY KEY

run_id VARCHAR(255)

file_path TEXT

file_content TEXT

created_at TIMESTAMP
```

---

## agent_logs

Stores execution logs.

### Fields

```sql
id UUID PRIMARY KEY

run_id VARCHAR(255)

agent_name VARCHAR(100)

message TEXT

log_level VARCHAR(20)

created_at TIMESTAMP
```

---

## review_reports

Stores reviewer outputs.

### Fields

```sql
id UUID PRIMARY KEY

run_id VARCHAR(255)

quality_score INTEGER

report JSONB

created_at TIMESTAMP
```

---

## execution_metrics

Stores observability data.

### Fields

```sql
id UUID PRIMARY KEY

run_id VARCHAR(255)

total_tokens INTEGER

execution_time_seconds INTEGER

retry_count INTEGER

created_at TIMESTAMP
```

---

# 24. Database Relationships

```text
users
 │
 └── project_runs
          │
          ├── generated_projects
          │
          ├── generated_files
          │
          ├── review_reports
          │
          ├── execution_metrics
          │
          └── agent_logs
```

---

# 25. Run Status Lifecycle

Every run must have exactly one status.

Valid statuses:

```text
PENDING

RESEARCHING

PLANNING

CODING

TESTING

DEBUGGING

REVIEWING

DELIVERING

COMPLETED

FAILED

ESCALATED
```

---

# 26. Redis Usage

Redis is used for:

* Workflow coordination
* Temporary state caching
* Pub/Sub events
* Queue communication

Redis must never be the permanent source of truth.

PostgreSQL remains the permanent source of truth.

---

# 27. Project Storage Strategy

Generated projects must be stored after successful completion.

Storage includes:

* Generated source files
* ZIP package
* Review report
* Metrics
* Logs

---

# 28. ZIP Delivery Architecture

After Reviewer Agent completes:

### Step 1

Collect all generated files.

---

### Step 2

Create project directory.

---

### Step 3

Generate ZIP archive.

---

### Step 4

Store ZIP metadata.

---

### Step 5

Generate download URL.

---

### Step 6

Persist into PostgreSQL.

---

# 29. API Architecture

Backend Framework:

```text
FastAPI
```

All APIs are REST APIs.

Response format must be JSON.

---

# 30. API Versioning

Base URL:

```text
/api/v1
```

Example:

```text
/api/v1/projects
```

---

# 31. Create Project API

## Endpoint

```http
POST /api/v1/projects/create
```

---

### Request

```json
{
  "prd": "Build a CRM using React and FastAPI"
}
```

---

### Response

```json
{
  "success": true,
  "run_id": "run_123456"
}
```

---

# 32. Get Run Status API

## Endpoint

```http
GET /api/v1/projects/{run_id}
```

---

### Response

```json
{
  "run_id": "run_123456",
  "status": "CODING"
}
```

---

# 33. Get Run Logs API

## Endpoint

```http
GET /api/v1/projects/{run_id}/logs
```

---

### Response

```json
{
  "logs": [
    {
      "agent": "Research",
      "message": "Research completed"
    }
  ]
}
```

---

# 34. Download Project API

## Endpoint

```http
GET /api/v1/projects/{run_id}/download
```

---

### Response

```json
{
  "download_url": "/downloads/project.zip"
}
```

---

# 35. Project History API

## Endpoint

```http
GET /api/v1/projects/history
```

---

### Response

```json
{
  "projects": []
}
```

---

# 36. Health Check API

## Endpoint

```http
GET /api/v1/health
```

---

### Response

```json
{
  "status": "healthy"
}
```

---

# 37. Agent Log API

## Endpoint

```http
GET /api/v1/agents/logs/{run_id}
```

---

### Response

```json
{
  "agent_logs": []
}
```

---

# 38. Error Response Standard

Every API must follow this format.

```json
{
  "success": false,
  "error": {
    "code": "RUN_NOT_FOUND",
    "message": "Run does not exist"
  }
}
```

---

# 39. Pagination Standard

List APIs must support:

```text
?page=1

&limit=20
```

---

# 40. Authentication Strategy

Version 1:

Authentication optional during initial development.

Future versions:

* JWT Authentication
* Refresh Tokens
* Role-Based Access

---

# 41. Delivery Requirements

A project is deliverable only when:

✓ Research Completed

✓ Planning Completed

✓ Code Generated

✓ Tests Executed

✓ Review Completed

✓ ZIP Generated

✓ Metadata Stored

✓ Download URL Generated

---

# 42. Delivery Artifacts

Final generated package must contain:

```text
project/
│
├── source_code
│
├── tests
│
├── requirements.txt
│
├── README.md
│
├── configuration files
│
└── generated documentation
```

---

# 43. Data Retention

Store:

* Runs
* Logs
* ZIP Metadata
* Reports

until manually deleted.

---

# End Of Part 3


# PART 4 — FRONTEND, BACKEND, SANDBOX, SECURITY & DEPLOYMENT

---

# 44. Frontend Architecture

## Technology Stack

Frontend Framework:

```text
React
```

Build Tool:

```text
Vite
```

Language:

```text
JavaScript
```

HTTP Client:

```text
Axios
```

Routing:

```text
React Router
```

State Management:

```text
React Context API
```

---

# 45. Frontend Goals

The frontend must provide a simple dashboard where users can:

* Submit requirements
* Start project generation
* Monitor progress
* View logs
* Download projects
* Access project history

The UI must prioritize simplicity and visibility.

---

# 46. Frontend Pages

## Dashboard

Purpose:

Main project creation page.

Components:

```text
Create Project Form

Recent Runs

Statistics Cards

Run Status Overview
```

---

## Run Details Page

Purpose:

View execution progress.

Components:

```text
Current Status

Agent Timeline

Execution Logs

Retry Count

Review Results

Download Button
```

---

## Project History Page

Purpose:

Access previous projects.

Components:

```text
Project List

Search

Filter

Download History
```

---

## Settings Page

Purpose:

Manage configuration.

Components:

```text
API Configuration

Environment Settings

User Preferences
```

---

# 47. Frontend Folder Structure

```text
frontend/

├── src/

│   ├── pages/

│   │   ├── Dashboard.jsx

│   │   ├── RunDetails.jsx

│   │   ├── History.jsx

│   │   └── Settings.jsx

│   ├── components/

│   ├── services/

│   ├── hooks/

│   ├── context/

│   ├── routes/

│   └── utils/

├── public/

└── package.json
```

---

# 48. Backend Architecture

Backend Framework:

```text
FastAPI
```

Language:

```text
Python 3.11
```

Architecture Style:

```text
Service-Oriented Modular Architecture
```

---

# 49. Backend Responsibilities

The backend must:

* Accept PRDs
* Create workflows
* Manage LangGraph execution
* Store results
* Manage ZIP delivery
* Handle logs
* Expose APIs

---

# 50. Backend Folder Structure

```text
backend/

├── agents/

│   ├── research_agent.py

│   ├── planner_agent.py

│   ├── coder_agent.py

│   ├── tester_agent.py

│   ├── debugger_agent.py

│   └── reviewer_agent.py

│

├── graph/

│   ├── state.py

│   └── orchestrator.py

│

├── tools/

│   ├── smart_scraper/

│   ├── docker_runner/

│   ├── smart_linter/

│   ├── zip_delivery/

│   └── db_delivery/

│

├── api/

│   ├── main.py

│   └── routes/

│

├── db/

│   ├── models.py

│   └── database.py

│

└── config.py
```

---

# 51. LangGraph Responsibilities

LangGraph is the orchestration engine.

Responsibilities:

* Agent sequencing
* State transitions
* Conditional branching
* Retry handling
* Workflow completion

LangGraph is the central brain of execution.

---

# 52. Docker Sandbox Architecture

Generated code must never run directly on the host system.

All execution must happen inside isolated Docker containers.

---

## Sandbox Goals

Provide:

* Isolation
* Safety
* Resource limits
* Automatic cleanup

---

# 53. Sandbox Rules

Mandatory Rules:

```text
No Internet Access

256 MB RAM

1 CPU

30 Second Timeout

Temporary File System

Read-Only Host Access

Container Auto Destruction
```

---

# 54. Sandbox Workflow

```text
Generate Project

↓

Create Temporary Workspace

↓

Create Docker Container

↓

Mount Project

↓

Execute Tests

↓

Capture Output

↓

Store Results

↓

Destroy Container
```

---

# 55. Docker Container Requirements

Container must:

* Start on demand
* Be disposable
* Have no external network access
* Be automatically removed

Every run gets a fresh container.

No container reuse.

---

# 56. Security Architecture

Security is mandatory.

Generated code must be treated as untrusted.

---

# 57. Security Principles

## Principle 1

Least Privilege

Agents receive only required permissions.

---

## Principle 2

Isolation First

Generated code cannot access host resources.

---

## Principle 3

Input Validation

All user inputs must be validated.

---

## Principle 4

Secret Protection

API keys must never appear in logs.

---

# 58. Security Requirements

## SEC-001

Environment variables stored in .env.

---

## SEC-002

Secrets never committed to Git.

---

## SEC-003

All inputs validated through Pydantic.

---

## SEC-004

Docker execution mandatory.

---

## SEC-005

SQL injection prevention required.

---

## SEC-006

Path traversal prevention required.

---

## SEC-007

Container isolation required.

---

## SEC-008

Generated code treated as untrusted.

---

# 59. Logging Architecture

Every major event must be logged.

---

## Log Categories

```text
System Logs

Agent Logs

API Logs

Database Logs

Sandbox Logs

Error Logs
```

---

# 60. Agent Logging Requirements

Each agent must log:

```text
Agent Started

Agent Finished

Tokens Used

Execution Duration

Errors

Outputs Generated
```

---

# 61. Observability Requirements

Track:

```text
Run Duration

Agent Duration

Retry Count

Failure Rate

Success Rate

Token Usage
```

---

# 62. Error Handling Architecture

All failures must be recoverable where possible.

The platform must fail gracefully.

---

# 63. Error Categories

## Research Errors

Examples:

```text
Search Failure

Document Parsing Failure
```

---

## Planning Errors

Examples:

```text
Invalid Plan

Schema Validation Failure
```

---

## Coding Errors

Examples:

```text
Code Generation Failure

Missing File
```

---

## Testing Errors

Examples:

```text
Failed Tests

Import Errors

Syntax Errors
```

---

## Database Errors

Examples:

```text
Connection Failure

Insert Failure
```

---

# 64. Retry Policies

Research Agent:

```text
1 Retry
```

---

Planner Agent:

```text
1 Retry
```

---

Coder Agent:

```text
1 Retry
```

---

Tester Agent:

```text
No Retry
```

---

Debugger Agent:

```text
Maximum 3 Attempts
```

---

Reviewer Agent:

```text
No Retry
```

---

# 65. Escalation Rules

Escalation occurs when:

```text
Debugger Retries > 3
```

Result:

```text
Run Status = ESCALATED
```

---

# 66. Deployment Architecture

Frontend:

```text
Vercel
```

---

Backend:

```text
Railway
```

---

Database:

```text
PostgreSQL Docker Container
```

---

Administration:

```text
pgAdmin Docker Container
```

---

Cache:

```text
Redis Docker Container
```

---

# 67. Environment Variables

Required Variables:

```bash
OPENROUTER_API_KEY=

TAVILY_API_KEY=

FIRECRAWL_API_KEY=

LANGSMITH_API_KEY=

POSTGRES_USER=

POSTGRES_PASSWORD=

POSTGRES_DB=

DATABASE_URL=

REDIS_URL=
```

---

# 68. Infrastructure Principles

Infrastructure must remain:

* Simple
* Low cost
* Maintainable
* Scalable

Budget constraint:

```text
₹0
```

Only free-tier services are permitted.

---

# End Of Part 4

# PART 5 — AI RULEBOOK, CODING STANDARDS, DEVELOPMENT RULES & DEFINITION OF DONE

---

# 69. AI RULEBOOK

## Purpose

This section contains mandatory instructions for all AI systems working on this repository.

Examples:

* Antigravity
* Claude
* ChatGPT
* Cursor
* Windsurf
* OpenHands
* Future AI Coding Agents

These instructions have higher priority than suggestions generated by AI.

---

# 70. Source Of Truth

This document is the official source of truth.

AI systems must:

* Follow this document
* Continue from existing implementation
* Respect all architectural decisions

AI systems must never redesign the project.

---

# 71. Architecture Protection Rules

## RULE-001

Never replace LangGraph.

---

## RULE-002

Never replace FastAPI.

---

## RULE-003

Never replace PostgreSQL.

---

## RULE-004

Never replace Redis.

---

## RULE-005

Never replace Docker Sandbox.

---

## RULE-006

Never replace React + Vite.

---

## RULE-007

Never replace OpenRouter.

---

## RULE-008

Never introduce paid services.

Budget must remain:

```text
₹0
```

---

# 72. Agent Rules

The platform contains exactly six agents.

Allowed Agents:

```text
Research Agent

Planner Agent

Coder Agent

Tester Agent

Debugger Agent

Reviewer Agent
```

---

Forbidden:

```text
Architect Agent

Manager Agent

Coordinator Agent

Delivery Agent

Supervisor Agent
```

Unless explicitly approved by the project owner.

---

# 73. Workflow Rules

Mandatory Execution Order:

```text
Research

↓

Planner

↓

Coder

↓

Tester

↓

Debugger (if required)

↓

Reviewer
```

AI must never change workflow order.

---

# 74. State Management Rules

AutoDevState is mandatory.

AI systems must never:

* Rename fields
* Remove fields
* Change field types

without explicit approval.

---

## Approved AutoDevState

```python
class AutoDevState(TypedDict):

    run_id: str
    user_id: str

    prd_text: str

    research_output: dict

    task_plan: dict

    code_files: dict
    sandbox_folder: str

    test_code: str
    test_results: dict

    retry_count: int
    error_trace: str

    review_result: dict
    download_url: str

    status: str
    logs: list
    total_tokens: int
```

---

# 75. Coding Rules

## Backend Rules

Language:

```text
Python 3.11
```

Requirements:

* Type hints mandatory
* Pydantic validation mandatory
* Async APIs preferred
* Clear separation of concerns
* Modular design

---

## Frontend Rules

Framework:

```text
React + Vite
```

Requirements:

* Functional Components
* Hooks Only
* No Class Components
* Reusable Components
* Clean Folder Structure

---

# 76. File Generation Rules

When generating code:

AI must generate complete files.

Never generate:

```text
Partial snippets

Pseudo code

Placeholder implementations
```

unless explicitly requested.

---

# 77. Testing Rules

Every generated project must include tests.

Minimum Requirements:

* Unit Tests
* Basic Integration Tests

Testing Framework:

```text
pytest
```

---

# 78. Sandbox Rules

Generated code must never execute on host machine.

Mandatory:

```text
Docker Sandbox
```

Requirements:

```text
No Internet

256MB RAM

1 CPU

30 Second Timeout
```

---

# 79. Debugger Rules

Debugger may:

* Modify one file at a time
* Fix specific errors

Debugger may not:

* Rewrite entire project
* Redesign architecture

---

## Retry Policy

Maximum retries:

```text
3
```

---

## Escalation

If retries exceed limit:

```text
Run Status = ESCALATED
```

---

# 80. Logging Rules

Every agent execution must create logs.

Required Log Events:

```text
Started

Completed

Failed

Retry

Escalated
```

---

# 81. Security Rules

Generated code must be treated as untrusted.

Required:

* Input validation
* Secret protection
* Docker isolation
* SQL injection protection
* Path traversal protection

---

Forbidden:

* Hardcoded secrets
* API keys in source code
* Secrets in logs

---

# 82. Database Rules

Database:

```text
PostgreSQL
```

Required:

* SQLAlchemy
* Alembic migrations
* Indexed primary keys

---

AI must never:

* Replace PostgreSQL
* Introduce another database

without approval.

---

# 83. OpenRouter Rules

All models must be accessed through:

```text
OpenRouter
```

Single API key strategy is mandatory.

---

Approved Models:

```text
Research:
Gemma 4 31B

Planner:
Nemotron 3 Super

Planner Fallback:
gpt-oss-120b

Coder:
Poolside Laguna M.1

Coder Fallback:
gpt-oss-120b

Tester:
Llama 3.3 70B

Debugger:
Nemotron 3 Super

Debugger Fallback:
gpt-oss-120b

Reviewer:
Gemma 4 31B
```

---

# 84. Development Roadmap

## Phase 1

Foundation

Tasks:

* Repository setup
* FastAPI setup
* PostgreSQL setup
* Redis setup
* LangGraph setup

Goal:

Working infrastructure.

---

## Phase 2

Core Agent Development

Tasks:

* Research Agent
* Planner Agent
* Coder Agent
* Tester Agent
* Debugger Agent
* Reviewer Agent

Goal:

Complete workflow.

---

## Phase 3

Workflow Integration

Tasks:

* LangGraph orchestration
* State management
* Retry handling

Goal:

End-to-end execution.

---

## Phase 4

Frontend Dashboard

Tasks:

* Dashboard
* Run monitoring
* Logs
* Downloads

Goal:

Usable UI.

---

## Phase 5

Observability

Tasks:

* LangSmith integration
* Metrics
* Monitoring

Goal:

Production visibility.

---

## Phase 6

MVP Release

Tasks:

* Final testing
* Bug fixes
* Documentation

Goal:

Public MVP.

---

# 85. Definition Of Done

A project generation run is considered complete only when all conditions below are satisfied.

Required:

```text
✓ Research Completed

✓ Planning Completed

✓ Code Generated

✓ Tests Generated

✓ Tests Executed

✓ Debugging Completed (if required)

✓ Review Completed

✓ ZIP Generated

✓ Download URL Generated

✓ Database Entry Created

✓ Logs Stored

✓ Metrics Stored
```

---

# 86. Failure Conditions

A run is considered failed if:

```text
Research Failure

Planning Failure

Code Generation Failure

Database Failure

ZIP Generation Failure
```

and recovery is impossible.

---

# 87. Escalation Conditions

Escalation occurs when:

```text
Debugger Retry Count > 3
```

Result:

```text
Status = ESCALATED
```

---

# 88. Future Enhancements

Future versions may support:

* Team Workspaces
* Multi-User Collaboration
* GitHub Integration
* CI/CD Generation
* Infrastructure Generation
* AI Application Generation
* Mobile App Generation
* Voice-Based Requirements
* Enterprise Analytics

These features are not part of Version 1.

---

# 89. Final Project Principles

Principle 1:

Automation First

---

Principle 2:

Security By Default

---

Principle 3:

Deterministic Execution

---

Principle 4:

Observability Everywhere

---

Principle 5:

Cost Efficiency

---

Principle 6:

AI-Native Development

---

# 90. Final Instruction For AI Systems

If an AI system is contributing to this project:

1. Read this entire document first.
2. Follow all architecture decisions.
3. Continue from existing progress.
4. Never redesign the platform.
5. Never replace approved technologies.
6. Never exceed budget constraints.
7. Generate production-quality code.
8. Respect AutoDevState.
9. Respect the six-agent workflow.
10. Treat this document as the primary source of truth.

---

# END OF MASTER PROJECT SPECIFICATION

# VERSION 1.0
