import requests
from loguru import logger
from ..utils.config import settings


class FrappeClient:
    def __init__(
        self, cookie: str | None = None, access_token: str | None = None
    ) -> None:
        self.frappe_url = settings.frappe_url
        self.api_key = settings.frappe_api_key
        self.api_secret = settings.frappe_api_secret
        self.headers = dict()
        if cookie:
            self.headers["Cookie"] = cookie
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"

    def get_teams(self):
        """
        Retrieves a list of teams from Frappe Drive.
        """
        if not all([self.frappe_url, self.api_key, self.api_secret]):
            logger.warning("Frappe credentials not set. Skipping team retrieval.")
            return {}

        try:
            response = requests.get(
                f"{self.frappe_url}/api/method/drive.api.permissions.get_teams",
                headers=self.headers,
                params={"details": 1},
            )
            response.raise_for_status()
            return response.json().get("message", {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching teams from Frappe: {e}")
            return {}

    def get_files(self, team, entity_name=None):
        """
        Retrieves a list of files from Frappe Drive.
        """
        if not all([self.frappe_url, self.api_key, self.api_secret]):
            logger.warning("Frappe credentials not set. Skipping file retrieval.")
            return []

        all_files = []
        try:
            params = {"team": team}
            if entity_name:
                params["entity_name"] = entity_name

            response = requests.get(
                f"{self.frappe_url}/api/method/drive.api.list.files",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            files = response.json().get("message", [])

            for file in files:
                if file.get("is_group") == 1:
                    all_files.extend(self.get_files(team, file.get("name")))
                else:
                    all_files.append(file)

            return all_files
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching files from Frappe: {e}")
            return []

    def get_file_content(self, file_name):
        """
        Retrieves the content of a specific file.
        """
        if not self.frappe_url:
            return None

        try:
            params = {"entity_name": file_name}
            file_response = requests.get(
                f"{self.frappe_url}/api/method/drive.api.files.get_file_content",
                headers=self.headers,
                params=params,
            )
            file_response.raise_for_status()
            return file_response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching file content: {e}")
            return None

    def get_default_company(self):
        """
        Retrieves the default company from Frappe's Global Defaults.
        """
        if not all([self.frappe_url, self.api_key, self.api_secret]):
            logger.warning(
                "Frappe credentials not set. Skipping default company retrieval."
            )
            return None

        try:
            response = requests.get(
                f"{self.frappe_url}/api/resource/Global Defaults/Global Defaults",
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            return data.get("default_company")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching default company from Frappe: {e}")
            return None

    def get_role_permissions(self, role: str):
        """
        Retrieves the permissions for a specific role.
        """
        if not self.frappe_url:
            return None

        try:
            response = requests.post(
                f"{self.frappe_url}/api/method/workspace.workspace.role_manager.get_permissions",
                headers=self.headers,
                data={"doctype": "", "role": role},
            )
            response.raise_for_status()
            return response.json().get("message", {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching role permissions from Frappe: {e}")
            return None

    def get_roles(self):
        """
        Retrieves a list of roles from Frappe.
        """
        if not self.frappe_url:
            return None

        try:
            response = requests.get(
                f"{self.frappe_url}/api/method/frappe.client.get_list",
                headers=self.headers,
                params={
                    "doctype": "Role",
                    "order_by": "modified desc",
                    "limit_page_length": 500,
                },
            )
            response.raise_for_status()
            data = response.json().get("message", {})
            return [row.get("name", "") for row in data]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching roles from Frappe: {e}")
            return None

    def get_current_user_info(self) -> dict:
        """
        Fetch current user's information including name, email, roles, and department.

        Returns:
            dict: User information with keys: full_name, email, roles, department
        """
        try:
            # Method 1: Get current user identity
            user_response = requests.get(
                f"{self.frappe_url}/api/method/frappe.auth.get_logged_user",
                headers=self.headers,
                timeout=10,
            )
            user_response.raise_for_status()
            username = user_response.json().get("message", "")

            if not username:
                logger.warning("Could not retrieve current username")
                return {}

            # Method 2: Fetch full user document with specific fields
            user_doc_response = requests.get(
                f"{self.frappe_url}/api/resource/User/{username}",
                headers=self.headers,
                params={
                    "fields": '["full_name", "email", "roles", "department"]'
                },
                timeout=10,
            )
            user_doc_response.raise_for_status()
            response_json = user_doc_response.json()
            user_data = response_json.get("data", {})

            # Extract roles from the child table structure
            roles_list = []
            roles_data = user_data.get("roles", [])
            if isinstance(roles_data, list):
                for role_item in roles_data:
                    if isinstance(role_item, dict):
                        role_name = role_item.get("role")
                        if role_name:
                            roles_list.append(role_name)

            logger.info(f"Successfully fetched user info for: {user_data.get('email', username)}")

            return {
                "full_name": user_data.get("full_name", ""),
                "email": user_data.get("email", username),
                "roles": roles_list,
                "department": user_data.get("department", ""),
            }
        except Exception as e:
            logger.error(f"Failed to fetch user info: {e}", exc_info=True)
            return {}
