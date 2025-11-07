import httpx
from loguru import logger
from typing import List, Dict, Optional

from megamind.configuration import Configuration
from megamind.models.requests import DocumentRequestBody
from megamind.utils.config import settings


class TitanClient:
    """
    A client for interacting with the Titan document processing service.
    """

    def __init__(self):
        """
        Initializes the Titan client.

        Args:
            titan_api_url: The base URL for the Titan API
        """
        self.api_url = settings.titan_api_url
        self.tenant_id = settings.tenant_id
        logger.debug(f"Initializing Titan client with API URL: {self.api_url}")

    async def submit_documents(
        self, file_names: list[DocumentRequestBody], callback_url: str
    ) -> str:
        """
        Submits a list of file names to the Titan service for processing.

        Args:
            file_names: List of file names to process
            callback_url: The URL where Titan should send the processed documents

        Returns:
            job_id: The unique identifier for this processing job

        Raises:
            httpx.HTTPError: If the request to Titan fails
        """
        logger.info(f"Submitting {len(file_names)} files to Titan service")
        logger.debug(f"Callback URL: {callback_url}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/process-requests",
                headers={"x-tenant-id": self.tenant_id},
                json={
                    "file_names": [file.model_dump() for file in file_names],
                    "callback_url": callback_url,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            job_id = data.get("id")

            logger.info(f"Titan processing job created: {job_id}")
            return job_id

    async def search_knowledge(
        self,
        query: str,
        doctype_filter: Optional[str] = None,
        match_count: int = 5,
        similarity_threshold: float = 0.7,
    ) -> List[Dict]:
        """
        Search ERPNext knowledge using semantic similarity.

        Args:
            query: Natural language query to search for
            doctype_filter: Optional DocType name to filter by
            match_count: Number of results to return (default: 5)
            similarity_threshold: Minimum similarity score 0-1 (default: 0.7)

        Returns:
            List of knowledge entries with similarity scores

        Raises:
            httpx.HTTPError: If the request to Titan fails
        """
        logger.info(f"Searching Titan knowledge: '{query[:100]}...'")

        # Build request payload
        payload = {
            "query": query,
            "match_count": match_count,
            "similarity_threshold": similarity_threshold,
        }

        if doctype_filter:
            payload["doctype_filter"] = doctype_filter

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/erpnext-knowledge/search",
                headers={"x-tenant-id": self.tenant_id},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            results = response.json()

            logger.info(f"Found {len(results)} knowledge entries")
            return results

    async def get_knowledge_by_id(self, knowledge_id: int) -> Dict:
        """
        Get a specific ERPNext knowledge entry by ID.

        Args:
            knowledge_id: Knowledge entry ID

        Returns:
            Knowledge entry data

        Raises:
            httpx.HTTPError: If the request fails or knowledge not found
        """
        logger.debug(f"Fetching knowledge entry: {knowledge_id}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/api/v1/erpnext-knowledge/{knowledge_id}",
                headers={"x-tenant-id": self.tenant_id},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def list_knowledge(
        self,
        doctype: Optional[str] = None,
        module: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict]:
        """
        List ERPNext knowledge entries with optional filtering.

        Args:
            doctype: Filter by DocType name
            module: Filter by ERPNext module
            skip: Pagination offset (default: 0)
            limit: Maximum number of results (default: 100)

        Returns:
            List of knowledge entries

        Raises:
            httpx.HTTPError: If the request fails
        """
        logger.debug(
            f"Listing knowledge entries (doctype={doctype}, module={module})"
        )

        params = {"skip": skip, "limit": limit}
        if doctype:
            params["doctype"] = doctype
        elif module:
            params["module"] = module

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/api/v1/erpnext-knowledge",
                headers={"x-tenant-id": self.tenant_id},
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            results = response.json()

            logger.info(f"Retrieved {len(results)} knowledge entries")
            return results

    async def create_knowledge_entry(
        self,
        title: str,
        content: str,
        summary: str,
        doctype_name: Optional[str] = None,
        related_doctypes: Optional[List[str]] = None,
        module: Optional[str] = None,
        priority: int = 70,
        meta_data: Optional[Dict] = None,
        version: int = 1,
    ) -> Dict:
        """
        Create a new ERPNext knowledge entry.

        Args:
            title: Title of the knowledge entry
            content: Detailed content
            summary: Brief summary
            doctype_name: Related DocType name
            related_doctypes: List of related DocTypes
            module: ERPNext module
            priority: Priority (1-100, default: 70)
            meta_data: Additional metadata
            version: Version number (default: 1)

        Returns:
            Created knowledge entry data

        Raises:
            httpx.HTTPError: If the request fails
        """
        logger.info(f"Creating knowledge entry: {title}")

        payload = {
            "title": title,
            "content": content,
            "summary": summary,
            "priority": priority,
            "version": version,
        }

        if doctype_name:
            payload["doctype_name"] = doctype_name
        if related_doctypes:
            payload["related_doctypes"] = related_doctypes
        if module:
            payload["module"] = module
        if meta_data:
            payload["meta_data"] = meta_data

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/erpnext-knowledge",
                headers={"x-tenant-id": self.tenant_id},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            logger.info(f"Knowledge entry created with ID: {result.get('id')}")
            return result

    async def create_process_definition(
        self,
        process_id: str,
        name: str,
        description: str,
        category: str,
        steps: Dict,
        trigger_conditions: Optional[Dict] = None,
        prerequisites: Optional[Dict] = None,
        version: str = "1.0",
    ) -> Dict:
        """
        Create a new process definition.

        Args:
            process_id: Unique process identifier
            name: Process name
            description: Process description
            category: Process category
            steps: Process steps dictionary
            trigger_conditions: Optional trigger conditions
            prerequisites: Optional prerequisites
            version: Version string (default: "1.0")

        Returns:
            Created process definition data

        Raises:
            httpx.HTTPError: If the request fails
        """
        logger.info(f"Creating process definition: {process_id}")

        payload = {
            "process_id": process_id,
            "name": name,
            "description": description,
            "category": category,
            "steps": steps,
            "version": version,
        }

        if trigger_conditions:
            payload["trigger_conditions"] = trigger_conditions
        if prerequisites:
            payload["prerequisites"] = prerequisites

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/process-definitions",
                headers={"x-tenant-id": self.tenant_id},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            logger.info(f"Process definition created with ID: {result.get('id')}")
            return result
