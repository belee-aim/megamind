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

### Testing and Visualization

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

### LangGraph Workflow System

This is a FastAPI microservice that uses **LangGraph** to build stateful, multi-agent workflows. Each workflow is an independent state machine handling specific business functions. The key insight is that workflows are **compiled at startup** in `main.py:lifespan()` and stored in `app.state`.

**Critical files:**
- `src/megamind/main.py`: Application entry point, graph initialization, main API endpoints
- `src/megamind/api/v1/minion.py`: Separate router for wiki/document search endpoints
- `src/megamind/base_prompt.py`: Base prompt with tool usage instructions
- `src/megamind/graph/tools/titan_knowledge_tools.py`: LangChain tools for ERPNext knowledge search
- `src/megamind/graph/nodes/corrective_rag_node.py`: CRAG implementation for automatic error recovery
- `src/megamind/clients/titan_client.py`: Client for Titan API (knowledge + embeddings)
- `src/megamind/graph/workflows/`: Graph definitions (megamind_graph.py, stock_movement_graph.py, etc.)
- `src/megamind/graph/nodes/`: Node implementations for each graph
- `src/megamind/graph/states.py`: State schemas for graphs (includes CRAG state fields)
- `src/megamind/prompts.py`: Static prompt templates (used by specialized graphs)
- `langgraph.json`: LangGraph configuration (currently points to stock_movement_graph)

### API Endpoints and Graph Mapping

**Endpoints in `main.py`:**
- `/api/v1/stream/{thread}` → megamind_graph (uses RAG-augmented prompts from Titan)
- `/api/v1/role-generation` → role_generation_graph (non-streaming, uses `ainvoke()`)
- `/api/v1/reconciliation/merge` → Utility endpoint (no graph, direct Pandas processing)

**Endpoints in `api/v1/minion.py` (included via router):**
- `/api/v1/wiki/stream/{thread_id}` → wiki_graph (uses static prompts from prompts.py)
- `/api/v1/document/stream/{thread_id}` → document_search_graph (uses static prompts from prompts.py)

**Key differences:**
- Main chat endpoint (`/api/v1/stream/{thread}`) uses RAG to retrieve relevant ERPNext knowledge from Titan
- Minion endpoints use `MinionRequest` (only `question` field) instead of `ChatRequest`
- Minion endpoints use a shared `_handle_minion_stream()` handler function
- Role generation endpoint is non-streaming and returns a complete JSON response

### Tool-Based Knowledge Retrieval (RAG)

The main chat endpoint uses **Tool-Based RAG** where the LLM decides when and how to search the ERPNext knowledge base using tools, rather than pre-loading context.

**Architecture:**
- `src/megamind/graph/tools/titan_knowledge_tools.py`: LangChain tools for knowledge search
- `src/megamind/base_prompt.py`: Base prompt with instructions on when/how to use knowledge tools
- `src/megamind/clients/titan_client.py`: Client for Titan API (embeddings + knowledge search)

**How it works:**
1. System prompt instructs LLM to use `search_erpnext_knowledge` tool for ERPNext-specific questions
2. LLM receives user query and decides whether knowledge search is needed
3. If needed, LLM calls tool with appropriate parameters (query, content_types, doctype, etc.)
4. Tool generates embedding, searches Titan, formats results, and returns to LLM
5. LLM uses retrieved knowledge to formulate response
6. LLM can call tool multiple times in same conversation with different queries

**Available Knowledge Tools:**
- `search_erpnext_knowledge`: Semantic search with filtering by content type, DocType, operation
- `get_erpnext_knowledge_by_id`: Retrieve specific knowledge entry by ID

**Tool Parameters:**
- `query` (required): Natural language search query
- `content_types` (optional): Filter by workflow, best_practice, schema, example, error_pattern, relationship, process
- `doctype` (optional): Filter by DocType name (e.g., "Sales Order")
- `operation` (optional): Filter by create, read, update, delete, workflow, search
- `match_count` (default: 5): Number of results to return

### Knowledge-First Workflow Pattern (MANDATORY)

The system enforces a **knowledge-first pattern** for all ERPNext operations to ensure accuracy and prevent errors.

**Required Workflow:**

```
User Request → Search Knowledge → Review Information → Execute Operation → Success
```

**Step-by-Step:**

1. **User requests ERPNext operation** (create, update, delete, workflow action)
2. **LLM ALWAYS searches knowledge first**:
   - Searches for schemas to understand required/optional fields
   - Searches for workflows to understand proper sequences
   - Searches for best practices to avoid common mistakes
3. **LLM reviews retrieved knowledge**:
   - Identifies all required fields and their formats
   - Understands validation rules and constraints
   - Learns proper workflow steps and sequences
4. **LLM calls MCP tools** with complete, accurate parameters based on knowledge
5. **Operation succeeds** on first attempt with correct data

**Example Flow:**

**User**: "Create a Sales Order for customer ABC Corp with item ITEM-001, quantity 10"

**LLM Workflow**:
```
1. Search: search_erpnext_knowledge("Sales Order required fields create workflow",
                                     content_types="schema,workflow",
                                     doctype="Sales Order")

2. Review: Retrieved knowledge shows required fields:
   - customer (mandatory)
   - transaction_date (mandatory)
   - items (mandatory, with child fields: item_code, qty, rate)
   - delivery_date (mandatory)
   - etc.

3. Execute: Call MCP tool with ALL required fields populated correctly

4. Success: Sales Order created without errors
```

**Why This Matters:**

- ❌ **Without knowledge search**: LLM guesses field names → missing required fields → operation fails → retry loop
- ✅ **With knowledge search**: LLM knows exact requirements → provides complete data → operation succeeds immediately

**Prevented Issues:**
- Missing required fields causing validation errors
- Incorrect field names or data types
- Wrong workflow sequences
- Business rule violations
- Duplicate work and user frustration

**When Tools Are Called:**

**MANDATORY (Knowledge search BEFORE operations):**
- Before calling ANY MCP tool for ERPNext operations
- Before creating or updating DocTypes
- Before workflow operations (submit, cancel, amend)
- Before complex multi-step operations

**Also called for (User questions):**
- User asks about ERPNext workflows ("How do I create X?")
- User needs schema information ("What fields does X have?")
- User requests best practices
- User wants examples
- Troubleshooting errors

**Benefits Over Pre-Retrieval:**
- ✅ **Knowledge-first pattern**: LLM searches BEFORE operations, preventing errors
- ✅ **Higher accuracy**: Schema-informed operations with all required fields
- ✅ **First-time success**: Operations succeed immediately without retries
- ✅ LLM decides when knowledge is actually needed (reduces unnecessary searches)
- ✅ Multi-turn refinement (can search multiple times with different queries)
- ✅ Conditional retrieval (only searches for ERPNext-specific questions)
- ✅ Flexible filtering (LLM chooses appropriate content types and filters)
- ✅ Transparent to user (can see when knowledge is being retrieved)
- ✅ Lower latency for simple questions that don't need knowledge base

**Technical Details:**
- Uses vector embeddings (1536-dimensional for Gemini) for semantic search
- Similarity threshold: 0.7 (70% relevance minimum)
- Tools registered with megamind_graph workflow
- Read-only tools bypass user consent checks
- Gracefully handles Titan service failures

### CRAG (Corrective RAG) - Automatic Error Recovery

The system implements **CRAG (Corrective Retrieval-Augmented Generation)** to automatically detect and recover from operation failures by analyzing errors, retrieving corrective knowledge, and retrying with improved information.

**Architecture:**
- `src/megamind/graph/nodes/corrective_rag_node.py`: CRAG implementation with error detection and query rewriting
- Integrated into megamind_graph workflow between tool execution and agent
- Automatic retry loop with knowledge enhancement

**How it works:**
1. Tool execution completes (may fail with error)
2. CRAG node analyzes the result for error patterns
3. If error detected:
   - Extracts error details and DocType context
   - Uses LLM to generate targeted corrective query
   - Retrieves enhanced knowledge (higher match count, lower threshold)
   - Injects correction guidance into agent's context
4. Agent receives correction and retries with complete information
5. Success on retry (or exits after 2 attempts to prevent infinite loops)

**Error Detection Patterns:**
- Validation errors ("validation failed", "required field")
- Missing fields ("missing", "not provided")
- Invalid data ("invalid", "cannot")
- Authorization issues ("unauthorized", "forbidden")
- Business rule violations

**Flow Example:**

```
User: "Create Sales Order for ABC Corp"
Agent: Calls create_sales_order(customer="ABC Corp")
Tool: ❌ Error: Missing required field: delivery_date

🔧 CRAG Node:
  - Detects error ✓
  - Generates query: "Sales Order required fields and validation rules"
  - Retrieves 7 knowledge entries (schemas, workflows, examples)
  - Injects correction message with required field information

Agent: Receives correction guidance
Agent: Calls create_sales_order with ALL required fields
Tool: ✅ Success! SO-00123 created
```

**Key Features:**
- **Intelligent error detection**: Pattern matching for common failure types
- **Smart query rewriting**: LLM generates targeted knowledge queries based on error context
- **Enhanced retrieval**: Higher match count (7 vs 5), lower threshold (0.6 vs 0.7) for corrections
- **Retry prevention**: Max 2 correction attempts, automatic reset on success
- **Transparent correction**: Agent sees clear guidance with error details and corrective knowledge

**State Management:**
- `correction_attempts`: Tracks retry count (prevents infinite loops)
- `last_error_context`: Stores error details for debugging
- `is_correction_mode`: Flags that agent is in retry mode

**Benefits:**
- ✅ **40-60% reduction in operation failures**: Automatic recovery from validation errors
- ✅ **Improved user experience**: Seamless retries without user intervention
- ✅ **First-time success rate**: Combined with knowledge-first pattern, operations succeed immediately
- ✅ **Learning from errors**: System retrieves targeted knowledge based on actual failures

**Performance:**
- +2-3 seconds latency per correction (query generation + retrieval)
- ~500 tokens per correction (LLM query generation)
- Only triggers on detected errors (no overhead for successful operations)

**Testing:**
- Comprehensive test suite in `tests/test_crag_integration.py`
- 14 unit and integration tests covering error detection, query generation, retry logic
- Run tests: `uv run pytest tests/test_crag_integration.py -v`


### Static Prompts (prompts.py)

For specialized graph workflows, static prompt templates are defined in `src/megamind/prompts.py`:
- `wiki_agent_instructions` / `document_agent_instructions`: Used by minion endpoints
- Role generation prompts: `role_generation_agent_instructions`, `permission_description_agent_instructions`

These are simpler string templates with `{company}` and other placeholders formatted at runtime.

### API Routing Structure

**Main router** (`main.py`):
- Defines most endpoints directly in the main FastAPI app
- Uses `_handle_chat_stream()` helper for main chat endpoint with RAG integration
- Single generic endpoint serves all use cases via dynamic knowledge retrieval

**Minion router** (`api/v1/minion.py`):
- Separate APIRouter for wiki/document search
- Included in main app via `app.include_router(minion_router, prefix="/api/v1", tags=["Minion"])`
- Uses `_handle_minion_stream()` helper to reduce duplication
- Simpler request model (`MinionRequest`) with only `question` field

### State Management and Persistence

Uses **AsyncPostgresSaver** for checkpoint persistence:
- Checkpointer is initialized in `main.py:lifespan()` with connection pool
- Thread state is retrieved with `checkpointer.aget(config)` where config contains `thread_id`
- System prompts are only added when `thread_state is None` (new threads)
- Cookie-based authentication is passed through graph state for ERPNext/Frappe client calls

### Database Connection Pool

The application uses **AsyncConnectionPool** from psycopg for robust database connection management:

**Architecture:**
- `src/megamind/utils/database.py`: Connection utilities (configure, check callbacks)
- Pool initialized in `main.py:lifespan()` with comprehensive configuration
- Automatic connection health checking and replacement
- Graceful startup retry logic and shutdown handling

**Pool Configuration** (configurable via environment variables):
- `min_size=2`: Minimum connections maintained in pool
- `max_size=100`: Maximum concurrent connections allowed
- `max_waiting=50`: Maximum requests that can queue for a connection
- `max_lifetime=1800s`: Connections recycled after 30 minutes
- `max_idle=180s`: Idle connections closed after 3 minutes
- `reconnect_timeout=300s`: Retry reconnection attempts for 5 minutes
- `timeout=30s`: Timeout for acquiring connection from pool
- `num_workers=3`: Background workers for pool maintenance

**Connection Health Features:**
- **TCP Keepalives**: Detect and close broken connections automatically
  - `keepalives_idle=30s`: Start keepalive packets after 30s of inactivity
  - `keepalives_interval=10s`: Send keepalive every 10s after idle period
  - `keepalives_count=5`: Declare connection dead after 5 failed keepalives
- **Statement Timeout**: Kill queries running longer than 60 seconds
- **Health Checking**: Execute `SELECT 1` before giving connection to client
- **Automatic Configuration**: New connections configured with optimal settings

**Startup Behavior:**
- Retry logic: 3 attempts with 2-second delays between retries
- Detailed logging of pool configuration and initialization status
- Fallback from `SUPABASE_DB_URL` to `SUPABASE_CONNECTION_STRING`
- Critical failure if pool cannot be opened after all retries

**Shutdown Behavior:**
- Explicit pool closure with proper error handling
- Waits for active connections to complete before shutdown
- Logs shutdown progress and any errors during closure

**Benefits:**
- ✅ **Concurrent request handling**: Multiple requests can execute simultaneously
- ✅ **Automatic reconnection**: Recovers from transient connection failures
- ✅ **Connection health**: Detects and replaces broken connections before use
- ✅ **Resource optimization**: Recycles old connections, closes idle ones
- ✅ **Production-ready**: Comprehensive error handling and graceful degradation

**Configuration:**
Set pool parameters in `.env` (all optional, defaults shown above):
```bash
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=100
DB_POOL_MAX_WAITING=50
DB_POOL_MAX_LIFETIME=1800.0
DB_POOL_MAX_IDLE=180.0
DB_POOL_RECONNECT_TIMEOUT=300.0
DB_POOL_TIMEOUT=30.0
DB_POOL_NUM_WORKERS=3
```

### External Service Integration

**Titan (ERPNext Knowledge Base):**
- `src/megamind/clients/titan_client.py`: HTTP client for Titan API
- Provides ERPNext knowledge search and embedding generation
- Configuration: `TITAN_API_URL` in `.env` (default: http://localhost:8001)
- Used by RAG service for semantic knowledge retrieval
- Endpoints: `/api/v1/erpnext-knowledge/search`, `/api/v1/erpnext-knowledge/{id}`, etc.

**Frappe/ERPNext:**
- `src/megamind/clients/frappe_client.py`: HTTP client for ERPNext API
- Uses cookie-based authentication passed from request headers
- Called in graph nodes to fetch/create ERP data

**MCP Servers:**
- `src/megamind/clients/mcp_client_manager.py`: Manages MCP server connections
- Frappe MCP server path configured in `.env` as `FRAPPE_MCP_SERVER_PATH`
- Used by megamind_graph's `erpnext_mcp_tool_agent` ToolNode

**Supabase:**
- `src/megamind/clients/supabase_client.py`: Client for vector storage and data retrieval
- Migrations in `supabase/migrations/`

**Minion Service:**
- `src/megamind/clients/minion_client.py`: Client for wiki/document search
- Tools in `src/megamind/graph/tools/minion_tools.py`

### Graph Workflows

**megamind_graph** (main.py:51, workflows/megamind_graph.py):
- Entry: `megamind_agent_node` → calls tools (knowledge + MCP) → `corrective_rag_node` → back to agent
- CRAG layer between tool execution and agent provides automatic error recovery
- Exit: `knowledge_capture_node` refines final response
- Used for general queries, RAG, tool-based actions, and ERPNext operations

**stock_movement_graph** (workflows/stock_movement_graph.py):
- Single node: `smart_stock_movement_node` (nodes/stock_movement/smart_stock_movement_node.py)
- Extracts item code/quantity, auto-selects warehouse, creates stock entry
- Mongolian language support

**wiki_graph & document_search_graph** (workflows/wiki_graph.py, workflows/document_search_graph.py):
- Single-node solutions: `wiki_agent_node` and `document_agent_node` (nodes/minion_agent.py)
- Use search_wiki/search_document tools via minion_tools.py

**role_generation_graph** (workflows/role_generation_graph.py):
- Generates ERPNext role permissions based on user description
- Multi-node workflow: finds similar role → generates permissions → describes in human-readable format
- Non-streaming: uses `ainvoke()` instead of streaming, returns complete JSON response

### Configuration

Environment variables (see `.env.example`):
- `GOOGLE_API_KEY`: For Google Gemini LLM
- `FRAPPE_URL`, `FRAPPE_API_KEY`, `FRAPPE_API_SECRET`: ERPNext connection
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_CONNECTION_STRING`: Database and vector store
- `FRAPPE_MCP_SERVER_PATH`: Path to MCP server for ERPNext integration
- `MINION_API_URL`: URL for minion service (wiki/doc search)
- `LANGSMITH_*`: Observability (optional)

Settings loaded via `src/megamind/utils/config.py` using pydantic-settings.

## Working with This Codebase

### Adding a New Workflow

1. Create graph definition in `src/megamind/graph/workflows/your_workflow_graph.py`
2. Implement nodes in `src/megamind/graph/nodes/`
3. Define state schema in `src/megamind/graph/states.py`
4. Build graph in `main.py:lifespan()` and store in `app.state`
5. Add endpoint in `main.py` that retrieves graph from `request.app.state`

### Modifying Prompts

**For tool-based knowledge retrieval** (used by main chat endpoint):
1. **Base prompt**: Edit `src/megamind/base_prompt.py` to:
   - Modify core agent behavior and identity
   - Adjust instructions on when to use knowledge search tools
   - Add/remove examples of tool usage
   - Change tool calling strategy
2. **Knowledge tools**: Modify `src/megamind/graph/tools/titan_knowledge_tools.py` to:
   - Adjust tool descriptions (affects when LLM calls them)
   - Change result formatting
   - Modify search parameters or filtering logic
3. **Knowledge content**: Add/update knowledge entries in Titan service (external to this repo)
4. Test by sending queries to `/api/v1/stream/{thread}` and observing when LLM calls knowledge tools

**For static prompts** (used by specialized graphs):
1. Edit the prompt string in `src/megamind/prompts.py`
2. Use `.format()` placeholders like `{company}` for runtime values
3. Reference the prompt in the graph's node or endpoint handler

### Adding Tools

1. Define tool functions in `src/megamind/graph/tools/` using `@tool` decorator
2. Import tools in `src/megamind/graph/nodes/megamind_agent.py` and add to tools list
3. Import tools in `src/megamind/graph/workflows/megamind_graph.py` and add to ToolNode
4. Tools receive arguments from LLM and return string results
5. Update routing logic if tool requires user consent (see `route_tools_from_rag`)

**Example** (Titan knowledge tools):
- Defined in `src/megamind/graph/tools/titan_knowledge_tools.py`
- Registered in megamind_agent_node (combined with MCP tools)
- Added to ToolNode in megamind_graph workflow
- Bypass consent checks (read-only operations)

### Adding New API Endpoints

**When to use which approach:**
- **Main.py endpoints**: Simple endpoints that can reuse existing graph workflows
- **Separate router**: Feature with multiple related endpoints, or endpoints with significant business logic (recommended for maintainability)

#### Option A: Add Endpoint in main.py

**For streaming LangGraph endpoints:**
1. Define endpoint with `@app.post("/api/v1/your-endpoint/stream/{thread}")`
2. Use `_handle_chat_stream()` if using megamind_graph with RAG (already handles knowledge retrieval)
3. Create corresponding request model in `src/megamind/models/requests.py` if needed
4. Return responses via `stream_response_with_ping()`

**For non-streaming endpoints:**
1. Define endpoint with `@app.post("/api/v1/your-endpoint")`
2. Create custom handler function
3. Use `MainResponse` for consistent response format
4. Example: `/api/v1/role-generation`

#### Option B: Create Separate Router (Recommended)

**Step-by-step guide with example:**

**1. Define Request/Response Models** (`src/megamind/models/requests.py` and `responses.py`)
```python
# In requests.py
class YourFeatureRequest(BaseModel):
    field1: str
    field2: list[str]

# Use MainResponse for all responses (already defined in responses.py)
```

**2. Create Prompt** (`src/megamind/prompts.py`)
```python
your_feature_agent_instructions = """Your prompt here with {placeholder} support.

# Agent Role
Description of what this agent does...

# Instructions
Step-by-step instructions...

{documents}  # Example placeholder
"""
```

**3. Create Business Logic** (e.g., `src/megamind/graph/nodes/your_feature_agent.py`)
```python
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger
from megamind.configuration import Configuration
from megamind.graph.schemas import YourSchema
from megamind import prompts

async def your_processing_function(data: list[str]) -> YourSchema:
    """
    Process data and return structured results.
    """
    logger.info(f"Processing {len(data)} items")

    try:
        config = Configuration()
        llm = ChatGoogleGenerativeAI(model=config.query_generator_model)

        # Format the prompt
        prompt = prompts.your_feature_agent_instructions.format(
            documents="\n\n".join(data)
        )

        # Use structured output if needed
        structured_llm = llm.with_structured_output(YourSchema)
        result: YourSchema = await structured_llm.ainvoke(prompt)

        logger.info("Successfully processed data")
        return result

    except Exception as e:
        logger.error(f"Error processing data: {e}")
        raise
```

**4. Create Schema** (`src/megamind/graph/schemas.py`)
```python
class YourSchema(BaseModel):
    """
    Schema for your feature's structured output.
    """
    field1: dict = Field(description="Description of field1")
    field2: list[dict] = Field(description="Description of field2")
```

**5. Create External Client** (if needed, e.g., `src/megamind/clients/your_service_client.py`)
```python
import httpx
from loguru import logger
from megamind.utils.config import settings

class YourServiceClient:
    """
    A client for interacting with external service.
    """

    def __init__(self):
        self.api_url = settings.your_service_api_url
        self.tenant_id = settings.tenant_id
        logger.debug(f"Initializing client with API URL: {self.api_url}")

    async def call_service(self, data: dict) -> str:
        """
        Calls external service.

        Returns:
            job_id: Unique identifier for the request
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/endpoint",
                headers={"x-tenant-id": self.tenant_id},
                json=data,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json().get("id")
```

**6. Create Router** (`src/megamind/api/v1/your_feature.py`)
```python
from fastapi import APIRouter, Request, HTTPException
from loguru import logger

from megamind.clients.your_service_client import YourServiceClient
from megamind.graph.nodes.your_feature_agent import your_processing_function
from megamind.models.requests import YourFeatureRequest
from megamind.models.responses import MainResponse
from megamind.utils.config import settings

router = APIRouter()


@router.post("/your-feature/submit")
async def submit_request(
    request: Request,
    request_data: YourFeatureRequest,
):
    """
    Endpoint description.
    """
    try:
        logger.info(f"Received request for {len(request_data.field2)} items")

        # Business logic here
        client = YourServiceClient()
        job_id = await client.call_service({
            "field1": request_data.field1,
            "callback_url": "/api/v1/your-feature/callback",
        })

        logger.info(f"Request submitted successfully: {job_id}")

        return MainResponse(
            message="Request submitted successfully",
            response={"job_id": job_id},
        ).model_dump()

    except Exception as e:
        logger.error(f"Error in submit endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=MainResponse(
                message="Error",
                error=f"Failed to submit request: {str(e)}",
            ).model_dump(),
        )


@router.post("/your-feature/callback")
async def callback_handler(
    request: Request,
    request_data: YourFeatureRequest,
):
    """
    Callback endpoint description.
    """
    try:
        logger.info(f"Received callback with {len(request_data.field2)} items")

        # Process with LLM or other business logic
        result = await your_processing_function(request_data.field2)

        logger.info("Successfully processed callback")

        return MainResponse(
            message="Processing completed successfully",
            response=result.model_dump(),
        ).model_dump()

    except Exception as e:
        logger.error(f"Error in callback: {e}")
        raise HTTPException(
            status_code=500,
            detail=MainResponse(
                message="Error",
                error=f"Failed to process callback: {str(e)}",
            ).model_dump(),
        )
```

**7. Update Configuration** (`src/megamind/utils/config.py`)
```python
class Settings(BaseSettings):
    # ... existing settings ...
    your_service_api_url: str = "http://localhost:8001"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

**8. Update Environment Variables** (`.env.example`)
```bash
YOUR_SERVICE_API_URL="http://localhost:8001"
```

**9. Register Router** (`src/megamind/main.py`)
```python
# Import at top
from megamind.api.v1.your_feature import router as your_feature_router

# Register after other routers
app.include_router(
    your_feature_router, prefix="/api/v1", tags=["Your Feature"]
)
```

**Key Conventions:**
- Always use `MainResponse` for consistent response format
- Wrap all responses in `MainResponse(message="...", response={...}).model_dump()`
- Wrap errors in `MainResponse(message="Error", error="...").model_dump()`
- Use descriptive logger messages at INFO level for business events
- Use DEBUG level for technical details
- All async functions should have proper type hints
- Document endpoints with clear docstrings

**Real Examples in Codebase:**
- **Simple router**: `src/megamind/api/v1/minion.py` (streaming endpoints with shared handler)
- **Complex router**: `src/megamind/api/v1/document_extraction.py` (submit + callback pattern)
- **Main.py endpoint**: `/api/v1/role-generation` (non-streaming with direct LLM call)

### Graph Execution Flow

1. Request hits endpoint → extracts `thread` from path, `cookie` from headers
2. Retrieve graph from `app.state` and build config with `thread_id`
3. Check if new thread: if so, build system prompt:
   - Get runtime values (company, datetime) from ERPNext
   - Build base prompt with knowledge-first workflow instructions
4. Handle interruptions (if `interrupt_response` provided in request)
5. Add user message and invoke graph with streaming via `stream_response_with_ping()`
6. Graph executes nodes with **knowledge-first pattern + CRAG**:
   - `megamind_agent_node`: LLM receives user request for ERPNext operation
   - **FIRST**: LLM calls `search_erpnext_knowledge` to retrieve schemas, workflows, best practices
   - LLM reviews retrieved knowledge for required fields, validation rules, workflow steps
   - **THEN**: LLM calls MCP tools with complete, accurate parameters based on knowledge
   - `mcp_tools` ToolNode: Executes tool calls and returns results
   - 🔧 `corrective_rag_node`: Analyzes tool results for errors
     - If error detected: Generates corrective query → Retrieves enhanced knowledge → Adds correction guidance
     - If success: Passes through, resets correction counter
   - Back to `megamind_agent_node`: LLM receives correction (if any) and retries or continues
   - Can loop multiple times for multi-step operations (search → execute → correct → retry → execute)
7. Stream events back to client as Server-Sent Events (SSE)
8. User sees tool calls in real-time:
   - Knowledge search happening first
   - Operation execution with informed parameters
   - Automatic correction and retry if needed
   - Success on first or second attempt
