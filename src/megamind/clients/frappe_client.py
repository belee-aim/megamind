import requests
from ..utils.config import settings

class FrappeClient:
    def __init__(self):
        self.frappe_url = settings.frappe_url
        self.api_key = settings.frappe_api_key
        self.api_secret = settings.frappe_api_secret
        self.headers = {
            "Authorization": f"token {self.api_key}:{self.api_secret}"
        }

    def get_teams(self):
        """
        Retrieves a list of teams from Frappe Drive.
        """
        if not all([self.frappe_url, self.api_key, self.api_secret]):
            print("Frappe credentials not set. Skipping team retrieval.")
            return {}

        try:
            response = requests.get(
                f"{self.frappe_url}/api/method/drive.api.permissions.get_teams",
                headers=self.headers,
                params={"details": 1}
            )
            response.raise_for_status()
            return response.json().get("message", {})
        except requests.exceptions.RequestException as e:
            print(f"Error fetching teams from Frappe: {e}")
            return {}

    def get_files(self, team, entity_name=None):
        """
        Retrieves a list of files from Frappe Drive.
        """
        if not all([self.frappe_url, self.api_key, self.api_secret]):
            print("Frappe credentials not set. Skipping file retrieval.")
            return []

        all_files = []
        try:
            params = {"team": team}
            if entity_name:
                params["entity_name"] = entity_name
            
            response = requests.get(
                f"{self.frappe_url}/api/method/drive.api.list.files",
                headers=self.headers,
                params=params
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
            print(f"Error fetching files from Frappe: {e}")
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
                params=params
            )
            file_response.raise_for_status()
            return file_response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching file content: {e}")
            return None
