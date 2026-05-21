import requests


class PaasClient:
    def __init__(self, api_base: str, token: str):
        self.api_base = api_base.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, json_body=None):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        response = requests.request(
            method,
            f"{self.api_base}{path}",
            headers=headers,
            json=json_body,
            timeout=30,
            verify=False,
        )
        response.raise_for_status()
        return response.json()
