from langchain_core.tools import tool
from megamind.clients.frappe_client import FrappeClient


@tool
async def get_role_permissions(
    role: str, cookie: str | None = None, access_token: str | None = None
) -> dict:
    """
    Fetches the permissions for a given role from the Frappe API.
    """
    client = FrappeClient(cookie=cookie, access_token=access_token)
    permissions = client.get_role_permissions(role=role)
    return {"permissions": permissions}
