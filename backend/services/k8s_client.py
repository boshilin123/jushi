from urllib.parse import urlencode


class K8sClient:
    # 直接调用 Kubernetes 原生 API，绕过 PaaS 对日志和 scale 的封装差异。
    def __init__(self, api_base: str, token: str):
        self.api_base = (api_base or "").rstrip("/")
        self.token = token

    @classmethod
    def from_config(cls, config):
        api_base = config.K8S_API_BASE or _derive_k8s_api_base(config.DCE_API_BASE)
        token = config.K8S_TOKEN or config.DCE_TOKEN
        return cls(api_base, token)

    def _request(self, method: str, path: str, json_body=None, headers=None):
        import requests

        request_headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if headers:
            request_headers.update(headers)

        try:
            response = requests.request(
                method,
                f"{self.api_base}{path}",
                headers=request_headers,
                json=json_body,
                timeout=30,
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

    def patch_deployment_replicas(self, namespace: str, name: str, replicas: int):
        path = f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}"
        body = {"spec": {"replicas": replicas}}
        return self._request(
            "PATCH",
            path,
            json_body=body,
            headers={"Content-Type": "application/merge-patch+json"},
        )

    def list_pods_by_app(self, namespace: str, app_name: str):
        query = urlencode({"labelSelector": f"app={app_name}"})
        path = f"/api/v1/namespaces/{namespace}/pods?{query}"
        return self._request("GET", path)

    def pod_logs(self, namespace: str, pod_name: str, tail_lines: int = 200):
        query = urlencode({"tailLines": tail_lines})
        path = f"/api/v1/namespaces/{namespace}/pods/{pod_name}/log?{query}"
        return self._request("GET", path)


def _derive_k8s_api_base(api_base: str) -> str:
    # DCE_API_BASE 常见形态为 https://host:port/apis/kpanda.io/v1alpha1，K8s 原生 API 根地址只保留 scheme/host/port。
    text = (api_base or "").rstrip("/")
    marker = "/apis/kpanda.io/"
    if marker in text:
        return text.split(marker, 1)[0]
    return text
