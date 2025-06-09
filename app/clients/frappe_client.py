import requests
from app.utils.config import settings

class FrappeClient:
    def __init__(self):
        self.frappe_url = settings.frappe_url
        self.api_key = settings.frappe_api_key
        self.api_secret = settings.frappe_api_secret
        self.headers = {
            "Authorization": f"token {self.api_key}:{self.api_secret}"
        }

    def get_files(self):
        """
        Retrieves a list of files from Frappe Drive.
        """
        if not all([self.frappe_url, self.api_key, self.api_secret]):
            print("Frappe credentials not set. Skipping file retrieval.")
            return []

        try:
            response = requests.get(
                f"{self.frappe_url}/api/resource/File",
                headers=self.headers,
                params={"fields": '["file_name", "file_url"]'}
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching files from Frappe: {e}")
            return []

    def get_file_content(self, file_url):
        """
        Retrieves the content of a specific file.
        """
        if not self.frappe_url:
            return None
            
        try:
            file_response = requests.get(f"{self.frappe_url}{file_url}", headers=self.headers)
            file_response.raise_for_status()
            return file_response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching file content: {e}")
            return None
