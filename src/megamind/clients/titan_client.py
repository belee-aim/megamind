import httpx
from loguru import logger

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
                    "file_names": file_names,
                    "callback_url": callback_url,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            job_id = data.get("id")

            logger.info(f"Titan processing job created: {job_id}")
            return job_id
