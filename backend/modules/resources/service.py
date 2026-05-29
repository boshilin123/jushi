import time
from datetime import datetime, timedelta


try:
    from backend.config import Config
    from backend.services.paas_client import PaasClient
    from backend.services.k8s_client import K8sClient
except ModuleNotFoundError:
    from config import Config
    from services.paas_client import PaasClient
    from services.k8s_client import K8sClient


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
        "display_name": "GPU 算力",
        "vendor": "NVIDIA",
        "kind": "gpu_core",
        "unit": "core",
    },
    "nvidia.com/gpumem": {
        "display_name": "GPU 显存",
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
        return None, _error("DCE_API_BASE 未配置", 500)
    if not Config.DCE_TOKEN:
        return None, _error("DCE_TOKEN 未配置", 500)
    return PaasClient(Config.DCE_API_BASE, Config.DCE_TOKEN), None


def _k8s_client():
    client = K8sClient.from_config(Config)
    if not client.api_base:
        return None, _error("K8S_API_BASE 未配置", 500)
    if not client.token:
        return None, _error("K8S_TOKEN 未配置", 500)
    return client, None


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


def _merge_resource_totals(primary, fallback):
    """
    primary 通常来自 PaaS cluster resourceSummary。
    fallback 通常来自 K8S Node / Pod 反推。
    规则：primary 有值优先；primary 没有或为 0 时，用 fallback 补齐。
    """
    merged = dict(primary or {})
    fallback = fallback or {}

    for key, value in fallback.items():
        current = _resource_get(merged, key)
        if current <= 0:
            merged[key] = value

    return merged


def _add_resource(target, key, value):
    parsed = value if isinstance(value, (int, float)) else _parse_resource(key, value)
    if parsed <= 0:
        return
    target[key] = target.get(key, 0) + parsed


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
        return None, _error("集群资源汇总查询失败", status, result)

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
        return None, _error("PaaS 节点列表查询失败", status, result)

    items = _extract_items(result)
    return items, None


def _list_nodes_from_k8s():
    client, err = _k8s_client()
    if err:
        return None, err

    status, result = client._request("GET", "/api/v1/nodes")
    if not 200 <= status < 300:
        return None, _error("K8S 节点列表查询失败", status, result)

    return _extract_items(result), None


def _list_nodes(client):
    paas_nodes, paas_error = _list_nodes_from_paas(client)
    if paas_nodes is not None and len(paas_nodes) > 0:
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
        return [], _error("Pod 列表查询失败", status, result)

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
        limits = resources.get("limits") or {}
        requests = resources.get("requests") or {}

        merged = dict(requests)
        merged.update(limits)

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
        paas_allocated = _node_allocated_from_paas(node)
        pod_allocated = pod_allocated_by_node.get(node_name, {})
        allocated = _merge_resource_totals(paas_allocated, pod_allocated)

        for key, value in allocatable.items():
            _add_resource(allocatable_total, key, value)

        for key, value in allocated.items():
            _add_resource(allocated_total, key, value)

    return allocatable_total, allocated_total


def _extract_gpu_model(node):
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

    if _parse_resource("huawei.com/Ascend310P", capacity.get("huawei.com/Ascend310P") or allocatable.get("huawei.com/Ascend310P")):
        return "Ascend 310P"
    if _parse_resource("nvidia.com/vgpu", capacity.get("nvidia.com/vgpu") or allocatable.get("nvidia.com/vgpu")):
        return "NVIDIA vGPU"
    if _parse_resource("nvidia.com/gpu", capacity.get("nvidia.com/gpu") or allocatable.get("nvidia.com/gpu")):
        return "NVIDIA GPU"

    return "Unknown"


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

    raw_nodes, nodes_error = _list_nodes(client)
    pods, pod_error = _list_namespace_pods(namespace)
    pod_allocated_by_node = _allocated_by_node_from_pods(pods)

    node_allocatable_total, node_allocated_total = _aggregate_node_resources(
        raw_nodes,
        pod_allocated_by_node,
    )

    merged_allocatable = _merge_resource_totals(
        snapshot["allocatable"],
        node_allocatable_total,
    )
    merged_allocated = _merge_resource_totals(
        snapshot["allocated"],
        node_allocated_total,
    )

    return {
        "client": client,
        "namespace": namespace,
        "cluster": snapshot["cluster"],
        "raw_nodes": raw_nodes,
        "pods": pods,
        "pod_allocated_by_node": pod_allocated_by_node,
        "allocatable": merged_allocatable,
        "allocated": merged_allocated,
        "diagnostics": {
            "nodes_error": nodes_error,
            "pod_error": pod_error,
            "resource_source": "paas_cluster_resourceSummary + k8s_node_fallback + pod_resource_fallback",
        },
    }, None


def summary(query):
    context, err = _resource_context(query)
    if err:
        return err

    allocatable = context["allocatable"]
    allocated = context["allocated"]

    gpu_total = _sum_resources(allocatable, GPU_COUNT_KEYS)
    gpu_used = _sum_resources(allocated, GPU_COUNT_KEYS)
    gpu_available = max(gpu_total - gpu_used, 0)

    gpu_mem_key, gpu_mem_total_mib = _first_existing(allocatable, GPU_MEMORY_KEYS)
    gpu_mem_used_mib = _resource_get(allocated, gpu_mem_key) if gpu_mem_key else 0

    gpu_core_key, gpu_core_total = _first_existing(allocatable, GPU_CORE_KEYS)
    gpu_core_used = _resource_get(allocated, gpu_core_key) if gpu_core_key else 0

    cpu_total_m = _parse_cpu_m(allocatable.get("cpu"))
    cpu_used_m = _resource_get(allocated, "cpu")

    memory_total_bytes = _parse_memory_bytes(allocatable.get("memory"))
    memory_used_bytes = _resource_get(allocated, "memory")

    gpu_percent = _percent(gpu_used, gpu_total)
    gpu_mem_percent = _percent(gpu_mem_used_mib, gpu_mem_total_mib)
    gpu_core_percent = _percent(gpu_core_used, gpu_core_total)

    max_percent = max(gpu_percent, gpu_mem_percent, gpu_core_percent)
    level = _health_level(max_percent)

    vgpu_total = _resource_get(allocatable, "nvidia.com/vgpu")
    vgpu_used = _resource_get(allocated, "nvidia.com/vgpu")

    return _ok({
        "cluster": Config.DCE_CLUSTER,
        "namespace": context["namespace"],
        "health": {
            "level": level,
            "text": _health_text(level),
            "score": max(0, 100 - max_percent // 2),
            "message": "资源调度健康" if level == "green" else "部分资源接近高负载",
        },
        "cards": {
            "node_count": len(context["raw_nodes"]),

            "gpu_total": gpu_total,
            "gpu_used": gpu_used,
            "gpu_available": gpu_available,
            "gpu_alloc_percent": gpu_percent,

            "vgpu_total": vgpu_total,
            "vgpu_used": vgpu_used,
            "vgpu_available": max(vgpu_total - vgpu_used, 0),
            "vgpu_alloc_percent": _percent(vgpu_used, vgpu_total),

            "gpu_core_total": gpu_core_total,
            "gpu_core_used": gpu_core_used,
            "gpu_core_percent": gpu_core_percent,

            "gpu_mem_total_gib": _mib_to_gib(gpu_mem_total_mib),
            "gpu_mem_used_gib": _mib_to_gib(gpu_mem_used_mib),
            "gpu_mem_percent": gpu_mem_percent,

            "cpu_total_m": cpu_total_m,
            "cpu_used_m": cpu_used_m,
            "cpu_percent": _percent(cpu_used_m, cpu_total_m),

            "memory_total_gib": _bytes_to_gib(memory_total_bytes),
            "memory_used_gib": _bytes_to_gib(memory_used_bytes),
            "memory_percent": _percent(memory_used_bytes, memory_total_bytes),
        },
        "raw_resource_keys": {
            "allocatable": sorted(list((allocatable or {}).keys())),
            "allocated": sorted(list((allocated or {}).keys())),
        },
        "diagnostics": context["diagnostics"],
    })


def nodes(query):
    context, err = _resource_context(query)
    if err:
        return err

    items = []

    for node in context["raw_nodes"]:
        node_name = _node_name(node)
        allocatable = _node_allocatable(node)
        paas_allocated = _node_allocated_from_paas(node)
        pod_allocated = context["pod_allocated_by_node"].get(node_name, {})
        allocated = _merge_resource_totals(paas_allocated, pod_allocated)

        gpu_total = _sum_resources(allocatable, GPU_COUNT_KEYS)
        gpu_used = _sum_resources(allocated, GPU_COUNT_KEYS)

        gpu_mem_key, gpu_mem_total_mib = _first_existing(allocatable, GPU_MEMORY_KEYS)
        gpu_mem_used_mib = _resource_get(allocated, gpu_mem_key) if gpu_mem_key else 0

        gpu_core_key, gpu_core_total = _first_existing(allocatable, GPU_CORE_KEYS)
        gpu_core_used = _resource_get(allocated, gpu_core_key) if gpu_core_key else 0

        gpu_percent = _percent(gpu_used, gpu_total)
        gpu_mem_percent = _percent(gpu_mem_used_mib, gpu_mem_total_mib)
        gpu_core_percent = _percent(gpu_core_used, gpu_core_total)

        max_percent = max(gpu_percent, gpu_mem_percent, gpu_core_percent)
        level = _health_level(max_percent)

        vgpu_total = _resource_get(allocatable, "nvidia.com/vgpu")
        vgpu_used = _resource_get(allocated, "nvidia.com/vgpu")

        item = {
            "node_name": node_name,
            "status": _node_status(node),
            "health_level": level,
            "health_text": _health_text(level),
            "gpu_model": _extract_gpu_model(node),

            "gpu_total": gpu_total,
            "gpu_used": gpu_used,
            "gpu_available": max(gpu_total - gpu_used, 0),
            "gpu_percent": gpu_percent,

            "vgpu_total": vgpu_total,
            "vgpu_used": vgpu_used,
            "vgpu_available": max(vgpu_total - vgpu_used, 0),
            "vgpu_percent": _percent(vgpu_used, vgpu_total),

            "gpu_core_total": gpu_core_total,
            "gpu_core_used": gpu_core_used,
            "gpu_core_percent": gpu_core_percent,

            "gpu_mem_total_gib": _mib_to_gib(gpu_mem_total_mib),
            "gpu_mem_used_gib": _mib_to_gib(gpu_mem_used_mib),
            "gpu_mem_percent": gpu_mem_percent,

            "cpu_total_m": _parse_cpu_m(allocatable.get("cpu")),
            "cpu_used_m": _resource_get(allocated, "cpu"),

            "memory_total_gib": _bytes_to_gib(_parse_memory_bytes(allocatable.get("memory"))),
            "memory_used_gib": _bytes_to_gib(_resource_get(allocated, "memory")),

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
            item.get("vgpu_percent", 0),
            item.get("gpu_percent", 0),
            item.get("gpu_mem_percent", 0),
            item.get("gpu_core_percent", 0),
        ),
        reverse=True,
    )

    return _ok({
        "namespace": context["namespace"],
        "items": items,
        "total": len(items),
        "diagnostics": context["diagnostics"],
    })


def gpus(query):
    context, err = _resource_context(query)
    if err:
        return err

    allocatable = context["allocatable"]
    allocated = context["allocated"]

    resources = []
    for key, meta in GPU_RESOURCE_META.items():
        total = _resource_get(allocatable, key)
        used = _resource_get(allocated, key)

        if total <= 0 and used <= 0:
            continue

        resources.append({
            "resource_name": key,
            "display_name": meta["display_name"],
            "vendor": meta["vendor"],
            "kind": meta["kind"],
            "unit": meta["unit"],
            "total": total,
            "used": used,
            "available": max(total - used, 0),
            "percent": _percent(used, total),
        })

    model_map = {}
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

    category_items = [
        {"model": model, "count": count}
        for model, count in model_map.items()
    ]
    category_items.sort(key=lambda item: item["count"], reverse=True)

    top_nodes_result = nodes(query)
    top_nodes = top_nodes_result.get("items", [])[:5] if top_nodes_result.get("is_success") else []

    return _ok({
        "resources": resources,
        "category_items": category_items,
        "top_nodes": top_nodes,
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
        elif vgpu_total > 0:
            # 当前没有真实物理卡 UUID 时，按 1 GPU = 2 vGPU 估算展示卡片数量。
            card_count = max((vgpu_total + 1) // 2, 1)
            data_precision = "vgpu_estimated"
        else:
            card_count = 1
            data_precision = "node_resource_snapshot"

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
                "gpu_model": node.get("gpu_model") or "Unknown",
                "vgpu": {
                    "allocated": node.get("vgpu_used", 0),
                    "total": node.get("vgpu_total", 0),
                    "percent": node.get("vgpu_percent", 0),
                },
                "gpu_core": {
                    "allocated": node.get("gpu_core_used", 0),
                    "total": node.get("gpu_core_total", 0),
                    "percent": node.get("gpu_core_percent", 0),
                },
                "gpu_memory": {
                    "allocated_gib": node.get("gpu_mem_used_gib", 0),
                    "total_gib": node.get("gpu_mem_total_gib", 0),
                    "percent": node.get("gpu_mem_percent", 0),
                },
                "data_precision": data_precision,
            })

    # 如果节点接口能通，但节点没有 GPU/vGPU 字段，则降级为集群资源卡，避免前端空白。
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
                        "percent": cards_data.get("gpu_core_percent", 0),
                    },
                    "gpu_memory": {
                        "allocated_gib": cards_data.get("gpu_mem_used_gib", 0),
                        "total_gib": cards_data.get("gpu_mem_total_gib", 0),
                        "percent": cards_data.get("gpu_mem_percent", 0),
                    },
                    "data_precision": "cluster_resource_snapshot",
                })

    return _ok({
        "items": card_items,
        "total": len(card_items),
        "note": "当前卡片由节点资源或集群资源推导。接入 DCGM / HAMI / Ascend exporter 后，可精确到真实物理卡 UUID。",
    })


def trend(query):
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
            "gpu_mem_percent": cards_data.get("gpu_mem_percent", 0),
            "gpu_core_percent": cards_data.get("gpu_core_percent", 0),
        })

    return _ok({
        "range": query.get("range") or "1h",
        "items": items,
        "data_source": "current_resource_snapshot",
        "need_history_collector": True,
        "note": "当前未接入历史采集表，趋势接口返回当前资源快照序列。后续接 Prometheus 或 MySQL 采集表后可返回真实趋势。",
    })


def recommendation(query):
    summary_result = summary(query)
    if not summary_result.get("is_success"):
        return summary_result

    cards_data = summary_result.get("cards", {})

    max_percent = max(
        cards_data.get("gpu_alloc_percent", 0),
        cards_data.get("vgpu_alloc_percent", 0),
        cards_data.get("gpu_mem_percent", 0),
        cards_data.get("gpu_core_percent", 0),
    )

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

    return _ok({
        "recommend_mode": mode,
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
        "suggestion": suggestion,
    })


def quotas(query):
    client, err = _k8s_client()
    if err:
        return err

    namespace = query.get("namespace") or Config.DCE_NAMESPACE
    path = f"/api/v1/namespaces/{namespace}/resourcequotas"
    status, result = client._request("GET", path)

    # ResourceQuota 不是首页 / 资源中心主流程必需数据。
    # 当前 serviceaccount 没有 list resourcequotas 权限时，不应该让页面接口失败。
    if status == 403:
        return _ok({
            "namespace": namespace,
            "items": [],
            "total": 0,
            "warning": "当前账号没有 ResourceQuota 查询权限，已跳过配额展示。",
            "permission_required": {
                "api_group": "",
                "resource": "resourcequotas",
                "verb": "list",
                "namespace": namespace,
            },
            "response": result,
        })

    # 有些环境没有配置 ResourceQuota，也按空列表处理。
    if status == 404:
        return _ok({
            "namespace": namespace,
            "items": [],
            "total": 0,
            "warning": "当前命名空间未配置 ResourceQuota。",
            "response": result,
        })

    if not 200 <= status < 300:
        return _error("资源配额查询失败", status, result)

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
