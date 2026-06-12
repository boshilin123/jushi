import time

try:
    from backend.config import Config
    from backend.services.paas_client import PaasClient
except ModuleNotFoundError:
    from config import Config
    from services.paas_client import PaasClient

from .schema import get_envelope_field


def _response_envelope(
    payload: dict,
    content: dict,
    http_status_code: int = 200,
    msg: str = "OK",
    status: int = 0,
) -> dict:
    # 兼容历史 app_x86/app_arm 脚本的统一响应包，前端也按这个结构读取 msg_id、serial、content。
    return {
        "msg_id": get_envelope_field(payload, "msg_id"),
        "head_id": 0,
        "context": get_envelope_field(payload, "context"),
        "serial": get_envelope_field(payload, "serial"),
        "version": "1.0",
        "status": status,
        "content": content,
        "token": "",
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "timestamp": int(time.time() * 1000),
        "http_status_code": http_status_code,
        "msg": msg,
        "is_success": 200 <= http_status_code < 300,
    }


def retrieve_clusters(payload: dict) -> tuple[dict, int]:
    # 集群查询是部署链路的第一步：只验证 PaaS 地址、token 和 /clusters 可访问性，不写数据库。
    if not Config.DCE_API_BASE:
        return _response_envelope(
            payload,
            {"error": "DCE_API_BASE is not configured"},
            http_status_code=500,
            msg="PaaS 地址未配置",
            status=-1,
        ), 500

    if not Config.DCE_TOKEN:
        return _response_envelope(
            payload,
            {"error": "DCE_TOKEN is not configured"},
            http_status_code=500,
            msg="PaaS token 未配置",
            status=-1,
        ), 500

    client = PaasClient(Config.DCE_API_BASE, Config.DCE_TOKEN)
    # DCE_API_BASE 已经包含 /apis/kpanda.io/v1alpha1，平台集群列表路径只需要追加 /clusters。
    status_code, result = client.request_with_status("GET", "/clusters")

    if 200 <= status_code < 300:
        return _response_envelope(
            payload,
            result if isinstance(result, dict) else {"data": result},
            http_status_code=status_code,
            msg="OK",
            status=0,
        ), status_code

    msg = "集群查询超时" if status_code == 504 else "集群查询失败"
    return _response_envelope(
        payload,
        {"response": result},
        http_status_code=status_code,
        msg=msg,
        status=-1,
    ), status_code
