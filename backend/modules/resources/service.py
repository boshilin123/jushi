import json
import os
import time
from datetime import datetime, timedelta

"""
资源中心接口说明。

这个模块不是直接维护一套自己的资源数据，而是把现有 PaaS / Kubernetes
已经暴露出来的资源信息重新整理成产品页面需要的结构。新人阅读时可以先记住：

1. PaaS 的 cluster resourceSummary 是第一数据源，用于拿集群级 allocatable / allocated。
2. PaaS / K8s 的 node 列表用于补节点维度、GPU label、vGPU 模式和显卡型号。
3. K8s Pod requests/limits 用于兜底反推“已分配资源”，避免 PaaS allocated 缺失或不准。
4. 当前返回的是“资源分配率/容量估算”，不是 DCGM、HAMI、npu-smi 这类真实运行利用率。
5. 趋势接口依赖 summary 写入 MySQL resource_snapshot 的历史快照，历史不足时用当前值兜底。
"""

try:
    from backend.config import Config
    from backend.services.paas_client import PaasClient
    from backend.services.k8s_client import K8sClient
    from backend.db.mysql import get_connection
except ModuleNotFoundError:
    from config import Config
    from services.paas_client import PaasClient
    from services.k8s_client import K8sClient
    from db.mysql import get_connection


GPU_RESOURCE_META = {
    "nvidia.com/gpu": {
        "display_name": "NVIDIA GPU",
        "vendor": "NVIDIA",
        "kind": "physical_gpu",
        "unit": "GPU",
    },
    "nvidia.com/vgpu": {
        "display_name": "NVIDIA vGPU",
        "vendor": "NVIDIA",
        "kind": "vgpu",
        "unit": "vGPU",
    },
    "nvidia.com/gpucores": {
        "display_name": "GPU Compute",
        "vendor": "NVIDIA",
        "kind": "gpu_core",
        "unit": "core",
    },
    "nvidia.com/gpumem": {
        "display_name": "GPU Memory",
        "vendor": "NVIDIA",
        "kind": "gpu_memory",
        "unit": "MiB",
    },
    "huawei.com/Ascend310P": {
        "display_name": "Huawei Ascend310P",
        "vendor": "Huawei",
        "kind": "npu",
        "unit": "NPU",
    },
}

# 物理加速卡：用于资源中心“显卡”数量。
PHYSICAL_GPU_KEYS = ["nvidia.com/gpu", "huawei.com/Ascend310P"]

# 虚拟加速卡：用于资源中心“vGPU”数量。
VGPU_KEYS = ["nvidia.com/vgpu"]

# 兼容旧字段名，后续代码中 gpu_total 只表示物理卡。
GPU_COUNT_KEYS = PHYSICAL_GPU_KEYS

GPU_MEMORY_KEYS = ["nvidia.com/gpumem"]
GPU_CORE_KEYS = ["nvidia.com/gpucores"]

UNKNOWN_GPU_MODEL = "Unknown"
METRIC_SOURCE = "paas_cluster_resourceSummary + k8s_node_label + cluster_pod_resource_fallback"


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _ok(data=None):
    return {
        "is_success": True,
        "msg": "OK",
        "time": _now(),
        "timestamp": int(time.time() * 1000),
        **(data or {}),
    }


def _error(msg, status_code=500, response=None):
    return {
        "is_success": False,
        "msg": msg,
        "http_status_code": status_code,
        "response": response or {},
        "time": _now(),
        "timestamp": int(time.time() * 1000),
    }


def _paas_client():
    # PaaS/DCE 是资源中心最主要的数据入口；没有平台地址或 token 时资源接口不能工作。
    if not Config.DCE_API_BASE:
        return None, _error("DCE_API_BASE is not configured", 500)
    if not Config.DCE_TOKEN:
        return None, _error("DCE_TOKEN is not configured", 500)
    return PaasClient(Config.DCE_API_BASE, Config.DCE_TOKEN), None


def _k8s_client():
    # Kubernetes 原生 API 用作补充入口，主要查 nodes、pods、resourcequotas 等 PaaS 包装不稳定的对象。
    client = K8sClient.from_config(Config)
    if not client.api_base:
        return None, _error("K8S_API_BASE is not configured", 500)
    if not client.token:
        return None, _error("K8S_TOKEN is not configured", 500)
    return client, None


def _snapshot_enabled():
    return os.getenv("RESOURCE_SNAPSHOT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}


def _snapshot_interval_seconds():
    try:
        return max(int(os.getenv("RESOURCE_SNAPSHOT_MIN_INTERVAL_SECONDS", "60")), 10)
    except ValueError:
        return 60


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _snapshot_retention_days():
    """
    资源快照保留天数。
    默认保留 30 天；设置为 0 或负数表示不清理。
    """
    return _env_int("RESOURCE_SNAPSHOT_RETENTION_DAYS", 30)


def _capacity_estimation_enabled():
    """
    当集群没有暴露 nvidia.com/gpumem / nvidia.com/gpucores 时，
    是否按物理卡数量估算显存容量和算力容量。
    """
    return _env_bool("RESOURCE_CAPACITY_ESTIMATION_ENABLED", True)


def _gpu_card_memory_gib():
    """
    单张物理卡估算显存容量，默认按 A10 24GiB。
    如果现场不是 A10，可以通过环境变量覆盖。
    """
    return _env_float("GPU_CARD_MEMORY_GIB", 24)


def _gpu_card_compute_units():
    """
    单张物理卡估算算力单位。
    这里不是 TFLOPS 真实值，只是资源中心展示用的标准化容量单位。
    """
    return _env_float("GPU_CARD_COMPUTE_UNITS", 100)


def _vgpu_per_gpu():
    """
    当无法拿到物理卡数量、只能拿到 vGPU 数量时，用这个比例反推物理卡数量。
    当前环境 4 张物理卡暴露 40 个 vGPU，所以默认 10。
    """
    return max(_env_int("VGPU_PER_GPU", 10), 1)


def _estimated_card_count(physical_gpu_total, vgpu_total):
    """
    优先使用真实物理卡数量。
    如果物理卡数量没有返回，但有 vGPU，则按 VGPU_PER_GPU 估算物理卡数量。
    """
    physical_gpu_total = int(physical_gpu_total or 0)
    vgpu_total = int(vgpu_total or 0)

    if physical_gpu_total > 0:
        return physical_gpu_total

    if vgpu_total > 0:
        per_gpu = _vgpu_per_gpu()
        return max(int((vgpu_total + per_gpu - 1) / per_gpu), 1)

    return 0


def _allocation_ratio(physical_gpu_used, physical_gpu_total, vgpu_used, vgpu_total):
    """
    用于估算显存/算力分配率。
    优先参考物理卡分配率，同时兼容 vGPU 分配率。
    """
    ratios = []

    if physical_gpu_total:
        ratios.append(physical_gpu_used / physical_gpu_total)

    if vgpu_total:
        ratios.append(vgpu_used / vgpu_total)

    if not ratios:
        return 0

    return min(max(max(ratios), 0), 1)


def _round2(value):
    value = round(float(value or 0), 2)
    return int(value) if value.is_integer() else value


def _split_value(value, count):
    if not count:
        return 0
    return _round2((value or 0) / count)


def _cleanup_old_resource_snapshots(cursor):
    days = _snapshot_retention_days()
    if days <= 0:
        return

    cutoff = datetime.now() - timedelta(days=days)
    cursor.execute(
        """
        DELETE FROM resource_snapshot
        WHERE created_at < %s
        """,
        (cutoff,),
    )


def _json_dumps(data):
    return json.dumps(data, ensure_ascii=False, default=str)


def _json_loads(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


def _to_datetime(value):
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value[:19], fmt)
            except ValueError:
                continue

    return None


def _save_resource_snapshot(snapshot_type, payload):
    """
    保存资源快照到 resource_snapshot。

    注意：
    1. 这个动作不能影响主接口返回，所以所有异常都吞掉。
    2. 默认同一种 snapshot_type 每 60 秒最多写一次，避免前端刷新导致数据库爆量。
    3. 每次成功写入后，顺带清理过期快照，默认保留 30 天。
    """
    if not _snapshot_enabled():
        return False

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT created_at
                FROM resource_snapshot
                WHERE snapshot_type = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (snapshot_type,),
            )
            latest = cursor.fetchone()

            latest_time = _to_datetime(latest.get("created_at")) if latest else None
            if latest_time:
                elapsed = (datetime.now() - latest_time).total_seconds()
                if elapsed < _snapshot_interval_seconds():
                    return False

            cursor.execute(
                """
                INSERT INTO resource_snapshot (snapshot_type, payload)
                VALUES (%s, %s)
                """,
                (snapshot_type, _json_dumps(payload)),
            )

            _cleanup_old_resource_snapshots(cursor)

            return True
    except Exception:
        return False


def _load_resource_snapshots(snapshot_type, start_time, limit=500):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload, created_at
                FROM resource_snapshot
                WHERE snapshot_type = %s
                  AND created_at >= %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (snapshot_type, start_time, int(limit)),
            )
            rows = cursor.fetchall() or []
    except Exception:
        return []

    result = []
    for row in rows:
        payload = _json_loads(row.get("payload"))
        created_at = _to_datetime(row.get("created_at"))
        if not payload or not created_at:
            continue
        result.append({
            "payload": payload,
            "created_at": created_at,
        })

    return result


def _trend_start_time(range_value):
    now = datetime.now()

    if range_value == "24h":
        return now - timedelta(hours=24)

    if range_value == "7d":
        return now - timedelta(days=7)

    return now - timedelta(hours=1)


def _trend_time_label(created_at, range_value):
    if range_value == "7d":
        return created_at.strftime("%m-%d")
    return created_at.strftime("%H:%M")


def _trend_items_from_snapshots(snapshots, range_value):
    items = []

    for row in snapshots:
        payload = row.get("payload") or {}
        cards = payload.get("cards") or {}
        created_at = row.get("created_at")

        if not created_at:
            continue

        gpu_mem_alloc_percent = cards.get("gpu_mem_alloc_percent", cards.get("gpu_mem_percent", 0))
        gpu_core_alloc_percent = cards.get("gpu_core_alloc_percent", cards.get("gpu_core_percent", 0))

        items.append({
            "time": _trend_time_label(created_at, range_value),

            "gpu_alloc_percent": cards.get("gpu_alloc_percent", 0),
            "vgpu_alloc_percent": cards.get("vgpu_alloc_percent", 0),

            "gpu_mem_percent": gpu_mem_alloc_percent,
            "gpu_mem_alloc_percent": gpu_mem_alloc_percent,
            "gpu_mem_usage_percent": cards.get("gpu_mem_usage_percent"),

            "gpu_core_percent": gpu_core_alloc_percent,
            "gpu_core_alloc_percent": gpu_core_alloc_percent,
            "gpu_core_usage_percent": cards.get("gpu_core_usage_percent"),

            "usage_metric_ready": cards.get("usage_metric_ready", False),
        })

    return items


def _safe_get(obj, *keys, default=None):
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def _extract_items(result):
    if not isinstance(result, dict):
        return []

    candidates = [
        result.get("items"),
        _safe_get(result, "data", "items"),
        _safe_get(result, "content", "items"),
        _safe_get(result, "response", "items"),
    ]

    for items in candidates:
        if isinstance(items, list):
            return items

    return []


def _parse_number(text):
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return 0


def _parse_cpu_m(value):
    if value is None:
        return 0

    text = str(value).strip()
    if not text:
        return 0

    if text.endswith("m"):
        return int(_parse_number(text[:-1]))

    return int(_parse_number(text) * 1000)


def _parse_memory_bytes(value):
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
            return int(_parse_number(text[: -len(suffix)]) * multiplier)

    return int(_parse_number(text))


def _parse_scalar(value):
    if value is None:
        return 0

    text = str(value).strip()
    if not text:
        return 0

    if text.endswith("m"):
        return int(_parse_number(text[:-1]))

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
            return int(_parse_number(text[: -len(suffix)]) * multiplier)

    return int(_parse_number(text))


def _parse_gpumem_mib(value):
    if value is None:
        return 0

    text = str(value).strip()
    if not text:
        return 0

    if text.endswith("Gi"):
        return int(_parse_number(text[:-2]) * 1024)
    if text.endswith("Mi"):
        return int(_parse_number(text[:-2]))
    if text.endswith("G"):
        return int(_parse_number(text[:-1]) * 1000 / 1024)
    if text.endswith("M"):
        return int(_parse_number(text[:-1]) * 1000 * 1000 / 1024 / 1024)

    # HAMI 的 nvidia.com/gpumem 常见是纯数字，按 MiB 处理。
    return int(_parse_number(text))


def _parse_resource(key, value):
    if key == "cpu":
        return _parse_cpu_m(value)
    if key == "memory":
        return _parse_memory_bytes(value)
    if key == "nvidia.com/gpumem":
        return _parse_gpumem_mib(value)
    return _parse_scalar(value)


def _resource_get(resource_map, key):
    value = (resource_map or {}).get(key)
    if isinstance(value, (int, float)):
        return int(value)
    return _parse_resource(key, value)


def _percent(used, total):
    if not total:
        return 0
    return round(used * 100 / total)


def _bytes_to_gib(value):
    return round(value / 1024 ** 3, 2)


def _mib_to_gib(value):
    return round(value / 1024, 2)


def _sum_resources(resource_map, keys):
    total = 0
    for key in keys:
        total += _resource_get(resource_map, key)
    return total


def _first_existing(resource_map, keys):
    resource_map = resource_map or {}
    for key in keys:
        if key in resource_map:
            return key, _resource_get(resource_map, key)
    return "", 0


def _health_level(percent):
    if percent >= 90:
        return "red"
    if percent >= 70:
        return "yellow"
    return "green"


def _health_text(level):
    return {
        "green": "绿色",
        "yellow": "黄色",
        "red": "红色",
    }.get(level, "未知")


def _add_resource(target, key, value):
    parsed = value if isinstance(value, (int, float)) else _parse_resource(key, value)
    if parsed <= 0:
        return
    target[key] = target.get(key, 0) + parsed


def _merge_resource_totals(primary, fallback):
    """
    primary 通常来自 PaaS resourceSummary。
    fallback 通常来自 K8S Node / Pod 资源反推。
    规则：primary 有值优先；primary 没有或为 0 时，用 fallback 补齐。
    """
    merged = dict(primary or {})
    fallback = fallback or {}

    for key, value in fallback.items():
        if _resource_get(merged, key) <= 0:
            merged[key] = value

    return merged

def _merge_cluster_resource_totals(primary, fallback, allocated=False):
    """
    集群汇总合并规则。

    对 GPU 相关字段：
    - allocatable：优先使用节点聚合值，因为节点 label 能识别 vGPU 节点底层物理卡。
    - allocated：取 PaaS 与 Pod 聚合中的较大值，避免漏算。

    对 CPU / 内存：
    - 保持原逻辑，primary 有值优先。
    """
    merged = dict(primary or {})
    fallback = fallback or {}

    gpu_related_keys = set(PHYSICAL_GPU_KEYS + VGPU_KEYS + GPU_MEMORY_KEYS + GPU_CORE_KEYS)

    for key, value in fallback.items():
        fallback_value = _resource_get(fallback, key)
        current_value = _resource_get(merged, key)

        if key in gpu_related_keys:
            if allocated:
                if max(current_value, fallback_value) > 0:
                    merged[key] = max(current_value, fallback_value)
            else:
                if fallback_value > 0:
                    merged[key] = fallback_value
                elif current_value <= 0:
                    merged[key] = value
        else:
            if current_value <= 0:
                merged[key] = value

    return merged

def _get_resource_summary_from_cluster(cluster):
    candidates = [
        _safe_get(cluster, "status", "resourceSummary"),
        _safe_get(cluster, "data", "status", "resourceSummary"),
        _safe_get(cluster, "content", "status", "resourceSummary"),
        _safe_get(cluster, "response", "status", "resourceSummary"),
    ]

    for item in candidates:
        if isinstance(item, dict):
            return item.get("allocatable") or {}, item.get("allocated") or {}

    return {}, {}


def _get_cluster_resource_summary():
    # 读取 PaaS 集群资源汇总，相当于“全局资源池”的粗粒度总账。
    client, err = _paas_client()
    if err:
        return None, err

    status, result = client.request_with_status("GET", f"/clusters/{Config.DCE_CLUSTER}")
    if not 200 <= status < 300:
        return None, _error("Failed to query cluster resource summary", status, result)

    allocatable, allocated = _get_resource_summary_from_cluster(result)

    return {
        "client": client,
        "cluster": result,
        "allocatable": allocatable,
        "allocated": allocated,
    }, None


def _list_nodes_from_paas(client):
    status, result = client.request_with_status("GET", f"/clusters/{Config.DCE_CLUSTER}/nodes")
    if not 200 <= status < 300:
        return None, _error("Failed to query PaaS node list", status, result)

    return _extract_items(result), None


def _list_nodes_from_k8s():
    client, err = _k8s_client()
    if err:
        return None, err

    status, result = client._request("GET", "/api/v1/nodes")
    if not 200 <= status < 300:
        return None, _error("Failed to query Kubernetes node list", status, result)

    return _extract_items(result), None


def _list_nodes(client):
    # 节点列表优先走 PaaS；如果 PaaS 节点接口没有返回可用 items，再降级走 Kubernetes 原生节点接口。
    paas_nodes, paas_error = _list_nodes_from_paas(client)
    if paas_nodes:
        return paas_nodes, None

    k8s_nodes, k8s_error = _list_nodes_from_k8s()
    if k8s_nodes is not None:
        return k8s_nodes, None

    return [], {
        "paas_error": paas_error,
        "k8s_error": k8s_error,
    }


def _list_namespace_pods(namespace):
    """
    资源统计要看全局 Pod，而不是只看 DCE_NAMESPACE。

    原因：
    1. 青海环境 GPU 工作负载分布在 algorithm / default / cigaretee / yolo / test1 等多个 namespace。
    2. 如果只查 algorithm，会把 qhvgpu1 的 GPU 使用量算成 1/4，也就是 25%。
    3. 真实资源分配口径应该基于全 namespace Running Pod 聚合。

    如果 service account 没有 list cluster pods 权限，则降级为当前 namespace。
    """
    client, err = _k8s_client()
    if err:
        return [], err

    status, result = client.list_cluster_pods()
    if 200 <= status < 300:
        return _extract_items(result), None

    fallback_status, fallback_result = client.list_pods(namespace)
    if not 200 <= fallback_status < 300:
        return [], _error("Failed to query pod list", fallback_status, {
            "cluster_pods_error": result,
            "namespace_pods_error": fallback_result,
        })

    return _extract_items(fallback_result), {
        "warning": "No permission to list cluster pods. Fallback to namespace pods.",
        "cluster_pods_error": result,
    }


def _node_name(node):
    return _safe_get(node, "metadata", "name", default="") or node.get("name") or ""


def _node_labels(node):
    return _safe_get(node, "metadata", "labels", default={}) or {}


def _node_capacity(node):
    return _safe_get(node, "status", "capacity", default={}) or {}

def _to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _normalize_gpu_model(value):
    if not value:
        return UNKNOWN_GPU_MODEL

    text = str(value).strip()
    text = text.replace("_", " ").replace("-", " ")

    # NVIDIA-A10 -> NVIDIA A10
    text = " ".join(text.split())
    return text


def _node_gpu_mode(node):
    labels = _node_labels(node)

    mode = str(labels.get("gpu.node.kpanda.io/nvidia-gpu-mode") or "").lower()
    vendor = str(labels.get("node.kpanda.io/gpu-vendor") or "").lower()
    vgpu_plugin = str(labels.get("nvidia.com/vgpu.deploy.device-plugin") or "").lower()

    if mode == "vgpu" or "vgpu" in vendor or vgpu_plugin == "true":
        return "vgpu"

    if mode == "gpu" or "nvidia-gpu" in vendor:
        return "gpu"

    allocatable = _node_base_allocatable(node)
    if _resource_get(allocatable, "nvidia.com/vgpu") > 0:
        return "vgpu"

    if _resource_get(allocatable, "nvidia.com/gpu") > 0:
        return "gpu"

    return "unknown"


def _node_gpu_vendor(node):
    labels = _node_labels(node)
    return labels.get("node.kpanda.io/gpu-vendor") or ""


def _node_gpu_product(node):
    labels = _node_labels(node)

    value = (
        labels.get("nvidia.com/gpu.product")
        or labels.get("gpu.nvidia.com/model")
        or labels.get("gpu.product")
        or labels.get("accelerator")
        or ""
    )

    if value:
        return _normalize_gpu_model(value)

    return UNKNOWN_GPU_MODEL


def _node_gpu_label_count(node):
    labels = _node_labels(node)
    return _to_int(labels.get("nvidia.com/gpu.count"), 0)


def _node_gpu_memory_mib_per_card(node):
    labels = _node_labels(node)

    # 青海节点 label: nvidia.com/gpu.memory=23028，单位按 MiB 处理。
    label_memory = _to_int(labels.get("nvidia.com/gpu.memory"), 0)
    if label_memory > 0:
        return label_memory

    # 兜底用环境变量，默认 A10 24GiB。
    return int(_gpu_card_memory_gib() * 1024)


def _node_gpu_physical_count(node, allocatable=None):
    allocatable = allocatable or _node_base_allocatable(node)

    label_count = _node_gpu_label_count(node)
    if label_count > 0:
        return label_count

    gpu_count = _resource_get(allocatable, "nvidia.com/gpu")
    if gpu_count > 0:
        return gpu_count

    vgpu_count = _resource_get(allocatable, "nvidia.com/vgpu")
    if vgpu_count > 0:
        return _estimated_card_count(0, vgpu_count)

    return 0


def _node_gpu_core_total(node, physical_count):
    if physical_count <= 0:
        return 0
    return int(physical_count * _gpu_card_compute_units())


def _node_gpu_mem_total_mib(node, physical_count):
    if physical_count <= 0:
        return 0
    return int(physical_count * _node_gpu_memory_mib_per_card(node))


def _node_vgpu_per_gpu(node, physical_count, vgpu_total):
    if physical_count <= 0 or vgpu_total <= 0:
        return 0
    return round(vgpu_total / physical_count, 2)


def _node_base_allocatable(node):
    return (
        _safe_get(node, "status", "resourceSummary", "allocatable")
        or _safe_get(node, "status", "allocatable")
        or _safe_get(node, "status", "capacity")
        or {}
    )


def _enhance_node_allocatable(node, allocatable=None):
    """
    将节点 label 中的 GPU 信息补进 allocatable。

    青海场景：
    qhvgpu1:
      nvidia.com/gpu=4
      nvidia.com/vgpu=0
      nvidia.com/gpu.count=4

    qhvgpu2:
      nvidia.com/gpu=0
      nvidia.com/vgpu=40
      nvidia.com/gpu.count=4

    这里需要把 qhvgpu2 的底层 4 张物理卡也纳入 physical_gpu_total。
    这一步是资源中心展示“显卡张数”的关键：PaaS/K8s 可能只暴露 vGPU，
    但产品页面仍然希望看到底层物理卡容量。
    """
    base = dict(allocatable or _node_base_allocatable(node))

    physical_count = _node_gpu_physical_count(node, base)
    vgpu_total = _resource_get(base, "nvidia.com/vgpu")

    if physical_count > 0:
        # gpu_total 代表底层物理卡数量。vgpu 节点也要计入。
        base["nvidia.com/gpu"] = str(physical_count)

        # 根据节点 label 自动计算显存容量。
        gpu_mem_total_mib = _node_gpu_mem_total_mib(node, physical_count)
        if gpu_mem_total_mib > 0:
            base["nvidia.com/gpumem"] = str(gpu_mem_total_mib)

        # 算力暂时使用标准化容量单位。
        gpu_core_total = _node_gpu_core_total(node, physical_count)
        if gpu_core_total > 0:
            base["nvidia.com/gpucores"] = str(gpu_core_total)

    if vgpu_total > 0:
        base["nvidia.com/vgpu"] = str(vgpu_total)

    return base


def _node_allocatable(node):
    return _enhance_node_allocatable(node, _node_base_allocatable(node))


def _node_allocated_from_paas(node):
    return (
        _safe_get(node, "status", "resourceSummary", "allocated")
        or _safe_get(node, "status", "allocated")
        or {}
    )


def _pod_phase(pod):
    return _safe_get(pod, "status", "phase", default="Unknown")


def _pod_node_name(pod):
    return _safe_get(pod, "spec", "nodeName", default="")


def _pod_resources(pod):
    result = {}

    if _pod_phase(pod) in {"Succeeded", "Failed"}:
        return result

    containers = _safe_get(pod, "spec", "containers", default=[]) or []
    for container in containers:
        resources = container.get("resources") or {}
        merged = dict(resources.get("requests") or {})
        merged.update(resources.get("limits") or {})

        for key, value in merged.items():
            _add_resource(result, key, value)

    return result


def _allocated_by_node_from_pods(pods):
    # 通过全命名空间 Pod 的 requests/limits 反推每个节点的已分配资源。
    # 这是 PaaS allocated 不完整时的兜底口径，也是资源预检和资源中心一致性的基础。
    by_node = {}

    for pod in pods:
        node_name = _pod_node_name(pod)
        if not node_name:
            continue

        pod_resource = _pod_resources(pod)
        if not pod_resource:
            continue

        by_node.setdefault(node_name, {})
        for key, value in pod_resource.items():
            by_node[node_name][key] = by_node[node_name].get(key, 0) + value

    return by_node


def _aggregate_node_resources(raw_nodes, pod_allocated_by_node):
    # 汇总所有节点的 allocatable / allocated。
    # allocatable 侧会结合节点 label 增强 GPU/vGPU 信息；allocated 侧会合并 PaaS 和 Pod 反推结果。
    allocatable_total = {}
    allocated_total = {}
    physical_gpu_total = 0

    for node in raw_nodes:
        node_name = _node_name(node)
        allocatable = _node_allocatable(node)
        allocated = _merge_resource_totals(
            _node_allocated_from_paas(node),
            pod_allocated_by_node.get(node_name, {}),
        )

        for key, value in allocatable.items():
            _add_resource(allocatable_total, key, value)

        for key, value in allocated.items():
            _add_resource(allocated_total, key, value)

        # 物理卡数量统一用 _node_gpu_physical_count，与节点行展示口径一致
        physical_gpu_total += _node_gpu_physical_count(node, allocatable)

    # 用显式累加的物理卡数覆盖 allocatable 中可能不一致的 nvidia.com/gpu
    if physical_gpu_total > 0:
        allocatable_total["nvidia.com/gpu"] = physical_gpu_total

    return allocatable_total, allocated_total


def _gpu_model_node_map():
    """
    可选配置：
    GPU_MODEL_NODE_MAP='{"node-gpu-01":"NVIDIA T4","node-gpu-02":"NVIDIA A100"}'

    用于节点 label 不完整时，人工补齐显卡型号展示。
    """
    raw = os.getenv("GPU_MODEL_NODE_MAP") or ""
    if not raw.strip():
        return {}

    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _extract_gpu_model(node):
    product = _node_gpu_product(node)
    if product != UNKNOWN_GPU_MODEL:
        return product

    labels = _node_labels(node)
    capacity = _node_capacity(node)
    allocatable = _node_allocatable(node)

    candidate_keys = [
        "nvidia.com/gpu.product",
        "gpu.nvidia.com/model",
        "gpu.product",
        "accelerator",
        "hami.io/vgpu-devices-to-allocate",
        "huawei.com/ascend.product",
        "huawei.com/npu.product",
    ]

    for key in candidate_keys:
        value = labels.get(key)
        if value:
            return _normalize_gpu_model(value)

    if _parse_resource(
        "huawei.com/Ascend310P",
        capacity.get("huawei.com/Ascend310P") or allocatable.get("huawei.com/Ascend310P"),
    ):
        return "Ascend 310P"

    if _parse_resource(
        "nvidia.com/vgpu",
        capacity.get("nvidia.com/vgpu") or allocatable.get("nvidia.com/vgpu"),
    ):
        return "NVIDIA vGPU"

    if _parse_resource(
        "nvidia.com/gpu",
        capacity.get("nvidia.com/gpu") or allocatable.get("nvidia.com/gpu"),
    ):
        return "NVIDIA GPU"

    return UNKNOWN_GPU_MODEL

def _node_status(node):
    conditions = _safe_get(node, "status", "conditions", default=[]) or []
    for condition in conditions:
        if condition.get("type") == "Ready":
            return "Ready" if condition.get("status") == "True" else "NotReady"
    return _safe_get(node, "status", "phase", default="Unknown")


def _resource_context(query):
    # resources 模块的核心上下文构建函数。
    # 对外的 summary / nodes / gpus / cards / recommendation 基本都先走这里，
    # 再把同一份底层资源快照转换成不同页面需要的视图。
    snapshot, err = _get_cluster_resource_summary()
    if err:
        return None, err

    client = snapshot["client"]
    namespace = query.get("namespace") or Config.DCE_NAMESPACE
    collected_at = _now()

    raw_nodes, nodes_error = _list_nodes(client)
    pods, pod_error = _list_namespace_pods(namespace)
    pod_allocated_by_node = _allocated_by_node_from_pods(pods)

    node_allocatable_total, node_allocated_total = _aggregate_node_resources(
        raw_nodes,
        pod_allocated_by_node,
    )

    return {
        "client": client,
        "namespace": namespace,
        "cluster": snapshot["cluster"],
        "raw_nodes": raw_nodes,
        "pods": pods,
        "pod_allocated_by_node": pod_allocated_by_node,
        "allocatable": _merge_cluster_resource_totals(
            snapshot["allocatable"],
            node_allocatable_total,
            allocated=False,
        ),
        "allocated": _merge_cluster_resource_totals(
            snapshot["allocated"],
            node_allocated_total,
            allocated=True,
        ),
        "collected_at": collected_at,
        "metric_source": METRIC_SOURCE,
        "diagnostics": {
            "nodes_error": nodes_error,
            "pod_error": pod_error,
            "resource_source": METRIC_SOURCE,
            "usage_metric_ready": False,
            "usage_metric_source": "not_configured",
        },
    }, None


def _resource_summary_cards(allocatable, allocated):
    # 把底层资源 map 转成前端卡片所需字段。
    # 注意：显存/算力如果没有平台原生资源键，会按环境变量估算容量和已分配量。
    physical_gpu_total = _sum_resources(allocatable, PHYSICAL_GPU_KEYS)
    physical_gpu_used = _sum_resources(allocated, PHYSICAL_GPU_KEYS)

    vgpu_total = _sum_resources(allocatable, VGPU_KEYS)
    vgpu_used = _sum_resources(allocated, VGPU_KEYS)

    estimated_card_count = _estimated_card_count(physical_gpu_total, vgpu_total)

    gpu_mem_key, gpu_mem_total_mib = _first_existing(allocatable, GPU_MEMORY_KEYS)
    gpu_mem_used_mib = _resource_get(allocated, gpu_mem_key) if gpu_mem_key else 0

    gpu_core_key, gpu_core_total = _first_existing(allocatable, GPU_CORE_KEYS)
    gpu_core_used = _resource_get(allocated, gpu_core_key) if gpu_core_key else 0

    capacity_estimated = False
    gpu_mem_capacity_estimated = False
    gpu_core_capacity_estimated = False

    ratio = _allocation_ratio(
        physical_gpu_used,
        physical_gpu_total,
        vgpu_used,
        vgpu_total,
    )

    # 没有显存总量时，按环境变量估算总量。
    if gpu_mem_total_mib <= 0 and _capacity_estimation_enabled() and estimated_card_count > 0:
        gpu_mem_total_mib = int(estimated_card_count * _gpu_card_memory_gib() * 1024)
        capacity_estimated = True
        gpu_mem_capacity_estimated = True

    # 有显存总量但没有显存分配量时，按物理卡 / vGPU 分配比例估算已分配显存。
    if gpu_mem_total_mib > 0 and gpu_mem_used_mib <= 0 and ratio > 0:
        gpu_mem_used_mib = int(gpu_mem_total_mib * ratio)
        capacity_estimated = True
        gpu_mem_capacity_estimated = True

    # 没有算力总量时，按物理卡数量估算标准化算力容量。
    if gpu_core_total <= 0 and _capacity_estimation_enabled() and estimated_card_count > 0:
        gpu_core_total = int(estimated_card_count * _gpu_card_compute_units())
        capacity_estimated = True
        gpu_core_capacity_estimated = True

    # 有算力总量但没有算力分配量时，按资源分配比例估算。
    if gpu_core_total > 0 and gpu_core_used <= 0 and ratio > 0:
        gpu_core_used = int(gpu_core_total * ratio)
        capacity_estimated = True
        gpu_core_capacity_estimated = True

    cpu_total_m = _parse_cpu_m(allocatable.get("cpu"))
    cpu_used_m = _resource_get(allocated, "cpu")

    memory_total_bytes = _parse_memory_bytes(allocatable.get("memory"))
    memory_used_bytes = _resource_get(allocated, "memory")

    gpu_core_alloc_percent = _percent(gpu_core_used, gpu_core_total)
    gpu_mem_alloc_percent = _percent(gpu_mem_used_mib, gpu_mem_total_mib)

    return {
        "gpu_total": physical_gpu_total,
        "gpu_used": physical_gpu_used,
        "gpu_available": max(physical_gpu_total - physical_gpu_used, 0),
        "gpu_alloc_percent": _percent(physical_gpu_used, physical_gpu_total),

        "physical_gpu_total": physical_gpu_total,
        "physical_gpu_used": physical_gpu_used,
        "physical_gpu_available": max(physical_gpu_total - physical_gpu_used, 0),
        "physical_gpu_alloc_percent": _percent(physical_gpu_used, physical_gpu_total),

        "vgpu_total": vgpu_total,
        "vgpu_used": vgpu_used,
        "vgpu_available": max(vgpu_total - vgpu_used, 0),
        "vgpu_alloc_percent": _percent(vgpu_used, vgpu_total),

        "accelerator_unit_total": physical_gpu_total + vgpu_total,
        "accelerator_unit_used": physical_gpu_used + vgpu_used,

        "gpu_core_total": gpu_core_total,
        "gpu_core_used": gpu_core_used,
        "gpu_core_alloc_percent": gpu_core_alloc_percent,
        "gpu_core_percent": gpu_core_alloc_percent,
        "gpu_core_usage_percent": None,
        "gpu_core_capacity_estimated": gpu_core_capacity_estimated,

        "gpu_mem_total_gib": _mib_to_gib(gpu_mem_total_mib),
        "gpu_mem_used_gib": _mib_to_gib(gpu_mem_used_mib),
        "gpu_mem_alloc_percent": gpu_mem_alloc_percent,
        "gpu_mem_percent": gpu_mem_alloc_percent,
        "gpu_mem_usage_percent": None,
        "gpu_mem_capacity_estimated": gpu_mem_capacity_estimated,

        "cpu_total_m": cpu_total_m,
        "cpu_used_m": cpu_used_m,
        "cpu_percent": _percent(cpu_used_m, cpu_total_m),

        "memory_total_gib": _bytes_to_gib(memory_total_bytes),
        "memory_used_gib": _bytes_to_gib(memory_used_bytes),
        "memory_percent": _percent(memory_used_bytes, memory_total_bytes),

        "usage_metric_ready": False,
        "usage_metric_source": "not_configured",
        "allocation_metric_source": METRIC_SOURCE,

        "capacity_estimated": capacity_estimated,
        "capacity_estimation_source": (
            "node_label_or_ratio"
            if capacity_estimated
            else "resource_key"
        ),
        "capacity_estimation_config": {
            "enabled": _capacity_estimation_enabled(),
            "gpu_card_memory_gib": _gpu_card_memory_gib(),
            "gpu_card_compute_units": _gpu_card_compute_units(),
            "vgpu_per_gpu": _vgpu_per_gpu(),
        },
    }

def summary(query):
    # 资源总览：首页和资源中心顶部统计使用。
    # 这里会顺手写入 resource_snapshot，供 /trend 后续读取历史趋势。
    context, err = _resource_context(query)
    if err:
        return err

    cards = _resource_summary_cards(context["allocatable"], context["allocated"])
    cards["node_count"] = len(context["raw_nodes"])

    max_percent = max(
        cards.get("gpu_alloc_percent", 0),
        cards.get("vgpu_alloc_percent", 0),
        cards.get("gpu_core_alloc_percent", 0),
        cards.get("gpu_mem_alloc_percent", 0),
    )
    level = _health_level(max_percent)

    result = _ok({
        "cluster": Config.DCE_CLUSTER,
        "namespace": context["namespace"],
        "collected_at": context["collected_at"],
        "metric_source": context["metric_source"],
        "health": {
            "level": level,
            "text": _health_text(level),
            "score": max(0, 100 - max_percent // 2),
            "message": "资源调度健康" if level == "green" else "部分资源接近高负载",
        },
        "cards": cards,
        "raw_resource_keys": {
            "allocatable": sorted(list((context["allocatable"] or {}).keys())),
            "allocated": sorted(list((context["allocated"] or {}).keys())),
        },
        "diagnostics": context["diagnostics"],
    })

    _save_resource_snapshot("summary", result)

    return result


def nodes(query):
    # 节点资源列表：按节点展示 GPU/vGPU/显存/算力/CPU/内存等分配情况。
    # 支持 node_name 查询参数做单节点过滤。
    context, err = _resource_context(query)
    if err:
        return err

    items = []

    for node in context["raw_nodes"]:
        node_name = _node_name(node)
        allocatable = _node_allocatable(node)
        allocated = _merge_resource_totals(
            _node_allocated_from_paas(node),
            context["pod_allocated_by_node"].get(node_name, {}),
        )

        cards = _resource_summary_cards(allocatable, allocated)

        max_percent = max(
            cards.get("gpu_alloc_percent", 0),
            cards.get("vgpu_alloc_percent", 0),
            cards.get("gpu_core_alloc_percent", 0),
            cards.get("gpu_mem_alloc_percent", 0),
        )
        level = _health_level(max_percent)

        item = {
            "node_name": node_name,
            "status": _node_status(node),
            "health_level": level,
            "health_text": _health_text(level),
            "gpu_model": _extract_gpu_model(node),
            "collected_at": context["collected_at"],
            "gpu_mode": _node_gpu_mode(node),
            "gpu_vendor": _node_gpu_vendor(node),
            "gpu_memory_mib_per_card": _node_gpu_memory_mib_per_card(node),
            "gpu_memory_gib_per_card": _mib_to_gib(_node_gpu_memory_mib_per_card(node)),
            "vgpu_per_gpu": _node_vgpu_per_gpu(
                node,
                cards.get("physical_gpu_total", 0),
                cards.get("vgpu_total", 0),
            ),
            "metric_source": context["metric_source"],

            "gpu_total": cards["gpu_total"],
            "gpu_used": cards["gpu_used"],
            "gpu_available": cards["gpu_available"],
            "gpu_percent": cards["gpu_alloc_percent"],
            "gpu_alloc_percent": cards["gpu_alloc_percent"],

            "physical_gpu_total": cards["physical_gpu_total"],
            "physical_gpu_used": cards["physical_gpu_used"],
            "physical_gpu_available": cards["physical_gpu_available"],
            "physical_gpu_alloc_percent": cards["physical_gpu_alloc_percent"],

            "vgpu_total": cards["vgpu_total"],
            "vgpu_used": cards["vgpu_used"],
            "vgpu_available": cards["vgpu_available"],
            "vgpu_percent": cards["vgpu_alloc_percent"],
            "vgpu_alloc_percent": cards["vgpu_alloc_percent"],

            "accelerator_unit_total": cards["accelerator_unit_total"],
            "accelerator_unit_used": cards["accelerator_unit_used"],

            "gpu_core_total": cards["gpu_core_total"],
            "gpu_core_used": cards["gpu_core_used"],
            "gpu_core_percent": cards["gpu_core_alloc_percent"],
            "gpu_core_alloc_percent": cards["gpu_core_alloc_percent"],
            "gpu_core_usage_percent": None,
            "gpu_core_capacity_estimated": cards["gpu_core_capacity_estimated"],

            "gpu_mem_total_gib": cards["gpu_mem_total_gib"],
            "gpu_mem_used_gib": cards["gpu_mem_used_gib"],
            "gpu_mem_percent": cards["gpu_mem_alloc_percent"],
            "gpu_mem_alloc_percent": cards["gpu_mem_alloc_percent"],
            "gpu_mem_usage_percent": None,
            "gpu_mem_capacity_estimated": cards["gpu_mem_capacity_estimated"],

            "cpu_total_m": cards["cpu_total_m"],
            "cpu_used_m": cards["cpu_used_m"],
            "memory_total_gib": cards["memory_total_gib"],
            "memory_used_gib": cards["memory_used_gib"],

            "usage_metric_ready": False,
            "usage_metric_source": "not_configured",

            "capacity_estimated": cards["capacity_estimated"],
            "capacity_estimation_source": cards["capacity_estimation_source"],
            "capacity_estimation_config": cards["capacity_estimation_config"],

            "allocatable": {
                key: allocatable.get(key)
                for key in GPU_RESOURCE_META.keys()
                if key in allocatable
            },
            "allocated": {
                key: allocated.get(key)
                for key in GPU_RESOURCE_META.keys()
                if key in allocated
            },
            "diagnostics": {
                "allocated_source": "paas_node_allocated + pod_resource_fallback",
            },
        }

        if query.get("node_name") and query.get("node_name") != item["node_name"]:
            continue

        items.append(item)

    items.sort(
        key=lambda item: max(
            item.get("vgpu_alloc_percent", 0),
            item.get("gpu_alloc_percent", 0),
            item.get("gpu_mem_alloc_percent", 0),
            item.get("gpu_core_alloc_percent", 0),
        ),
        reverse=True,
    )

    return _ok({
        "namespace": context["namespace"],
        "collected_at": context["collected_at"],
        "metric_source": context["metric_source"],
        "items": items,
        "total": len(items),
        "diagnostics": context["diagnostics"],
    })


def gpus(query):
    # GPU 统计视图：按资源名和显卡型号聚合，供“显卡类别占比”和 Top 节点展示使用。
    # 这里会再次调用 nodes(query) 生成 top_nodes，因此资源页并发请求时会产生重复底层查询。
    context, err = _resource_context(query)
    if err:
        return err

    resources = []

    for key, meta in GPU_RESOURCE_META.items():
        total = _resource_get(context["allocatable"], key)
        used = _resource_get(context["allocated"], key)

        if total <= 0 and used <= 0:
            continue

        percent = _percent(used, total)
        resources.append({
            "resource_name": key,
            "display_name": meta["display_name"],
            "vendor": meta["vendor"],
            "kind": meta["kind"],
            "unit": meta["unit"],
            "total": total,
            "used": used,
            "available": max(total - used, 0),
            "percent": percent,
            "alloc_percent": percent,
            "usage_percent": None,
            "usage_metric_ready": False,
        })

    model_map = {}
    unknown_nodes = []

    for node in context["raw_nodes"]:
        model = _extract_gpu_model(node)
        allocatable = _node_allocatable(node)

        count = _sum_resources(allocatable, PHYSICAL_GPU_KEYS)

        # 如果节点没有返回物理卡数量，但返回了 vGPU 数量，则按 VGPU_PER_GPU 估算物理卡数量。
        if count <= 0:
            count = _estimated_card_count(
                0,
                _resource_get(allocatable, "nvidia.com/vgpu"),
            )

        if count <= 0:
            continue

        model_map[model] = model_map.get(model, 0) + count

        if model == UNKNOWN_GPU_MODEL:
            unknown_nodes.append(_node_name(node))

    category_items = [
        {"model": model, "count": count}
        for model, count in model_map.items()
    ]
    category_items.sort(key=lambda item: item["count"], reverse=True)

    top_nodes_result = nodes(query)
    top_nodes = top_nodes_result.get("items", [])[:5] if top_nodes_result.get("is_success") else []

    return _ok({
        "collected_at": context["collected_at"],
        "metric_source": context["metric_source"],
        "resources": resources,
        "category_items": category_items,
        "top_nodes": top_nodes,
        "unknown_model_nodes": unknown_nodes,
        "model_map_configured": bool(_gpu_model_node_map()),
        "diagnostics": context["diagnostics"],
    })


def cards(query):
    # 显卡卡片视图：根据节点资源推导“每张卡”的展示行。
    # 当前没有真实 GPU UUID，因此 card_id 是 node_name + 序号；真实卡级指标需要后续接 exporter。
    node_result = nodes(query)
    if not node_result.get("is_success"):
        return node_result

    card_items = []
    node_items = node_result.get("items", []) or []

    for node in node_items:
        node_name = node.get("node_name") or "unknown-node"

        physical_gpu_total = int(node.get("physical_gpu_total") or node.get("gpu_total") or 0)
        physical_gpu_used = int(node.get("physical_gpu_used") or node.get("gpu_used") or 0)

        vgpu_total = int(node.get("vgpu_total") or 0)
        vgpu_used = int(node.get("vgpu_used") or 0)

        gpu_core_total = float(node.get("gpu_core_total") or 0)
        gpu_core_used = float(node.get("gpu_core_used") or 0)

        gpu_mem_total_gib = float(node.get("gpu_mem_total_gib") or 0)
        gpu_mem_used_gib = float(node.get("gpu_mem_used_gib") or 0)

        gpu_mode = node.get("gpu_mode") or "unknown"
        vgpu_per_gpu = node.get("vgpu_per_gpu") or _vgpu_per_gpu()

        has_gpu_like_resource = (
            physical_gpu_total > 0
            or vgpu_total > 0
            or gpu_core_total > 0
            or gpu_mem_total_gib > 0
        )

        if not has_gpu_like_resource:
            continue

        card_count = physical_gpu_total or _estimated_card_count(0, vgpu_total)
        if card_count <= 0:
            card_count = 1

        if gpu_mode == "vgpu":
            data_precision = "vgpu_node_label"
            mapping_rule = f"vGPU node label: 1 GPU ≈ {vgpu_per_gpu} vGPU"
            usage_mode = "vGPU 后台调度"
        elif gpu_mode == "gpu":
            data_precision = "physical_gpu_node_label"
            mapping_rule = "physical GPU node label"
            usage_mode = "物理 GPU 调度"
        else:
            data_precision = "node_resource_snapshot"
            mapping_rule = "node resource snapshot"
            usage_mode = "GPU 资源调度"

        per_vgpu_total = _split_value(vgpu_total, card_count)
        per_vgpu_used = _split_value(vgpu_used, card_count)

        per_core_total = _split_value(gpu_core_total, card_count)
        per_core_used = _split_value(gpu_core_used, card_count)

        per_mem_total = _split_value(gpu_mem_total_gib, card_count)
        per_mem_used = _split_value(gpu_mem_used_gib, card_count)

        for index in range(card_count):
            if gpu_mode == "vgpu":
                physical_card_allocated = 0
            else:
                physical_card_allocated = 1 if index < physical_gpu_used else 0

            card_status = "空闲"
            if node.get("health_level") == "red":
                card_status = "高负载"
            elif (
                physical_card_allocated > 0
                or per_vgpu_used > 0
                or per_core_used > 0
                or per_mem_used > 0
            ):
                card_status = "运行中"

            card_items.append({
                "card_id": f"{node_name}-gpu-{index + 1:02d}",
                "card_status": card_status,
                "usage_mode": usage_mode,
                "node_name": node_name,
                "gpu_model": node.get("gpu_model") or UNKNOWN_GPU_MODEL,
                "gpu_mode": gpu_mode,

                "physical_gpu": {
                    "allocated": physical_card_allocated,
                    "total": 1,
                    "percent": 100 if physical_card_allocated else 0,
                },
                "vgpu": {
                    "allocated": per_vgpu_used,
                    "total": per_vgpu_total,
                    "percent": _percent(per_vgpu_used, per_vgpu_total),
                    "per_gpu": vgpu_per_gpu if gpu_mode == "vgpu" else 0,
                },
                "gpu_core": {
                    "allocated": per_core_used,
                    "total": per_core_total,
                    "percent": _percent(per_core_used, per_core_total),
                    "usage_percent": None,
                    "capacity_estimated": node.get("gpu_core_capacity_estimated", False),
                },
                "gpu_memory": {
                    "allocated_gib": per_mem_used,
                    "total_gib": per_mem_total,
                    "percent": _percent(per_mem_used, per_mem_total),
                    "usage_percent": None,
                    "capacity_estimated": node.get("gpu_mem_capacity_estimated", False),
                },

                "data_precision": data_precision,
                "is_real_physical_card": False,
                "metric_source": node.get("metric_source") or METRIC_SOURCE,
                "mapping_rule": mapping_rule,
                "usage_metric_ready": False,
                "usage_metric_source": "not_configured",

                "capacity_estimated": node.get("capacity_estimated", False),
                "capacity_estimation_source": node.get("capacity_estimation_source"),
            })

    return _ok({
        "items": card_items,
        "total": len(card_items),
        "metric_source": METRIC_SOURCE,
        "mapping_rule": "Cards are inferred from node labels and Kubernetes resource snapshots.",
        "note": "Real GPU UUID and runtime usage require device metrics integration.",
    })

def trend(query):
    # 趋势视图：优先从 MySQL resource_snapshot 读历史；样本不足时用当前 summary 生成兜底曲线。
    # 因此这里的趋势适合 MVP 展示，不等价于 Prometheus 这类真实时序监控。
    range_value = query.get("range") or "1h"
    start_time = _trend_start_time(range_value)

    snapshots = _load_resource_snapshots("summary", start_time)
    snapshot_items = _trend_items_from_snapshots(snapshots, range_value)

    if len(snapshot_items) >= 2:
        return _ok({
            "range": range_value,
            "items": snapshot_items,
            "data_source": "resource_snapshot",
            "metric_source": METRIC_SOURCE,
            "usage_metric_ready": any(item.get("usage_metric_ready") for item in snapshot_items),
            "need_history_collector": False,
            "snapshot_count": len(snapshot_items),
            "note": "Trend data is loaded from resource_snapshot history.",
        })

    summary_result = summary(query)
    if not summary_result.get("is_success"):
        return summary_result

    cards_data = summary_result.get("cards", {})
    now = datetime.now().replace(second=0, microsecond=0)

    items = []
    for i in range(5, -1, -1):
        t = now - timedelta(minutes=10 * i)
        items.append({
            "time": t.strftime("%H:%M"),

            "gpu_alloc_percent": cards_data.get("gpu_alloc_percent", 0),
            "vgpu_alloc_percent": cards_data.get("vgpu_alloc_percent", 0),

            "gpu_mem_percent": cards_data.get("gpu_mem_alloc_percent", 0),
            "gpu_mem_alloc_percent": cards_data.get("gpu_mem_alloc_percent", 0),
            "gpu_mem_usage_percent": None,

            "gpu_core_percent": cards_data.get("gpu_core_alloc_percent", 0),
            "gpu_core_alloc_percent": cards_data.get("gpu_core_alloc_percent", 0),
            "gpu_core_usage_percent": None,

            "usage_metric_ready": False,
        })

    return _ok({
        "range": range_value,
        "items": items,
        "data_source": "current_resource_snapshot",
        "metric_source": METRIC_SOURCE,
        "usage_metric_ready": False,
        "need_history_collector": True,
        "snapshot_count": len(snapshot_items),
        "note": "Historical samples are not enough. Current response is generated from the latest resource snapshot.",
    })


def _node_score(item):
    return max(
        item.get("vgpu_alloc_percent", 0),
        item.get("gpu_alloc_percent", 0),
        item.get("gpu_mem_alloc_percent", 0),
        item.get("gpu_core_alloc_percent", 0),
    )


def recommendation(query):
    # 推荐策略：根据整体资源分配率和节点排序，给出推荐节点、避让节点和风险提示。
    # 这里只是轻量启发式规则，不会真正影响 Kubernetes 调度。
    summary_result = summary(query)
    if not summary_result.get("is_success"):
        return summary_result

    node_result = nodes(query)
    node_items = node_result.get("items", []) if node_result.get("is_success") else []

    cards_data = summary_result.get("cards", {})
    max_percent = max(
        cards_data.get("gpu_alloc_percent", 0),
        cards_data.get("vgpu_alloc_percent", 0),
        cards_data.get("gpu_mem_alloc_percent", 0),
        cards_data.get("gpu_core_alloc_percent", 0),
    )

    recommended_node = None
    avoid_nodes = []
    reason = []

    if node_items:
        sorted_nodes = sorted(node_items, key=_node_score)
        recommended_node = sorted_nodes[0].get("node_name")
        reason.append(f"{recommended_node} 当前资源分配率相对较低")

        avoid_nodes = [
            item.get("node_name")
            for item in sorted_nodes
            if _node_score(item) >= 80
        ]

        if avoid_nodes:
            reason.append("部分节点已进入中高负载区间，建议暂缓新增普通任务")

    if max_percent >= 90:
        priority = "高"
        mode = "高优先级排队"
        risk = "高，建议暂停低优先级创建"
        suggestion = "资源接近满载，建议优先保障生产任务，暂停非必要实例创建。"
    elif max_percent >= 70:
        priority = "中"
        mode = "优先调度低负载节点"
        risk = "中，需观察峰值"
        suggestion = "资源进入中高负载区间，建议优先选择空闲节点并控制弹性任务数量。"
    else:
        priority = "低"
        mode = "自动推荐"
        risk = "低，可继续创建实例"
        suggestion = "当前资源余量较充足，可以继续创建实例或开启弹性任务。"

    if recommended_node:
        suggestion = f"建议优先调度到 {recommended_node}。" + suggestion

    return _ok({
        "recommend_mode": mode,
        "recommended_node": recommended_node,
        "avoid_nodes": avoid_nodes,
        "expected_occupation": {
            "gpu_available": cards_data.get("gpu_available", 0),
            "vgpu_available": cards_data.get("vgpu_available", 0),
            "gpu_memory_available_gib": round(
                cards_data.get("gpu_mem_total_gib", 0) - cards_data.get("gpu_mem_used_gib", 0),
                2,
            ),
        },
        "strategy": "60% 主任务 + 30% 弹性 + 10% 预留",
        "risk_level": risk,
        "priority": priority,
        "reason": reason,
        "suggestion": suggestion,
        "metric_source": METRIC_SOURCE,
        "usage_metric_ready": False,
    })


def quotas(query):
    # 命名空间 ResourceQuota 查询。无权限或没有配置 quota 时降级返回空列表，不阻塞资源中心页面。
    client, err = _k8s_client()
    if err:
        return err

    namespace = query.get("namespace") or Config.DCE_NAMESPACE
    status, result = client._request("GET", f"/api/v1/namespaces/{namespace}/resourcequotas")

    if status == 403:
        return _ok({
            "namespace": namespace,
            "items": [],
            "total": 0,
            "warning": "Current service account has no permission to list ResourceQuota. Quota display is skipped.",
            "permission_required": {
                "api_group": "",
                "resource": "resourcequotas",
                "verb": "list",
                "namespace": namespace,
            },
            "response": result,
        })

    if status == 404:
        return _ok({
            "namespace": namespace,
            "items": [],
            "total": 0,
            "warning": "ResourceQuota is not configured in the namespace.",
            "response": result,
        })

    if not 200 <= status < 300:
        return _error("Failed to query ResourceQuota", status, result)

    items = []
    for item in result.get("items", []) or []:
        metadata = item.get("metadata") or {}
        status_obj = item.get("status") or {}

        items.append({
            "name": metadata.get("name"),
            "namespace": metadata.get("namespace"),
            "hard": status_obj.get("hard") or {},
            "used": status_obj.get("used") or {},
        })

    return _ok({
        "namespace": namespace,
        "items": items,
        "total": len(items),
    })
