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
# Generate workflow graph images
python generate_graph_image.py stock_movement
python generate_graph_image.py document

# Test dynamic prompt builder
python tests/test_prompt_builder.py
python tests/test_prompt_builder.py --variant stock_movement
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
- `src/megamind/graph/workflows/`: Graph definitions (megamind_graph.py, stock_movement_graph.py, etc.)
- `src/megamind/graph/nodes/`: Node implementations for each graph
- `src/megamind/graph/states.py`: State schemas for graphs
- `src/megamind/prompts.py`: Static prompt templates (older style, used by some graphs)
- `src/megamind/dynamic_prompts/`: Dynamic prompt system (newer, used by megamind_graph)
- `langgraph.json`: LangGraph configuration (currently points to stock_movement_graph)

### API Endpoints and Graph Mapping

**Endpoints in `main.py`:**
- `/api/v1/stream/{thread}` → megamind_graph (generic prompt family, uses dynamic prompts)
- `/api/v1/stock-movement/stream/{thread}` → megamind_graph (stock_movement prompt family, uses dynamic prompts)
- `/api/v1/accounting-finance/stream/{thread}` → megamind_graph (accounting_finance prompt family, uses dynamic prompts)
- `/api/v1/admin-support/stream/{thread}` → admin_support_graph (uses static prompts from prompts.py)
- `/api/v1/bank-reconciliation/stream/{thread}` → bank_reconciliation_graph (uses static prompts from prompts.py)
- `/api/v1/role-generation` → role_generation_graph (non-streaming, uses `ainvoke()`)
- `/api/v1/reconciliation/merge` → Utility endpoint (no graph, direct Pandas processing)

**Endpoints in `api/v1/minion.py` (included via router):**
- `/api/v1/wiki/stream/{thread_id}` → wiki_graph (uses static prompts from prompts.py)
- `/api/v1/document/stream/{thread_id}` → document_search_graph (uses static prompts from prompts.py)

**Key differences:**
- Endpoints using `megamind_graph` share the same graph but load different **prompt families** via the dynamic prompt system
- Minion endpoints use `MinionRequest` (only `question` field) instead of `ChatRequest`
- Minion endpoints use a shared `_handle_minion_stream()` handler function
- Role generation endpoint is non-streaming and returns a complete JSON response

### Dynamic Prompt System

Located in `src/megamind/dynamic_prompts/`, this system builds prompts from reusable YAML-configured components:
- `components/`: Reusable prompt pieces (agent_role.py, constraints.py, examples.py, etc.)
- `variants/`: YAML files defining prompt structures (generic.yaml, stock_movement.yaml, etc.)
- `core/builder.py`: PromptBuilder assembles components based on YAML config
- `core/registry.py`: Manages component registration and retrieval

**How it works:**
1. At startup, `prompt_registry.load()` is called in `main.py:lifespan()`
2. When a new thread starts, the system prompt is built using `prompt_registry.get(context)` where context includes the prompt family
3. Components are combined in the order specified in the YAML variant file

### Static Prompts (prompts.py)

For graphs not using the dynamic prompt system, static prompt templates are defined in `src/megamind/prompts.py`:
- `wiki_agent_instructions` / `document_agent_instructions`: Used by minion endpoints
- `admin_support_agent_instructions` / `bank_reconciliation_agent_instructions`: Used by dedicated graphs
- `content_agent_instructions`: Used by content refinement node in megamind_graph
- Role generation prompts: `find_related_role_instructions`, `role_generation_agent_instructions`, `permission_description_agent_instructions`

These are simpler string templates with `{company}` and other placeholders formatted at runtime.

### API Routing Structure

**Main router** (`main.py`):
- Defines most endpoints directly in the main FastAPI app
- Uses `_handle_chat_stream()` helper for endpoints sharing megamind_graph
- Differentiates requests by `prompt_family` parameter

**Minion router** (`api/v1/minion.py`):
- Separate APIRouter for wiki/document search
- Included in main app via `app.include_router(minion_router, prefix="/api/v1", tags=["Minion"])`
- Uses `_handle_minion_stream()` helper to reduce duplication
- Simpler request model (`MinionRequest`) with only `question` field

### State Management and Persistence

Uses **AsyncPostgresSaver** for checkpoint persistence:
- Checkpointer is initialized in `main.py:lifespan()` with `settings.supabase_connection_string`
- Thread state is retrieved with `checkpointer.aget(config)` where config contains `thread_id`
- System prompts are only added when `thread_state is None` (new threads)
- Cookie-based authentication is passed through graph state for ERPNext/Frappe client calls

### External Service Integration

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
- Entry: `megamind_agent_node` → can call `erpnext_mcp_tool_agent` in a loop
- Exit: `content_agent` refines final response
- Used for general queries, RAG, and tool-based actions

**stock_movement_graph** (workflows/stock_movement_graph.py):
- Single node: `smart_stock_movement_node` (nodes/stock_movement/smart_stock_movement_node.py)
- Extracts item code/quantity, auto-selects warehouse, creates stock entry
- Mongolian language support

**wiki_graph & document_search_graph** (workflows/wiki_graph.py, workflows/document_search_graph.py):
- Single-node solutions: `wiki_agent_node` and `document_agent_node` (nodes/minion_agent.py)
- Use search_wiki/search_document tools via minion_tools.py

**admin_support_graph & bank_reconciliation_graph:**
- Multi-node workflows for specific business processes
- Defined in workflows/admin_support_graph.py and workflows/bank_reconciliation_graph.py

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

**For dynamic prompts** (used by megamind_graph endpoints):
1. Add/modify components in `src/megamind/dynamic_prompts/components/`
2. Create/update YAML variant in `src/megamind/dynamic_prompts/variants/`
3. Test with `python tests/test_prompt_builder.py --variant your_variant`
4. Use variant by passing correct `prompt_family` in endpoint handler's `_handle_chat_stream()` call

**For static prompts** (used by other graphs):
1. Edit the prompt string in `src/megamind/prompts.py`
2. Use `.format()` placeholders like `{company}` for runtime values
3. Reference the prompt in the graph's node or endpoint handler

### Adding Tools

1. Define tool functions in `src/megamind/graph/tools/`
2. Register tools with agent nodes or ToolNodes in graph definitions
3. Tools receive state and can access `cookie` for authenticated API calls

### Adding New API Endpoints

**When to use which approach:**
- **Main.py endpoints**: Simple endpoints, or endpoints that need to share megamind_graph with different prompt families
- **Separate router**: Feature with multiple related endpoints, or endpoints with significant business logic (recommended for maintainability)

#### Option A: Add Endpoint in main.py

**For streaming LangGraph endpoints:**
1. Define endpoint with `@app.post("/api/v1/your-endpoint/stream/{thread}")`
2. Use `_handle_chat_stream()` if using megamind_graph with a new prompt family
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
3. Check if new thread: if so, build system prompt using prompt_registry
4. Handle interruptions (if `interrupt_response` provided in request)
5. Add user message and invoke graph with streaming via `stream_response_with_ping()`
6. Graph executes nodes, calls tools, updates checkpointer state
7. Stream events back to client as Server-Sent Events (SSE)
