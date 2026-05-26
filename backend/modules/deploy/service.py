from . import repository
from .model import build_deploy_record
from .schema import get_deploy_name, validate_create_payload

try:
    from backend.config import Config
    from backend.services.paas_client import PaasClient
    from backend.modules.ports.repository import resolve_blocked_ports
except ModuleNotFoundError:
    from config import Config
    from services.paas_client import PaasClient
    from modules.ports.repository import resolve_blocked_ports


MIN_CPU_M = 2000
MIN_MEM_BYTES = 4 * 1024 ** 3
NODEPORT_START = 30000
NODEPORT_END = 59999

GPU_DEVICE_MAP = {
    "NVIDIA/GPU": {
        "resource_name": "nvidia.com/gpu",
        "deploy_type": "NvidiaInfer",
        "vendor": "NVIDIA",
    },
    "Huawei/Ascend310P": {
        "resource_name": "huawei.com/Ascend310P",
        "deploy_type": "HuaweiInfer",
        "vendor": "Huawei",
    },
}


def _envelope_field(payload: dict, key: str, default: str = "") -> str:
    return str(payload.get(key) or default)


def _response_envelope(
    payload: dict,
    content: dict,
    http_status_code: int = 200,
    msg: str = "OK",
    status: int = 0,
) -> dict:
    # 部署类接口沿用旧服务 envelope，方便前端和历史脚本按 msg_id/serial/context 追踪链路。
    return {
        "msg_id": f"{_envelope_field(payload, 'msg_id')}_Resp",
        "head_id": 0,
        "context": _envelope_field(payload, "context"),
        "serial": _envelope_field(payload, "serial"),
        "version": "1.0.0.1",
        "status": status,
        "content": content,
        "token": "",
        "http_status_code": http_status_code,
        "msg": msg,
        "is_success": 200 <= http_status_code < 300,
    }


def _failed_check(key: str, label: str, display: str, message: str, detail=None) -> dict:
    result = {
        "key": key,
        "label": label,
        "status": "failed",
        "display": display,
        "message": message,
    }
    if detail is not None:
        result["detail"] = detail
    return result


def _passed_check(key: str, label: str, display: str = "通过", detail=None) -> dict:
    result = {
        "key": key,
        "label": label,
        "status": "passed",
        "display": display,
    }
    if detail is not None:
        result["detail"] = detail
    return result


def _parse_cpu_m(value) -> int:
    # Kubernetes/PaaS CPU 可能返回 "2500m" 或 "2.5"，统一换算成毫核 m。
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0
    if text.endswith("m"):
        return int(float(text[:-1] or 0))
    return int(float(text) * 1000)


def _parse_memory_bytes(value) -> int:
    # Kubernetes/PaaS 内存可能返回 Gi/Mi 等单位，预检统一换算成 bytes 后比较。
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0

    units = {
        "Ki": 1024,
        "Mi": 1024 ** 2,
        "Gi": 1024 ** 3,
        "Ti": 1024 ** 4,
        "K": 1000,
        "M": 1000 ** 2,
        "G": 1000 ** 3,
        "T": 1000 ** 4,
    }
    for suffix, multiplier in units.items():
        if text.endswith(suffix):
            return int(float(text[: -len(suffix)] or 0) * multiplier)
    return int(float(text))


def _parse_int_quantity(value) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _extract_device_request(payload: dict) -> tuple[dict | None, str | None]:
    # 资源预检只处理一种 GPU 类型，避免一次请求同时混用 NVIDIA 和 Huawei 导致模板选择不确定。
    content = payload.get("content", {}) or {}
    devices = content.get("devices")
    if not isinstance(devices, dict) or not devices:
        return None, "缺少必填字段：content.devices"

    if len(devices) != 1:
        return None, "一次预检只支持一种 GPU 类型"

    device_key, requested = next(iter(devices.items()))
    if device_key not in GPU_DEVICE_MAP:
        return None, f"不支持的 GPU 类型：{device_key}"

    requested_count = _parse_int_quantity(requested)
    if requested_count <= 0:
        return None, "GPU 数量必须大于 0"

    profile = GPU_DEVICE_MAP[device_key]
    deploy_type = str(content.get("deployType") or "").strip()
    if deploy_type and deploy_type != profile["deploy_type"]:
        return None, f"{device_key} 必须匹配 deployType={profile['deploy_type']}"

    gpu_resource_name = str(payload.get("gpu_resource_name") or "").strip()
    if gpu_resource_name and gpu_resource_name != profile["resource_name"]:
        return None, f"{device_key} 必须匹配 gpu_resource_name={profile['resource_name']}"

    return {
        "device_key": device_key,
        "requested": requested_count,
        **profile,
    }, None


def _deployment_items(result) -> list:
    # PaaS 列表接口通常把资源放在 items 中；异常结构按空列表处理，避免后续遍历报错。
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return result["items"]
    return []


def _existing_node_ports(services_result) -> set[int]:
    # 从已有 Service 中提取 nodePort，后续随机端口必须避开这些已经被集群占用的端口。
    ports = set()
    if not isinstance(services_result, dict):
        return ports
    for service in services_result.get("items", []) or []:
        for port_obj in (service.get("spec", {}) or {}).get("ports", []) or []:
            node_port = port_obj.get("nodePort")
            if isinstance(node_port, int):
                ports.add(node_port)
    return ports


def _deployment_exists(deployments: list, name: str) -> bool:
    # 预检阶段只做同名检测，不加锁；真正创建时仍需要再检查一次，避免并发窗口。
    if not name:
        return False
    for item in deployments:
        metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
        if metadata.get("name") == name:
            return True
    return False


def check_available(payload: dict) -> dict:
    # 资源预检只判断“当前配置是否具备创建条件”，不会创建 Deployment、Service 或占用端口。
    device_request, error = _extract_device_request(payload)
    if error:
        content = {
            "can_create": False,
            "reason": error,
            "checks": [
                _failed_check(
                    "gpu_available",
                    "GPU 可用余量",
                    "未通过",
                    error,
                )
            ],
            "devices": (payload.get("content", {}) or {}).get("devices", {}),
        }
        return _response_envelope(payload, content, 400, error, -1)

    if not Config.DCE_API_BASE:
        msg = "PaaS 地址未配置"
        return _response_envelope(payload, {"can_create": False, "reason": msg, "checks": []}, 500, msg, -1)
    if not Config.DCE_TOKEN:
        msg = "PaaS token 未配置"
        return _response_envelope(payload, {"can_create": False, "reason": msg, "checks": []}, 500, msg, -1)

    client = PaasClient(Config.DCE_API_BASE, Config.DCE_TOKEN)
    # 第一步：查询集群资源汇总，用于计算 GPU 总量、CPU/内存 allocatable 与 allocated。
    cluster_path = f"/clusters/{Config.DCE_CLUSTER}"
    cluster_status, cluster_result = client.request_with_status("GET", cluster_path)
    if cluster_status != 200 or not isinstance(cluster_result, dict):
        msg = "无法获取资源汇总"
        return _response_envelope(
            payload,
            {
                "can_create": False,
                "reason": msg,
                "checks": [],
                "response": cluster_result,
            },
            502 if cluster_status != 504 else 504,
            msg,
            -1,
        )

    # 第二步：查询当前命名空间下已有 Deployment。旧脚本约定一个 Deployment 近似占一张卡。
    deployment_path = f"/clusters/{Config.DCE_CLUSTER}/namespaces/{Config.DCE_NAMESPACE}/deployments"
    deploy_status, deploy_result = client.request_with_status("GET", deployment_path)
    if deploy_status != 200:
        msg = "获取部署列表失败"
        return _response_envelope(
            payload,
            {
                "can_create": False,
                "reason": msg,
                "checks": [],
                "response": deploy_result,
            },
            502 if deploy_status != 504 else 504,
            msg,
            -1,
        )

    deployments = _deployment_items(deploy_result)
    allocatable = (cluster_result.get("status", {}) or {}).get("resourceSummary", {}).get("allocatable", {}) or {}
    allocated = (cluster_result.get("status", {}) or {}).get("resourceSummary", {}).get("allocated", {}) or {}

    resource_name = device_request["resource_name"]
    gpu_total = _parse_int_quantity(allocatable.get(resource_name))

    # 新规则：优先使用 PaaS resourceSummary.allocated 中的 GPU 已分配数量。
    # 如果 PaaS 没有返回该资源名，再退回旧脚本逻辑：用 Deployment 数量估算已占 GPU。
    if resource_name in allocated:
        gpu_used = _parse_int_quantity(allocated.get(resource_name))
        gpu_used_source = "resourceSummary.allocated"
    else:
        gpu_used = len(deployments)
        gpu_used_source = "deployment_count_fallback"
    gpu_available = max(gpu_total - gpu_used, 0)
    requested = device_request["requested"]

    checks = []
    # 检查项 1：GPU 可用余量。页面展示“可用 N 张”，比“资源设备可用”更贴近原脚本逻辑。
    gpu_detail = {
        "resource_name": resource_name,
        "device_key": device_request["device_key"],
        "requested": requested,
        "available": gpu_available,
        "total": gpu_total,
        "used": gpu_used,
        "used_source": gpu_used_source,
        "vendor": device_request["vendor"],
    }
    if gpu_available >= requested:
        checks.append(_passed_check("gpu_available", "GPU 可用余量", f"可用 {gpu_available} / {gpu_total} 张", gpu_detail))
    else:
        checks.append(
            _failed_check(
                "gpu_available",
                "GPU 可用余量",
                f"可用 {gpu_available} / {gpu_total} 张",
                f"当前可用 {gpu_available} 张，申请 {requested} 张",
                gpu_detail,
            )
        )

    cpu_available_m = _parse_cpu_m(allocatable.get("cpu")) - _parse_cpu_m(allocated.get("cpu"))
    mem_available_bytes = _parse_memory_bytes(allocatable.get("memory")) - _parse_memory_bytes(allocated.get("memory"))
    # 检查项 2：CPU/内存余量。沿用旧脚本最低门槛：CPU 2000m、内存 4GiB。
    cpu_mem_detail = {
        "cpu_available_m": cpu_available_m,
        "cpu_required_m": MIN_CPU_M,
        "mem_available_bytes": mem_available_bytes,
        "mem_required_bytes": MIN_MEM_BYTES,
    }
    cpu_mem_reasons = []
    if cpu_available_m < MIN_CPU_M:
        cpu_mem_reasons.append(f"CPU 可用 {cpu_available_m}m，需至少 {MIN_CPU_M}m")
    if mem_available_bytes < MIN_MEM_BYTES:
        cpu_mem_reasons.append(f"内存可用 {mem_available_bytes}B，需至少 {MIN_MEM_BYTES}B")
    if cpu_mem_reasons:
        checks.append(
            _failed_check(
                "cpu_memory",
                "CPU / 内存余量",
                "未通过",
                "；".join(cpu_mem_reasons),
                cpu_mem_detail,
            )
        )
    else:
        checks.append(_passed_check("cpu_memory", "CPU / 内存余量", "通过", cpu_mem_detail))

    # 检查项 3：NodePort 自动避让。这里只确认“存在可选端口”，不提前占用端口。
    service_path = f"/clusters/{Config.DCE_CLUSTER}/namespaces/{Config.DCE_NAMESPACE}/services"
    service_status, service_result = client.request_with_status("GET", service_path)
    if service_status == 200:
        service_ports = _existing_node_ports(service_result)
        try:
            # 封闭端口已经迁入本服务 MySQL，部署模块直接复用 repository，避免 HTTP 调自己。
            blocked_ports = set(resolve_blocked_ports().get("blocked_ports", []))
            blocked_error = None
        except Exception as exc:
            blocked_ports = set()
            blocked_error = str(exc)

        unavailable_ports = {
            port for port in service_ports.union(blocked_ports)
            if NODEPORT_START <= port <= NODEPORT_END
        }
        has_candidate = len(unavailable_ports) < (NODEPORT_END - NODEPORT_START + 1)
        nodeport_detail = {
            "range_start": NODEPORT_START,
            "range_end": NODEPORT_END,
            "service_node_ports": sorted(service_ports),
            "blocked_ports": sorted(blocked_ports),
            "unavailable_count": len(unavailable_ports),
        }
        if blocked_error:
            checks.append(
                _failed_check(
                    "nodeport",
                    "NodePort 自动避让",
                    "未通过",
                    f"读取封闭端口失败：{blocked_error}",
                    nodeport_detail,
                )
            )
        elif has_candidate:
            checks.append(_passed_check("nodeport", "NodePort 自动避让", "通过", nodeport_detail))
        else:
            checks.append(
                _failed_check(
                    "nodeport",
                    "NodePort 自动避让",
                    "未通过",
                    "NodePort 可选范围已无可用端口",
                    nodeport_detail,
                )
            )
    else:
        checks.append(
            _failed_check(
                "nodeport",
                "NodePort 自动避让",
                "未通过",
                "获取 Service 列表失败，无法确认 NodePort 可避让",
                {"response": service_result},
            )
        )

    deploy_name = get_deploy_name(payload)
    # 检查项 4：同名部署校验。没有传 name 时允许通过，创建接口最终生成名称后还要再校验。
    if deploy_name and _deployment_exists(deployments, deploy_name):
        checks.append(
            _failed_check(
                "deploy_lock",
                "部署锁与并发校验",
                "未通过",
                f"部署 {deploy_name} 已存在",
                {"deployment_name": deploy_name},
            )
        )
    else:
        checks.append(_passed_check("deploy_lock", "部署锁与并发校验", "通过", {"deployment_name": deploy_name or None}))

    failed_checks = [check for check in checks if check["status"] == "failed"]
    # 只要任一检查项失败，就不允许创建；reason 取第一个失败项，便于前端顶部展示。
    can_create = not failed_checks
    reason = "资源预检通过" if can_create else failed_checks[0].get("message", "资源预检未通过")
    http_status = 200 if can_create else 400

    content = {
        "can_create": can_create,
        "reason": reason,
        "checks": checks,
        "cpu_available_m": cpu_available_m,
        "mem_available_bytes": mem_available_bytes,
        "gpu_details": {
            resource_name: {
                "requested": requested,
                "available": gpu_available,
                "total": gpu_total,
                "used": gpu_used,
                "used_source": gpu_used_source,
            }
        },
        "total_deployments": gpu_used,
        "devices": (payload.get("content", {}) or {}).get("devices", {}),
    }
    return _response_envelope(payload, content, http_status, reason, 0 if can_create else -1)


def create_default(payload: dict) -> tuple[dict, int]:
    # TODO: 按 deployType 区分 NVIDIA/Huawei，组装对应 Deployment/Service 模板后调用 PaaS。
    valid, message = validate_create_payload(payload)
    if not valid:
        return {"is_success": False, "msg": message}, 400

    name = "pending-implementation"
    repository.save_deploy_instance(build_deploy_record(name, payload))
    return {"deployment_name": name, "payload": payload}, 200


def retrieve(payload: dict) -> dict:
    # TODO: 调用 PaaS 查询 Deployment，再按 app/name label 查询 Pod 状态并合并返回。
    name = get_deploy_name(payload)
    return {"deployment_name": name, "deployment": None, "pods": [], "summary": {}}


def release(payload: dict) -> dict:
    # TODO: 调用 PaaS 删除 Deployment 和 Service；车间模式没有 Service 时允许 404。
    name = get_deploy_name(payload)
    return repository.update_deploy_status(name, "released")


def reset(payload: dict) -> dict:
    # TODO: 调用 PaaS/Kubernetes restart 能力，保持和旧脚本 /restart 路径一致。
    name = get_deploy_name(payload)
    return {"deployment_name": name, "is_success": True}


def list_deployments() -> dict:
    # TODO: 查询 PaaS deployments 列表，并和 deploy_instance 表中的创建人、端口、日志路径合并。
    return {"items": repository.list_deploy_instances()}
