class PaasClient:
    # PaaS/DCE 平台 HTTP 客户端。当前主要用于调用 /clusters、/deployments、/services 等平台接口。
    def __init__(self, api_base: str, token: str):
        self.api_base = api_base.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, json_body=None):
        # requests 是 Python 第三方 HTTP 包；这里惰性导入，避免只打开 Swagger 时就强依赖本地测试环境已安装该包。
        import requests

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

    def request_with_status(self, method: str, path: str, json_body=None, timeout=30):
        # 给业务接口使用：不抛出 HTTPError，保留 PaaS 原始状态码和响应体，方便前端/Swagger 排查。
        import requests

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.request(
                method,
                f"{self.api_base}{path}",
                headers=headers,
                json=json_body,
                timeout=timeout,
                verify=False,
            )
        except requests.Timeout as exc:
            return 504, {"error": str(exc)}
        except requests.RequestException as exc:
            return 502, {"error": str(exc)}

        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, {"raw": response.text}
