import json
import os
import time
from datetime import datetime, timedelta

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

GPU_COUNT_KEYS = ["nvidia.com/vgpu", "nvidia.com/gpu", "huawei.com/Ascend310P"]
GPU_MEMORY_KEYS = ["nvidia.com/gpumem"]
GPU_CORE_KEYS = ["nvidia.com/gpucores"]

UNKNOWN_GPU_MODEL = "Unknown"
METRIC_SOURCE = "paas_cluster_resourceSummary + k8s_node_fallback + pod_resource_fallback"


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
    if not Config.DCE_API_BASE:
        return None, _error("DCE_API_BASE is not configured", 500)
    if not Config.DCE_TOKEN:
        return None, _error("DCE_TOKEN is not configured", 500)
    return PaasClient(Config.DCE_API_BASE, Config.DCE_TOKEN), None


def _k8s_client():
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
    client, err = _k8s_client()
    if err:
        return [], err

    status, result = client.list_pods(namespace)
    if not 200 <= status < 300:
        return [], _error("Failed to query pod list", status, result)

    return _extract_items(result), None


def _node_name(node):
    return _safe_get(node, "metadata", "name", default="") or node.get("name") or ""


def _node_labels(node):
    return _safe_get(node, "metadata", "labels", default={}) or {}


def _node_capacity(node):
    return _safe_get(node, "status", "capacity", default={}) or {}


def _node_allocatable(node):
    return (
        _safe_get(node, "status", "resourceSummary", "allocatable")
        or _safe_get(node, "status", "allocatable")
        or _safe_get(node, "status", "capacity")
        or {}
    )


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
    allocatable_total = {}
    allocated_total = {}

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
    node_name = _node_name(node)
    node_map = _gpu_model_node_map()
    if node_name in node_map:
        return str(node_map[node_name])

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
            return str(value).replace("_", " ")

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
        "allocatable": _merge_resource_totals(snapshot["allocatable"], node_allocatable_total),
        "allocated": _merge_resource_totals(snapshot["allocated"], node_allocated_total),
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
    gpu_total = _sum_resources(allocatable, GPU_COUNT_KEYS)
    gpu_used = _sum_resources(allocated, GPU_COUNT_KEYS)

    gpu_mem_key, gpu_mem_total_mib = _first_existing(allocatable, GPU_MEMORY_KEYS)
    gpu_mem_used_mib = _resource_get(allocated, gpu_mem_key) if gpu_mem_key else 0

    gpu_core_key, gpu_core_total = _first_existing(allocatable, GPU_CORE_KEYS)
    gpu_core_used = _resource_get(allocated, gpu_core_key) if gpu_core_key else 0

    vgpu_total = _resource_get(allocatable, "nvidia.com/vgpu")
    vgpu_used = _resource_get(allocated, "nvidia.com/vgpu")

    cpu_total_m = _parse_cpu_m(allocatable.get("cpu"))
    cpu_used_m = _resource_get(allocated, "cpu")

    memory_total_bytes = _parse_memory_bytes(allocatable.get("memory"))
    memory_used_bytes = _resource_get(allocated, "memory")

    gpu_core_alloc_percent = _percent(gpu_core_used, gpu_core_total)
    gpu_mem_alloc_percent = _percent(gpu_mem_used_mib, gpu_mem_total_mib)

    return {
        "gpu_total": gpu_total,
        "gpu_used": gpu_used,
        "gpu_available": max(gpu_total - gpu_used, 0),
        "gpu_alloc_percent": _percent(gpu_used, gpu_total),

        "vgpu_total": vgpu_total,
        "vgpu_used": vgpu_used,
        "vgpu_available": max(vgpu_total - vgpu_used, 0),
        "vgpu_alloc_percent": _percent(vgpu_used, vgpu_total),

        "gpu_core_total": gpu_core_total,
        "gpu_core_used": gpu_core_used,
        "gpu_core_alloc_percent": gpu_core_alloc_percent,
        "gpu_core_percent": gpu_core_alloc_percent,
        "gpu_core_usage_percent": None,

        "gpu_mem_total_gib": _mib_to_gib(gpu_mem_total_mib),
        "gpu_mem_used_gib": _mib_to_gib(gpu_mem_used_mib),
        "gpu_mem_alloc_percent": gpu_mem_alloc_percent,
        "gpu_mem_percent": gpu_mem_alloc_percent,
        "gpu_mem_usage_percent": None,

        "cpu_total_m": cpu_total_m,
        "cpu_used_m": cpu_used_m,
        "cpu_percent": _percent(cpu_used_m, cpu_total_m),

        "memory_total_gib": _bytes_to_gib(memory_total_bytes),
        "memory_used_gib": _bytes_to_gib(memory_used_bytes),
        "memory_percent": _percent(memory_used_bytes, memory_total_bytes),

        "usage_metric_ready": False,
        "usage_metric_source": "not_configured",
        "allocation_metric_source": METRIC_SOURCE,
    }


def summary(query):
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
            "metric_source": context["metric_source"],

            "gpu_total": cards["gpu_total"],
            "gpu_used": cards["gpu_used"],
            "gpu_available": cards["gpu_available"],
            "gpu_percent": cards["gpu_alloc_percent"],
            "gpu_alloc_percent": cards["gpu_alloc_percent"],

            "vgpu_total": cards["vgpu_total"],
            "vgpu_used": cards["vgpu_used"],
            "vgpu_available": cards["vgpu_available"],
            "vgpu_percent": cards["vgpu_alloc_percent"],
            "vgpu_alloc_percent": cards["vgpu_alloc_percent"],

            "gpu_core_total": cards["gpu_core_total"],
            "gpu_core_used": cards["gpu_core_used"],
            "gpu_core_percent": cards["gpu_core_alloc_percent"],
            "gpu_core_alloc_percent": cards["gpu_core_alloc_percent"],
            "gpu_core_usage_percent": None,

            "gpu_mem_total_gib": cards["gpu_mem_total_gib"],
            "gpu_mem_used_gib": cards["gpu_mem_used_gib"],
            "gpu_mem_percent": cards["gpu_mem_alloc_percent"],
            "gpu_mem_alloc_percent": cards["gpu_mem_alloc_percent"],
            "gpu_mem_usage_percent": None,

            "cpu_total_m": cards["cpu_total_m"],
            "cpu_used_m": cards["cpu_used_m"],
            "memory_total_gib": cards["memory_total_gib"],
            "memory_used_gib": cards["memory_used_gib"],

            "usage_metric_ready": False,
            "usage_metric_source": "not_configured",

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

        count = (
            _resource_get(allocatable, "nvidia.com/gpu")
            or _resource_get(allocatable, "huawei.com/Ascend310P")
            or _resource_get(allocatable, "nvidia.com/vgpu")
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
    node_result = nodes(query)
    if not node_result.get("is_success"):
        return node_result

    card_items = []
    node_items = node_result.get("items", []) or []

    for node in node_items:
        node_name = node.get("node_name") or "unknown-node"

        physical_gpu_total = int(node.get("gpu_total") or 0)
        vgpu_total = int(node.get("vgpu_total") or 0)
        gpu_core_total = int(node.get("gpu_core_total") or 0)
        gpu_mem_total_gib = float(node.get("gpu_mem_total_gib") or 0)

        has_gpu_like_resource = (
            physical_gpu_total > 0
            or vgpu_total > 0
            or gpu_core_total > 0
            or gpu_mem_total_gib > 0
        )

        if not has_gpu_like_resource:
            continue

        if physical_gpu_total > 0:
            card_count = physical_gpu_total
            data_precision = "physical_gpu_estimated"
            mapping_rule = "physical GPU resource count"
        elif vgpu_total > 0:
            card_count = max((vgpu_total + 1) // 2, 1)
            data_precision = "vgpu_estimated"
            mapping_rule = "1 GPU = 2 vGPU"
        else:
            card_count = 1
            data_precision = "node_resource_snapshot"
            mapping_rule = "node resource snapshot"

        for index in range(card_count):
            card_status = "空闲"
            if node.get("health_level") == "red":
                card_status = "高负载"
            elif (
                int(node.get("gpu_used") or 0) > 0
                or int(node.get("vgpu_used") or 0) > 0
                or int(node.get("gpu_core_used") or 0) > 0
                or float(node.get("gpu_mem_used_gib") or 0) > 0
            ):
                card_status = "运行中"

            card_items.append({
                "card_id": f"{node_name}-gpu-{index + 1:02d}" if card_count > 1 else f"{node_name}-resource",
                "card_status": card_status,
                "usage_mode": "vGPU 后台调度" if vgpu_total > 0 else "物理 GPU 调度",
                "node_name": node_name,
                "gpu_model": node.get("gpu_model") or UNKNOWN_GPU_MODEL,

                "vgpu": {
                    "allocated": node.get("vgpu_used", 0),
                    "total": node.get("vgpu_total", 0),
                    "percent": node.get("vgpu_alloc_percent", 0),
                },
                "gpu_core": {
                    "allocated": node.get("gpu_core_used", 0),
                    "total": node.get("gpu_core_total", 0),
                    "percent": node.get("gpu_core_alloc_percent", 0),
                    "usage_percent": None,
                },
                "gpu_memory": {
                    "allocated_gib": node.get("gpu_mem_used_gib", 0),
                    "total_gib": node.get("gpu_mem_total_gib", 0),
                    "percent": node.get("gpu_mem_alloc_percent", 0),
                    "usage_percent": None,
                },

                "data_precision": data_precision,
                "is_real_physical_card": False,
                "metric_source": node.get("metric_source") or METRIC_SOURCE,
                "mapping_rule": mapping_rule,
                "usage_metric_ready": False,
                "usage_metric_source": "not_configured",
            })

    if not card_items:
        summary_result = summary(query)
        if summary_result.get("is_success"):
            cards_data = summary_result.get("cards", {}) or {}

            has_cluster_resource = (
                int(cards_data.get("gpu_total") or 0) > 0
                or int(cards_data.get("vgpu_total") or 0) > 0
                or int(cards_data.get("gpu_core_total") or 0) > 0
                or float(cards_data.get("gpu_mem_total_gib") or 0) > 0
            )

            if has_cluster_resource:
                card_items.append({
                    "card_id": "cluster-resource-summary",
                    "card_status": "运行中",
                    "usage_mode": "集群资源汇总",
                    "node_name": "cluster",
                    "gpu_model": "Cluster Resource",
                    "vgpu": {
                        "allocated": cards_data.get("vgpu_used", 0),
                        "total": cards_data.get("vgpu_total", 0),
                        "percent": cards_data.get("vgpu_alloc_percent", 0),
                    },
                    "gpu_core": {
                        "allocated": cards_data.get("gpu_core_used", 0),
                        "total": cards_data.get("gpu_core_total", 0),
                        "percent": cards_data.get("gpu_core_alloc_percent", 0),
                        "usage_percent": None,
                    },
                    "gpu_memory": {
                        "allocated_gib": cards_data.get("gpu_mem_used_gib", 0),
                        "total_gib": cards_data.get("gpu_mem_total_gib", 0),
                        "percent": cards_data.get("gpu_mem_alloc_percent", 0),
                        "usage_percent": None,
                    },
                    "data_precision": "cluster_resource_snapshot",
                    "is_real_physical_card": False,
                    "metric_source": summary_result.get("metric_source") or METRIC_SOURCE,
                    "mapping_rule": "cluster resource snapshot",
                    "usage_metric_ready": False,
                    "usage_metric_source": "not_configured",
                })

    return _ok({
        "items": card_items,
        "total": len(card_items),
        "mapping_rule": "1 GPU = 2 vGPU when only vGPU resources are available",
        "metric_source": METRIC_SOURCE,
        "note": "Cards are inferred from node or cluster resources. Real device UUID and runtime usage require device metrics integration.",
    })


def trend(query):
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
