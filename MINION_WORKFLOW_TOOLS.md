# Minion Workflow Tools - API Mapping Reference

This document shows how the new workflow tools in `minion_workflow_tools.py` map to Minion's `/search/*` API endpoints.

## Tool to API Endpoint Mapping

| Tool Function | Minion API Method | Endpoint | Description |
|---------------|-------------------|----------|-------------|
| `search_business_workflows()` | `client.search()` | `POST /search/search` | Searches with fixed object_types: ["Workflow", "BusinessProcess", "ProcessStep"] |
| `search_workflow_knowledge()` | `client.search()` | `POST /search/search` | Flexible semantic search with configurable object_types |
| `ask_workflow_question()` | `client.ask()` | `POST /search/ask` | Natural language questions with synthesized answers |
| `get_workflow_related_objects()` | `client.get_related()` | `POST /search/related` | Graph traversal to find related objects |
| `search_employees()` | `client.search()` | `POST /search/search` | Searches with fixed object_types: ["User", "Employee", "Department", "Role"] |

## Implementation Details

### 1. search_business_workflows (Drop-in replacement for ZEP)

**Function Signature:**
```python
async def search_business_workflows(query: str) -> str
```

**Minion API Call:**
```python
await client.search(
    query=query,
    object_types=["Workflow", "BusinessProcess", "ProcessStep"],
    limit=10,
)
```

**Purpose:** Direct replacement for ZEP's workflow search. Uses Minion's unified search with workflow-specific object types.

---

### 2. search_workflow_knowledge (Enhanced search)

**Function Signature:**
```python
async def search_workflow_knowledge(
    query: str,
    object_types: list[str] | None = None,
    limit: int = 10
) -> str
```

**Minion API Call:**
```python
await client.search(
    query=query,
    object_types=object_types,  # Configurable
    limit=limit,
)
```

**Purpose:** More flexible than `search_business_workflows`. Allows custom object_types for searching roles, policies, or any other organizational knowledge.

---

### 3. ask_workflow_question (Natural language)

**Function Signature:**
```python
async def ask_workflow_question(question: str) -> str
```

**Minion API Call:**
```python
await client.ask(question)
```

**Purpose:** Natural language Q&A about workflows. Returns synthesized answers rather than raw search results.

---

### 4. get_workflow_related_objects (Graph traversal)

**Function Signature:**
```python
async def get_workflow_related_objects(
    object_type: str,
    object_id: str,
    direction: str = "both",
    max_depth: int = 2
) -> str
```

**Minion API Call:**
```python
await client.get_related(
    object_type=object_type,
    object_id=object_id,
    direction=direction,  # "in", "out", or "both"
    max_depth=max_depth,
)
```

**Purpose:** Graph traversal to discover relationships between workflows, processes, roles, and other elements.

---

### 5. search_employees (Drop-in replacement for ZEP)

**Function Signature:**
```python
async def search_employees(query: str) -> str
```

**Minion API Call:**
```python
await client.search(
    query=query,
    object_types=["User", "Employee", "Department", "Role"],
    limit=10,
)
```

**Purpose:** Direct replacement for ZEP's employee search. Uses Minion's unified search with employee-related object types.

---

## MinionClient Methods Reference

All tools use methods from `MinionClient` in `src/megamind/clients/minion_client.py`:

| Method | Endpoint | Parameters |
|--------|----------|------------|
| `search()` | `POST /api/v1/search/search` | query, object_types, limit, user_email |
| `ask()` | `POST /api/v1/search/ask` | question, user_email |
| `get_related()` | `POST /api/v1/search/related` | object_type, object_id, direction, max_depth, user_email |

Additional MinionClient methods available (not yet exposed as tools):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `get_user_context()` | `GET /api/v1/search/context/user/{email}` | User roles, approvals, recent docs |
| `get_document_context()` | `GET /api/v1/search/context/document/{doctype}/{name}` | Document details with chain |
| `get_entity_context()` | `POST /api/v1/search/context/entity` | Entity details with transactions |

## Where Tools Are Used

### Orchestrator Agent (`get_orchestrator_tools()`)
- `search_business_workflows` - Quick workflow lookups
- `search_employees` - Quick employee searches
- Direct access for fast read-only queries

### Knowledge Specialist (`get_knowledge_tools()`)
- All 5 tools for comprehensive research:
  - `search_business_workflows`
  - `search_workflow_knowledge` (enhanced)
  - `ask_workflow_question` (NL questions)
  - `get_workflow_related_objects` (graph traversal)
  - `search_employees`

### Knowledge Analyst Subagent (`call_knowledge_analyst`)
- `search_business_workflows`
- `search_employees`
- Used in standalone tool for backward compatibility

## Migration Path from ZEP

**Before (ZEP Cloud):**
```python
from megamind.graph.tools.zep_graph_tools import (
    search_business_workflows,  # Uses Zep Cloud API
    search_employees,            # Uses Zep Cloud API
)
```

**After (Minion):**
```python
from megamind.graph.tools.minion_workflow_tools import (
    search_business_workflows,  # Uses Minion /search/search
    search_employees,            # Uses Minion /search/search
)
```

**Benefits:**
- ✅ Same function signatures (drop-in replacement)
- ✅ Self-hosted (no external SaaS dependency)
- ✅ Richer Neo4j knowledge graph
- ✅ Unified `/search/*` API (future-proof)
- ✅ Additional tools for advanced use cases

## Example Usage

### Agent calling search_business_workflows:
```python
# LLM decides to search for workflows
result = await search_business_workflows.ainvoke({
    "query": "purchase order approval process"
})
# Returns JSON with workflows, processes, and steps from Neo4j
```

### Agent asking a natural language question:
```python
result = await ask_workflow_question.ainvoke({
    "question": "What is the procurement workflow?"
})
# Returns synthesized answer based on graph knowledge
```

### Agent finding related objects:
```python
result = await get_workflow_related_objects.ainvoke({
    "object_type": "Workflow",
    "object_id": "Purchase Order Approval",
    "direction": "both",
    "max_depth": 2,
})
# Returns related states, transitions, roles, etc.
```
