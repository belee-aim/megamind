from typing import Any

import httpx
from loguru import logger

DEFAULT_USER_EMAIL = "agent@system"


class MinionClient:
    """
    A client for interacting with the Minion service.
    Provides access to GraphRAG search, semantic search, workflow queries,
    and document synchronization APIs.
    """

    def __init__(self, minion_api_url: str, timeout: float = 30.0):
        """
        Initializes the Minion client.

        Args:
            minion_api_url: Base URL of the Minion service
            timeout: Default timeout for requests in seconds
        """
        self.api_url = minion_api_url
        self.timeout = timeout
        logger.debug(f"Initializing Minion client with API URL: {self.api_url}")

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Internal method to make HTTP requests."""
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"{self.api_url}{endpoint}",
                json=json,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    # ==================== GraphRAG Router ====================

    async def search_document(self, query: str) -> dict[str, Any]:
        """
        Searches for documents using GraphRAG with sources.

        Args:
            query: Natural language search query

        Returns:
            Response with answer and sources
        """
        return await self._request(
            "POST", "/api/v1/graphrag/search", json={"query": query}
        )

    # ==================== Search Router (Agent-focused) ====================

    async def get_actions(self, category: str | None = None) -> dict[str, Any]:
        """
        List all available actions for agents.

        Args:
            category: Optional filter - "query" or "context"

        Returns:
            List of available actions with their details
        """
        params = {"category": category} if category else None
        return await self._request("GET", "/api/v1/search/actions", params=params)

    async def get_action_details(self, action_id: str) -> dict[str, Any]:
        """
        Get details for a specific action.

        Args:
            action_id: The action identifier (e.g., "query.search")

        Returns:
            Action details including parameters and returns
        """
        return await self._request("GET", f"/api/v1/search/actions/{action_id}")

    async def execute_action(
        self,
        action_id: str,
        parameters: dict[str, Any],
        user_email: str = DEFAULT_USER_EMAIL,
        user_roles: list[str] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute an action (main endpoint for agents).

        Args:
            action_id: The action to execute (e.g., "query.search")
            parameters: Action-specific parameters
            user_email: User email for authorization
            user_roles: User roles for permission checks
            request_id: Optional trace ID

        Returns:
            Action execution result with data or error
        """
        payload = {
            "action_id": action_id,
            "parameters": parameters,
            "user_email": user_email,
        }
        if user_roles:
            payload["user_roles"] = user_roles
        if request_id:
            payload["request_id"] = request_id

        return await self._request("POST", "/api/v1/search/execute", json=payload)

    async def validate_action(
        self,
        action_id: str,
        parameters: dict[str, Any],
        user_email: str = DEFAULT_USER_EMAIL,
        user_roles: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Validate an action without executing it.

        Args:
            action_id: The action to validate
            parameters: Action-specific parameters
            user_email: User email for authorization
            user_roles: User roles for permission checks

        Returns:
            Validation result with is_valid, errors, warnings
        """
        payload = {
            "action_id": action_id,
            "parameters": parameters,
            "user_email": user_email,
        }
        if user_roles:
            payload["user_roles"] = user_roles

        return await self._request("POST", "/api/v1/search/validate", json=payload)

    async def search(
        self,
        query: str,
        object_types: list[str] | None = None,
        limit: int = 10,
        user_email: str = DEFAULT_USER_EMAIL,
    ) -> dict[str, Any]:
        """
        Semantic search across the Neo4j graph.

        Args:
            query: Natural language search query
            object_types: Filter by types (e.g., ["process", "workflow"])
            limit: Maximum results to return
            user_email: User email for context

        Returns:
            Search results with similarity scores
        """
        payload = {
            "query": query,
            "limit": limit,
            "user_email": user_email,
        }
        if object_types:
            payload["object_types"] = object_types

        return await self._request("POST", "/api/v1/search/search", json=payload)

    async def ask(
        self, question: str, user_email: str = "agent@system"
    ) -> dict[str, Any]:
        """
        Ask a natural language question.

        Args:
            question: Natural language question
            user_email: User email for context

        Returns:
            Natural language answer
        """
        return await self._request(
            "POST",
            "/api/v1/search/ask",
            json={"question": question, "user_email": user_email},
        )

    async def get_related(
        self,
        object_type: str,
        object_id: str,
        direction: str = "both",
        max_depth: int = 2,
        user_email: str = DEFAULT_USER_EMAIL,
    ) -> dict[str, Any]:
        """
        Get objects related to a given object via graph traversal.

        Args:
            object_type: Type of the source object (e.g., "Purchase Order")
            object_id: ID of the source object (e.g., "PO-001")
            direction: Traversal direction - "in", "out", or "both"
            max_depth: Maximum traversal depth
            user_email: User email for context

        Returns:
            Related objects with relationship details
        """
        return await self._request(
            "POST",
            "/api/v1/search/related",
            json={
                "object_type": object_type,
                "object_id": object_id,
                "direction": direction,
                "max_depth": max_depth,
                "user_email": user_email,
            },
        )

    async def get_chain(
        self, doctype: str, name: str, user_email: str = "agent@system"
    ) -> dict[str, Any]:
        """
        Get the transaction chain for a document (e.g., SO→DN→SI).

        Args:
            doctype: Document type (e.g., "Sales Order")
            name: Document name (e.g., "SO-001")
            user_email: User email for context

        Returns:
            Document chain with related transactions
        """
        return await self._request(
            "POST",
            "/api/v1/search/chain",
            json={"doctype": doctype, "name": name, "user_email": user_email},
        )

    async def aggregate(
        self,
        object_type: str,
        group_by: str,
        metric: str = "count",
        metric_field: str | None = None,
        filters: dict[str, Any] | None = None,
        user_email: str = DEFAULT_USER_EMAIL,
    ) -> dict[str, Any]:
        """
        Aggregate data by dimensions for business intelligence.

        Args:
            object_type: Type to aggregate (e.g., "Purchase Order")
            group_by: Field to group by (e.g., "supplier")
            metric: Aggregation metric - "count", "sum", "avg", "min", "max"
            metric_field: Field for sum/avg/min/max metrics
            filters: Optional filters (e.g., {"status": "completed"})
            user_email: User email for context

        Returns:
            Aggregated results
        """
        payload = {
            "object_type": object_type,
            "group_by": group_by,
            "metric": metric,
            "user_email": user_email,
        }
        if metric_field:
            payload["metric_field"] = metric_field
        if filters:
            payload["filters"] = filters

        return await self._request("POST", "/api/v1/search/aggregate", json=payload)

    async def get_user_context(self, email: str) -> dict[str, Any]:
        """
        Get context for a user including roles, pending approvals, recent docs.

        Args:
            email: User email address

        Returns:
            User profile with authorization context
        """
        return await self._request("GET", f"/api/v1/search/context/user/{email}")

    async def get_document_context(self, doctype: str, name: str) -> dict[str, Any]:
        """
        Get full context for a document including chain, owner, workflow state.

        Args:
            doctype: Document type (e.g., "Sales Order")
            name: Document name (e.g., "SO-001")

        Returns:
            Document details with related context
        """
        return await self._request(
            "GET", f"/api/v1/search/context/document/{doctype}/{name}"
        )

    async def get_entity_context(
        self, entity_type: str, entity_id: str, user_email: str = "agent@system"
    ) -> dict[str, Any]:
        """
        Get context for a business entity (Customer, Supplier, etc.).

        Args:
            entity_type: Entity type (e.g., "Customer")
            entity_id: Entity ID (e.g., "CUST-001")
            user_email: User email for context

        Returns:
            Entity details with related transactions and statistics
        """
        return await self._request(
            "POST",
            "/api/v1/search/context/entity",
            json={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "user_email": user_email,
            },
        )

    # ==================== Sync Router ====================

    async def sync_document(
        self, doctype: str, name: str, with_embeddings: bool = True
    ) -> dict[str, Any]:
        """
        Sync a single document from ERPNext to Neo4j.

        Args:
            doctype: Document type (e.g., "Purchase Order")
            name: Document name (e.g., "PO-001")
            with_embeddings: Whether to generate embeddings

        Returns:
            Sync result with status
        """
        return await self._request(
            "POST",
            "/api/v1/sync/document",
            json={"doctype": doctype, "name": name, "with_embeddings": with_embeddings},
        )

    async def delete_document(self, doctype: str, name: str) -> dict[str, Any]:
        """
        Delete a document from Neo4j (for cleanup after ERPNext deletion).

        Args:
            doctype: Document type
            name: Document name

        Returns:
            Deletion result
        """
        return await self._request(
            "DELETE",
            "/api/v1/sync/document",
            json={"doctype": doctype, "name": name},
        )

    async def semantic_search(
        self,
        query: str,
        labels: list[str] | None = None,
        limit: int = 10,
        min_score: float = 0.7,
    ) -> dict[str, Any]:
        """
        Semantic search across synced documents using vector similarity.

        Args:
            query: Natural language search query
            labels: Filter by Neo4j labels (e.g., ["PurchaseOrder", "SalesOrder"])
            limit: Maximum results to return
            min_score: Minimum similarity score threshold

        Returns:
            Matching documents with similarity scores
        """
        payload = {"query": query, "limit": limit, "min_score": min_score}
        if labels:
            payload["labels"] = labels

        return await self._request("POST", "/api/v1/search/semantic", json=payload)

    async def get_sync_status(self) -> dict[str, Any]:
        """
        Get current sync status and statistics.

        Returns:
            Last sync times and node counts per doctype
        """
        return await self._request("GET", "/api/v1/sync/status")

    async def get_supported_doctypes(self) -> dict[str, Any]:
        """
        List all supported doctypes for sync with their tiers.

        Returns:
            Doctypes organized by tier (tier1, tier2, tier3, all)
        """
        return await self._request("GET", "/api/v1/sync/doctypes")

    # ==================== Processes Router ====================

    async def get_workflow(self, workflow_name: str) -> dict[str, Any]:
        """
        Get complete workflow definition including states and transitions.

        Args:
            workflow_name: Name of the workflow

        Returns:
            Workflow structure with approval chain
        """
        return await self._request("GET", f"/api/v1/workflows/{workflow_name}")

    async def get_process(self, process_name: str) -> dict[str, Any]:
        """
        Get complete business process definition.

        Args:
            process_name: Name of the process

        Returns:
            Process definition with steps, conditions, and triggers
        """
        return await self._request("GET", f"/api/v1/processes/{process_name}")

    async def query_next_steps(
        self, workflow_name: str, state_name: str
    ) -> dict[str, Any]:
        """
        Query what workflows are triggered after a workflow state completes.

        Args:
            workflow_name: Current workflow name
            state_name: Current state name

        Returns:
            List of next workflows/steps to execute
        """
        return await self._request(
            "POST",
            "/api/v1/processes/query/next-steps",
            params={"workflow_name": workflow_name, "state_name": state_name},
        )

    async def query_actions(
        self, workflow_name: str, state_name: str
    ) -> dict[str, Any]:
        """
        Query available actions and transitions from a workflow state.

        Args:
            workflow_name: Current workflow name
            state_name: Current state name

        Returns:
            Available transitions and authorized roles
        """
        return await self._request(
            "POST",
            "/api/v1/processes/query/actions",
            params={"workflow_name": workflow_name, "state_name": state_name},
        )

    async def query_permissions(
        self, workflow_name: str, state_name: str
    ) -> dict[str, Any]:
        """
        Query who can edit or execute transitions in a specific state.

        Args:
            workflow_name: Current workflow name
            state_name: Current state name

        Returns:
            Roles and users with specific permissions
        """
        return await self._request(
            "POST",
            "/api/v1/processes/query/permissions",
            params={"workflow_name": workflow_name, "state_name": state_name},
        )

    async def validate_user_permission(
        self, user_email: str, workflow_name: str, state_name: str
    ) -> dict[str, Any]:
        """
        Validate if a user has permissions for a specific workflow state.

        Args:
            user_email: User email to check
            workflow_name: Workflow name
            state_name: State name

        Returns:
            Authorization status with reason
        """
        return await self._request(
            "POST",
            "/api/v1/processes/validate-user",
            json={
                "user_email": user_email,
                "workflow_name": workflow_name,
                "state_name": state_name,
            },
        )

    async def get_role_permissions(self, role_name: str) -> dict[str, Any]:
        """
        Get all permissions for a role.

        Args:
            role_name: Name of the role

        Returns:
            Role permissions including doctypes and state permissions
        """
        return await self._request("GET", f"/api/v1/roles/{role_name}/permissions")

    async def search_workflows(
        self, query: str, top_k: int = 10, similarity_threshold: float = 0.7
    ) -> dict[str, Any]:
        """
        Semantic search for workflows using natural language.

        Args:
            query: Natural language description
            top_k: Number of results
            similarity_threshold: Minimum similarity score

        Returns:
            Ranked workflows by similarity
        """
        return await self._request(
            "POST",
            "/api/v1/workflows/search",
            json={
                "query": query,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
            },
        )

    async def search_processes(
        self, query: str, top_k: int = 10, similarity_threshold: float = 0.7
    ) -> dict[str, Any]:
        """
        Semantic search for business processes using natural language.

        Args:
            query: Natural language description
            top_k: Number of results
            similarity_threshold: Minimum similarity score

        Returns:
            Ranked processes by similarity
        """
        return await self._request(
            "POST",
            "/api/v1/processes/search",
            json={
                "query": query,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
            },
        )
