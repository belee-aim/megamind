import httpx
from loguru import logger


class MinionClient:
    """
    A client for interacting with the Minion service.
    """

    def __init__(self, minion_api_url: str):
        """
        Initializes the Minion client.
        """
        self.api_url = minion_api_url
        logger.debug(f"Initializing Minion client with API URL: {self.api_url}")

    async def search_role_permissions(self, query: str):
        """
        Searches for role permissions in the Minion service.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/graphrag/search",
                # headers={"x-graph-name": "role"},
                json={"query": query},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def search_document(self, query: str):
        """
        Searches for documents in the Minion service.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/graphrag/search",
                # headers={"x-graph-name": "document"},
                json={"query": query},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def search_wiki(self, query: str):
        """
        Searches for knowledge in Company's Wiki in the Minion service.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/graphrag/search",
                # headers={"x-graph-name": "wiki"},
                json={"query": query},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    # GET Methods for Process/Workflow Definitions

    async def get_process(self, process_name: str) -> dict:
        """
        Get complete definition of a business process.

        Args:
            process_name: Name of the business process

        Returns:
            Process definition with all steps, conditions, and triggers
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/api/v1/processes/{process_name}",
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_workflow(self, workflow_name: str) -> dict:
        """
        Get complete definition of a workflow including approval chain.

        Args:
            workflow_name: Name of the workflow

        Returns:
            Workflow definition with states, transitions, and role requirements
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/api/v1/workflows/{workflow_name}",
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_department_hierarchy(self, dept_code: str) -> dict:
        """
        Get department hierarchy including parent departments.

        Args:
            dept_code: Department code

        Returns:
            Department hierarchy
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/api/v1/departments/{dept_code}/hierarchy",
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_role_permissions(self, role_name: str) -> dict:
        """
        Get all permissions for a role.

        Args:
            role_name: Role name

        Returns:
            Role permissions including doctypes and states
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/api/v1/roles/{role_name}/permissions",
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    # POST Methods for Query Operations

    async def query_next_steps(self, workflow_name: str, state_name: str) -> dict:
        """
        Query what workflows are triggered after a workflow state completes.

        This is used by AI agents to determine what to execute next.

        Args:
            workflow_name: Current workflow
            state_name: Current state

        Returns:
            List of next workflows/steps to execute
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/processes/query/next-steps",
                json={
                    "workflow_name": workflow_name,
                    "state_name": state_name,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def query_available_actions(
        self, workflow_name: str, state_name: str
    ) -> dict:
        """
        Query available actions and transitions from a workflow state.

        Args:
            workflow_name: Current workflow
            state_name: Current state

        Returns:
            List of available transitions and authorized roles
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/processes/query/actions",
                json={
                    "workflow_name": workflow_name,
                    "state_name": state_name,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def query_state_permissions(
        self, workflow_name: str, state_name: str
    ) -> dict:
        """
        Query who can edit or execute transitions in a specific state.

        Args:
            workflow_name: Current workflow
            state_name: Current state

        Returns:
            List of roles and users with specific permissions
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/processes/query/permissions",
                json={
                    "workflow_name": workflow_name,
                    "state_name": state_name,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def validate_user_permission(
        self, user_email: str, workflow_name: str, state_name: str
    ) -> dict:
        """
        Validate if a user has permissions for a specific workflow state.

        Checks both edit permissions and transition execution permissions.

        Args:
            user_email: User's email address
            workflow_name: Workflow name
            state_name: State name

        Returns:
            User validation result with authorization status
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/processes/validate-user",
                json={
                    "user_email": user_email,
                    "workflow_name": workflow_name,
                    "state_name": state_name,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    # POST Methods for Semantic Search

    async def search_processes(
        self, query: str, top_k: int = 5, similarity_threshold: float = 0.7
    ) -> dict:
        """
        Semantic search for business processes using natural language queries.

        Uses vector similarity to find processes matching the query description.

        Args:
            query: Natural language search query
            top_k: Number of results to return (default: 5)
            similarity_threshold: Minimum similarity score (default: 0.7)

        Returns:
            Ranked list of business processes by similarity
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/processes/search",
                json={
                    "query": query,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def search_workflows(
        self, query: str, top_k: int = 5, similarity_threshold: float = 0.7
    ) -> dict:
        """
        Semantic search for workflows using natural language queries.

        Uses vector similarity to find workflows matching the query description.

        Args:
            query: Natural language search query
            top_k: Number of results to return (default: 5)
            similarity_threshold: Minimum similarity score (default: 0.7)

        Returns:
            Ranked list of workflows by similarity
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/workflows/search",
                json={
                    "query": query,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def search_policies(
        self, query: str, top_k: int = 5, similarity_threshold: float = 0.7
    ) -> dict:
        """
        Semantic search for policies using natural language queries.

        Uses vector similarity to find policies matching the query description.
        Searches both summary and full_text fields.

        Args:
            query: Natural language search query
            top_k: Number of results to return (default: 5)
            similarity_threshold: Minimum similarity score (default: 0.7)

        Returns:
            Ranked list of policies by similarity
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/policies/search",
                json={
                    "query": query,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def search_steps(
        self, query: str, top_k: int = 5, similarity_threshold: float = 0.7
    ) -> dict:
        """
        Semantic search for process steps using natural language queries.

        Uses vector similarity to find process steps matching the query.
        Useful for finding specific approval steps or actions.

        Args:
            query: Natural language search query
            top_k: Number of results to return (default: 5)
            similarity_threshold: Minimum similarity score (default: 0.7)

        Returns:
            Ranked list of process steps by similarity
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/steps/search",
                json={
                    "query": query,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def search_roles(
        self, query: str, top_k: int = 5, similarity_threshold: float = 0.7
    ) -> dict:
        """
        Semantic search for roles using natural language queries.

        Uses vector similarity to find roles matching the query description.
        Useful for finding roles with specific responsibilities.

        Args:
            query: Natural language search query
            top_k: Number of results to return (default: 5)
            similarity_threshold: Minimum similarity score (default: 0.7)

        Returns:
            Ranked list of roles by similarity
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/roles/search",
                json={
                    "query": query,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
