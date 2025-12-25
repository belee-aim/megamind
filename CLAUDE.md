# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

This project uses **uv** as its dependency manager. Install it from https://docs.astral.sh/uv/getting-started/installation/

```bash
# Create virtual environment and install dependencies
uv venv
uv sync

# Install package in editable mode (required for langgraph dev)
uv pip install -e .
```

## Common Commands

### Running the Application

```bash
# Development mode (FastAPI with hot reload)
uv run fastapi dev src/megamind/main.py

# LangGraph Studio (visual graph debugging)
langgraph dev
```

### Testing

```bash
# Run tests
pytest tests/

# Test specific modules
pytest tests/test_specific_module.py
```

### Docker

```bash
# Build with cache optimization
docker buildx build --mount=type=cache,target=/root/.cache/pypoetry -t megamind .

# Run container
docker run --env-file .env -p 8000:8000 megamind
```

## Architecture Overview

### LangGraph Subagent System

This is a FastAPI microservice that uses **LangGraph** to build stateful, multi-agent workflows with a **subagent architecture**. The system uses an orchestrator that delegates work to specialist subagents via a `task` tool.

**Critical files:**

- `src/megamind/main.py`: FastAPI entry point, graph initialization, API endpoints
- `src/megamind/graph/workflows/subagent_graph.py`: Main subagent-based workflow definition
- `src/megamind/graph/middleware/subagent_middleware.py`: SubAgentMiddleware for task delegation
- `src/megamind/graph/middleware/consent_middleware.py`: Human-in-the-loop consent for state-changing operations
- `src/megamind/prompts/subagent_prompts.py`: Prompts for orchestrator and all subagents
- `src/megamind/prompts/megamind.py`: Base system prompt builder
- `src/megamind/graph/tools/`: Tool definitions (titan_knowledge, zep_graph, subagent, minion)
- `src/megamind/graph/states.py`: State schemas for graphs
- `langgraph.json`: LangGraph configuration

### Subagent Architecture

The system uses a **subagent pattern** where the orchestrator has NO direct tools. Instead, it delegates ALL work to specialist subagents via the `task` tool.

**Subagent Types:**

| Subagent     | Role                                       | Tools                                                                                                                   |
| ------------ | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `knowledge`  | **SOLE GATEWAY** for all knowledge queries | `search_erpnext_knowledge`, `search_business_workflows`, `search_employees`, `search_user_knowledge`, `search_document` |
| `report`     | Report execution and export                | MCP tools: `run_query_report`, `get_report_meta`, `export_report`, `get_financial_statements`, etc.                     |
| `operations` | Document CRUD and workflows                | MCP tools: `create_document`, `get_document`, `update_document`, `apply_workflow_action`, schema tools, etc.            |

**Knowledge-First Pattern:**

The orchestrator MUST consult the knowledge subagent BEFORE delegating to other subagents. This ensures:

- Required field validation before operations
- Proper workflow understanding before report generation
- Best practices applied to all actions

```
User Request → Orchestrator → Knowledge Subagent (FIRST) → Report/Operations Subagent → Response
```

### API Endpoints and Graph Mapping

**Endpoints in `main.py`:**

- `/api/v1/stream/{thread}` → `subagent_graph` (main orchestrator + subagents)
- `/api/v1/thread/{thread_id}/state` → Check interrupt status and pending tool calls
- `/api/v1/threads/{thread_id}/history` → Retrieve conversation history
- `/api/v1/reconciliation/merge` → Utility endpoint (Pandas processing, no graph)
- `/api/v1/role-generation` → Role permission generation (non-streaming)

**Endpoints via routers:**

- `/api/v1/wiki/stream/{thread_id}` → `minion_router` → document_search_graph
- `/api/v1/document/stream/{thread_id}` → `minion_router` → document_search_graph
- `/api/v1/document-extraction/*` → `document_extraction_router`
- `/api/v1/zep/*` → `zep_router` → Zep memory management
- `/api/v1/subagents/*` → `subagents_router` → Deep analyst subagent endpoints

### Middleware System

**SubAgentMiddleware** (`src/megamind/graph/middleware/subagent_middleware.py`):

- Creates `task` tool for delegating to specialist subagents
- Manages subagent specifications (SubAgent) and pre-compiled agents (CompiledSubAgent)
- Injects subagent instructions into orchestrator's system prompt
- Handles async subagent invocations with proper state management

**ConsentMiddleware** (`src/megamind/graph/middleware/consent_middleware.py`):

- Interrupts execution for state-changing MCP tool calls (create, update, delete)
- Human-in-the-loop approval pattern
- Used by operations subagent for write operations

**MCPTokenMiddleware** (`src/megamind/graph/middleware/mcp_token_middleware.py`):

- Injects access tokens into MCP tool calls
- Enables authenticated ERPNext operations

### State Management and Persistence

**Checkpointing (AsyncPostgresSaver):**

- Thread state persisted in PostgreSQL via Supabase
- Config includes `thread_id`, `company`, `current_datetime`, user context
- State retrieved with `checkpointer.aget(config)`

**Zep Knowledge Graph:**

- Optional integration for fact extraction and semantic memory
- User and thread management via `zep_client`
- Messages synced for automatic knowledge extraction

### Database Connection Pool

Uses **AsyncConnectionPool** from psycopg with configurable settings:

```bash
DB_POOL_MIN_SIZE=2          # Minimum connections
DB_POOL_MAX_SIZE=100        # Maximum connections
DB_POOL_MAX_WAITING=50      # Max queued requests
DB_POOL_MAX_LIFETIME=1800.0 # Connection recycling (30 min)
DB_POOL_MAX_IDLE=180.0      # Idle timeout (3 min)
DB_POOL_TIMEOUT=30.0        # Acquisition timeout
```

### External Service Integration

**Titan (ERPNext Knowledge Base):**

- `src/megamind/clients/titan_client.py`: ERPNext knowledge search and embeddings
- Tools: `search_erpnext_knowledge`, `get_erpnext_knowledge_by_id`
- Config: `TITAN_API_URL`

**Zep (Knowledge Graph):**

- `src/megamind/clients/zep_client.py`: Semantic memory and fact extraction
- Tools: `search_business_workflows`, `search_employees`, `search_user_knowledge`
- Config: `ZEP_API_KEY`, `ZEP_API_URL`

**Frappe/ERPNext:**

- `src/megamind/clients/frappe_client.py`: ERPNext API client
- Uses Bearer token authentication from request headers
- Gets company, user info, department context

**MCP Servers:**

- `src/megamind/clients/mcp_client_manager.py`: Manages MCP server connections
- Frappe MCP server for ERPNext operations
- Config: `FRAPPE_MCP_SERVER_PATH`

### Graph Workflows

**subagent_graph** (`src/megamind/graph/workflows/subagent_graph.py`):

- Main workflow using SubAgentMiddleware pattern
- Orchestrator delegates to knowledge, report, operations subagents
- Knowledge subagent is sole gateway for all knowledge queries
- ConsentMiddleware on operations subagent for write approvals

**document_search_graph** (`src/megamind/graph/workflows/document_search_graph.py`):

- Single-node workflow for document search
- Uses `search_document` tool via minion_tools

**document_extraction_graph** (`src/megamind/graph/workflows/document_extraction_graph.py`):

- Extracts structured data from documents
- Used by document extraction API endpoints

### Configuration

Environment variables (see `.env.example`):

```bash
# LLM Provider
GOOGLE_API_KEY=             # Google Gemini API key
PROVIDER=google             # LLM provider (google)

# ERPNext/Frappe
FRAPPE_URL=                 # ERPNext instance URL
FRAPPE_MCP_SERVER_PATH=     # Path to MCP server

# Database
SUPABASE_URL=               # Supabase project URL
SUPABASE_KEY=               # Supabase anon key
SUPABASE_DB_URL=            # PostgreSQL connection string

# External Services
TITAN_API_URL=              # Titan knowledge service
ZEP_API_KEY=                # Zep Cloud API key
MINION_API_URL=             # Minion doc search service

# Observability
SENTRY_DSN=                 # Sentry error tracking
LANGSMITH_API_KEY=          # LangSmith tracing (optional)
```

Settings loaded via `src/megamind/utils/config.py` using pydantic-settings.

## Working with This Codebase

### Adding a New Subagent

1. Define subagent prompt in `src/megamind/prompts/subagent_prompts.py`
2. Create tool set function in `src/megamind/graph/workflows/subagent_graph.py` (e.g., `get_new_subagent_tools()`)
3. Add SubAgent spec to `build_subagent_graph()`:
   ```python
   SubAgent(
       name="new_subagent",
       description="Description for orchestrator to know when to use",
       system_prompt=NEW_SUBAGENT_PROMPT,
       tools=get_new_subagent_tools(),
   )
   ```
4. Update orchestrator prompt in `subagent_prompts.py` to include new subagent

### Modifying Prompts

**Orchestrator prompt:**

- Edit `ORCHESTRATOR_PROMPT` in `src/megamind/prompts/subagent_prompts.py`
- Dynamic context (company, datetime, user) injected at runtime

**Subagent prompts:**

- Edit corresponding `*_PROMPT` variables in `src/megamind/prompts/subagent_prompts.py`
- `KNOWLEDGE_ANALYST_PROMPT`, `OPERATIONS_SPECIALIST_PROMPT`, `REPORT_SPECIALIST_PROMPT`

**Base prompts:**

- Edit `src/megamind/prompts/megamind.py` for base system prompt
- Used by `build_system_prompt()` function

### Adding Tools

1. Define tool in appropriate file under `src/megamind/graph/tools/`
2. Import in `subagent_graph.py` and add to correct subagent's tool getter function
3. If tool needs consent, add to ConsentMiddleware's interrupt list

**Tool files:**

- `titan_knowledge_tools.py`: ERPNext knowledge search tools
- `zep_graph_tools.py`: Zep knowledge graph tools
- `minion_tools.py`: Document search tools
- `subagent_tools.py`: Subagent-specific tools

### Adding New API Endpoints

**Option A: Add to main.py**

```python
@app.post("/api/v1/your-endpoint")
async def your_endpoint(request: Request, request_data: YourRequest):
    graph = request.app.state.subagent_graph
    # ... implementation
```

**Option B: Create separate router (recommended)**

1. Create `src/megamind/api/v1/your_feature.py`:

   ```python
   from fastapi import APIRouter
   router = APIRouter()

   @router.post("/your-feature")
   async def your_feature(...):
       ...
   ```

2. Register in `main.py`:
   ```python
   from megamind.api.v1.your_feature import router as your_feature_router
   app.include_router(your_feature_router, prefix="/api/v1", tags=["Your Feature"])
   ```

### Graph Execution Flow

1. Request hits `/api/v1/stream/{thread}` with Bearer token
2. `_handle_chat_stream()` extracts token, gets user context from Frappe
3. Builds config with thread_id, company, datetime, user info
4. Adds user message to inputs
5. Invokes `subagent_graph` via `stream_response_with_ping()`
6. **Orchestrator** receives request, consults knowledge subagent first
7. **Knowledge subagent** retrieves relevant context (schemas, workflows, docs)
8. **Orchestrator** delegates to report/operations subagent with knowledge context
9. **Operations subagent** may trigger ConsentMiddleware for write operations
10. User approves/rejects → execution continues/aborts
11. Stream events back as SSE with subagent attribution

### Project Structure

```
src/megamind/
├── main.py                     # FastAPI entry point
├── api/v1/                     # API routers
│   ├── minion.py              # Wiki/document search endpoints
│   ├── document_extraction.py # Document extraction endpoints
│   ├── zep.py                 # Zep memory endpoints
│   └── subagents.py           # Deep analyst endpoints
├── clients/                    # External service clients
│   ├── frappe_client.py       # ERPNext API
│   ├── titan_client.py        # Knowledge search
│   ├── zep_client.py          # Knowledge graph
│   └── mcp_client_manager.py  # MCP server management
├── graph/
│   ├── workflows/             # Graph definitions
│   │   ├── subagent_graph.py # Main orchestrator workflow
│   │   ├── document_search_graph.py
│   │   └── document_extraction_graph.py
│   ├── middleware/            # Agent middleware
│   │   ├── subagent_middleware.py   # Task delegation
│   │   ├── consent_middleware.py    # Human-in-the-loop
│   │   └── mcp_token_middleware.py  # Token injection
│   ├── nodes/                 # Node implementations
│   ├── tools/                 # Tool definitions
│   ├── states.py             # State schemas
│   └── schemas.py            # Pydantic models
├── prompts/                   # Prompt definitions
│   ├── subagent_prompts.py   # Orchestrator + subagent prompts
│   ├── megamind.py           # Base system prompt
│   └── ...
├── models/                    # Request/response models
├── utils/                     # Utilities (config, logging, streaming)
└── configuration.py           # Runtime configuration
```
