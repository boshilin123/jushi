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

GPU_COUNT_KEYS = [
    "nvidia.com/vgpu",
    "nvidia.com/gpu",
    "huawei.com/Ascend310P",
]

GPU_MEMORY_KEYS = [
    "nvidia.com/gpumem",
]

GPU_CORE_KEYS = [
    "nvidia.com/gpucores",
]


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


def _parse_quantity(value):
    if value is None:
        return 0

    text = str(value).strip()
    if not text:
        return 0

    if text.endswith("m"):
        return int(float(text[:-1] or 0))

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

    try:
        return int(float(text))
    except ValueError:
        return 0


def _percent(used, total):
    if not total:
        return 0
    return round(used * 100 / total)


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
    items = result.get("items")
    return items if isinstance(items, list) else []


def _format_bytes_to_gib(value):
    return round(value / 1024 ** 3, 2)


def _format_mib_to_gib(value):
    return round(value / 1024, 2)


def _sum_resources(resource_map, keys):
    return sum(_parse_quantity(resource_map.get(key)) for key in keys)


def _first_existing(resource_map, keys):
    for key in keys:
        if key in resource_map:
            return key, _parse_quantity(resource_map.get(key))
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


def _get_cluster_resource_summary():
    client, err = _paas_client()
    if err:
        return None, err

    status, result = client.request_with_status("GET", f"/clusters/{Config.DCE_CLUSTER}")
    if not 200 <= status < 300:
        return None, _error("集群资源汇总查询失败", status, result)

    resource_summary = _safe_get(result, "status", "resourceSummary", default={}) or {}
    allocatable = resource_summary.get("allocatable") or {}
    allocated = resource_summary.get("allocated") or {}

    return {
        "client": client,
        "cluster": result,
        "allocatable": allocatable,
        "allocated": allocated,
    }, None


def _list_cluster_nodes(client):
    status, result = client.request_with_status("GET", f"/clusters/{Config.DCE_CLUSTER}/nodes")
    if not 200 <= status < 300:
        return [], _error("节点列表查询失败", status, result)
    return _extract_items(result), None


def _node_name(node):
    return _safe_get(node, "metadata", "name", default="") or node.get("name") or ""


def _node_labels(node):
    return _safe_get(node, "metadata", "labels", default={}) or {}


def _node_allocatable(node):
    return (
        _safe_get(node, "status", "resourceSummary", "allocatable", default=None)
        or _safe_get(node, "status", "allocatable", default=None)
        or _safe_get(node, "status", "capacity", default=None)
        or {}
    )


def _node_allocated(node):
    return (
        _safe_get(node, "status", "resourceSummary", "allocated", default=None)
        or _safe_get(node, "status", "allocated", default=None)
        or {}
    )


def _extract_gpu_model(node):
    labels = _node_labels(node)

    candidate_keys = [
        "nvidia.com/gpu.product",
        "gpu.nvidia.com/model",
        "accelerator",
        "hami.io/vgpu-devices-to-allocate",
        "huawei.com/ascend.product",
        "huawei.com/npu.product",
    ]

    for key in candidate_keys:
        value = labels.get(key)
        if value:
            return str(value).replace("_", " ")

    allocatable = _node_allocatable(node)
    if _parse_quantity(allocatable.get("huawei.com/Ascend310P")):
        return "Ascend 310P"
    if _parse_quantity(allocatable.get("nvidia.com/vgpu")):
        return "NVIDIA vGPU"
    if _parse_quantity(allocatable.get("nvidia.com/gpu")):
        return "NVIDIA GPU"
    return "Unknown"


def _node_status(node):
    conditions = _safe_get(node, "status", "conditions", default=[]) or []
    for condition in conditions:
        if condition.get("type") == "Ready":
            return "Ready" if condition.get("status") == "True" else "NotReady"
    return _safe_get(node, "status", "phase", default="Unknown")


def summary(query):
    snapshot, err = _get_cluster_resource_summary()
    if err:
        return err

    allocatable = snapshot["allocatable"]
    allocated = snapshot["allocated"]
    client = snapshot["client"]

    raw_nodes, nodes_error = _list_cluster_nodes(client)
    node_count = len(raw_nodes)

    gpu_total = _sum_resources(allocatable, GPU_COUNT_KEYS)
    gpu_used = _sum_resources(allocated, GPU_COUNT_KEYS)
    gpu_available = max(gpu_total - gpu_used, 0)

    gpu_mem_key, gpu_mem_total_mib = _first_existing(allocatable, GPU_MEMORY_KEYS)
    gpu_mem_used_mib = _parse_quantity(allocated.get(gpu_mem_key)) if gpu_mem_key else 0

    gpu_core_key, gpu_core_total = _first_existing(allocatable, GPU_CORE_KEYS)
    gpu_core_used = _parse_quantity(allocated.get(gpu_core_key)) if gpu_core_key else 0

    cpu_total_m = _parse_quantity(allocatable.get("cpu"))
    cpu_used_m = _parse_quantity(allocated.get("cpu"))

    memory_total_bytes = _parse_quantity(allocatable.get("memory"))
    memory_used_bytes = _parse_quantity(allocated.get("memory"))

    gpu_percent = _percent(gpu_used, gpu_total)
    gpu_mem_percent = _percent(gpu_mem_used_mib, gpu_mem_total_mib)
    gpu_core_percent = _percent(gpu_core_used, gpu_core_total)
    max_percent = max(gpu_percent, gpu_mem_percent, gpu_core_percent)

    level = _health_level(max_percent)

    return _ok({
        "cluster": Config.DCE_CLUSTER,
        "namespace": Config.DCE_NAMESPACE,
        "health": {
            "level": level,
            "text": _health_text(level),
            "score": max(0, 100 - max_percent // 2),
            "message": "资源调度健康" if level == "green" else "部分资源接近高负载",
        },
        "cards": {
            "node_count": node_count,

            "gpu_total": gpu_total,
            "gpu_used": gpu_used,
            "gpu_available": gpu_available,
            "gpu_alloc_percent": gpu_percent,

            "vgpu_total": _parse_quantity(allocatable.get("nvidia.com/vgpu")),
            "vgpu_used": _parse_quantity(allocated.get("nvidia.com/vgpu")),
            "vgpu_available": max(
                _parse_quantity(allocatable.get("nvidia.com/vgpu"))
                - _parse_quantity(allocated.get("nvidia.com/vgpu")),
                0,
            ),
            "vgpu_alloc_percent": _percent(
                _parse_quantity(allocated.get("nvidia.com/vgpu")),
                _parse_quantity(allocatable.get("nvidia.com/vgpu")),
            ),

            "gpu_core_total": gpu_core_total,
            "gpu_core_used": gpu_core_used,
            "gpu_core_percent": gpu_core_percent,

            "gpu_mem_total_gib": _format_mib_to_gib(gpu_mem_total_mib),
            "gpu_mem_used_gib": _format_mib_to_gib(gpu_mem_used_mib),
            "gpu_mem_percent": gpu_mem_percent,

            "cpu_total_m": cpu_total_m,
            "cpu_used_m": cpu_used_m,
            "cpu_percent": _percent(cpu_used_m, cpu_total_m),

            "memory_total_gib": _format_bytes_to_gib(memory_total_bytes),
            "memory_used_gib": _format_bytes_to_gib(memory_used_bytes),
            "memory_percent": _percent(memory_used_bytes, memory_total_bytes),
        },
        "raw_resource_keys": {
            "allocatable": sorted(list(allocatable.keys())),
            "allocated": sorted(list(allocated.keys())),
        },
        "node_error": nodes_error,
    })


def nodes(query):
    snapshot, err = _get_cluster_resource_summary()
    if err:
        return err

    client = snapshot["client"]
    raw_nodes, nodes_error = _list_cluster_nodes(client)
    if nodes_error:
        return nodes_error

    items = []

    for node in raw_nodes:
        allocatable = _node_allocatable(node)
        allocated = _node_allocated(node)

        gpu_total = _sum_resources(allocatable, GPU_COUNT_KEYS)
        gpu_used = _sum_resources(allocated, GPU_COUNT_KEYS)

        gpu_mem_key, gpu_mem_total_mib = _first_existing(allocatable, GPU_MEMORY_KEYS)
        gpu_mem_used_mib = _parse_quantity(allocated.get(gpu_mem_key)) if gpu_mem_key else 0

        gpu_core_key, gpu_core_total = _first_existing(allocatable, GPU_CORE_KEYS)
        gpu_core_used = _parse_quantity(allocated.get(gpu_core_key)) if gpu_core_key else 0

        max_percent = max(
            _percent(gpu_used, gpu_total),
            _percent(gpu_mem_used_mib, gpu_mem_total_mib),
            _percent(gpu_core_used, gpu_core_total),
        )
        level = _health_level(max_percent)

        item = {
            "node_name": _node_name(node),
            "status": _node_status(node),
            "health_level": level,
            "health_text": _health_text(level),
            "gpu_model": _extract_gpu_model(node),

            "gpu_total": gpu_total,
            "gpu_used": gpu_used,
            "gpu_available": max(gpu_total - gpu_used, 0),
            "gpu_percent": _percent(gpu_used, gpu_total),

            "vgpu_total": _parse_quantity(allocatable.get("nvidia.com/vgpu")),
            "vgpu_used": _parse_quantity(allocated.get("nvidia.com/vgpu")),
            "vgpu_percent": _percent(
                _parse_quantity(allocated.get("nvidia.com/vgpu")),
                _parse_quantity(allocatable.get("nvidia.com/vgpu")),
            ),

            "gpu_core_total": gpu_core_total,
            "gpu_core_used": gpu_core_used,
            "gpu_core_percent": _percent(gpu_core_used, gpu_core_total),

            "gpu_mem_total_gib": _format_mib_to_gib(gpu_mem_total_mib),
            "gpu_mem_used_gib": _format_mib_to_gib(gpu_mem_used_mib),
            "gpu_mem_percent": _percent(gpu_mem_used_mib, gpu_mem_total_mib),

            "cpu_total_m": _parse_quantity(allocatable.get("cpu")),
            "cpu_used_m": _parse_quantity(allocated.get("cpu")),

            "memory_total_gib": _format_bytes_to_gib(_parse_quantity(allocatable.get("memory"))),
            "memory_used_gib": _format_bytes_to_gib(_parse_quantity(allocated.get("memory"))),

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
        }

        if query.get("node_name") and query.get("node_name") != item["node_name"]:
            continue

        items.append(item)

    items.sort(key=lambda item: item.get("gpu_percent", 0), reverse=True)

    return _ok({
        "items": items,
        "total": len(items),
    })


def gpus(query):
    snapshot, err = _get_cluster_resource_summary()
    if err:
        return err

    allocatable = snapshot["allocatable"]
    allocated = snapshot["allocated"]
    client = snapshot["client"]

    resources = []
    for key, meta in GPU_RESOURCE_META.items():
        total = _parse_quantity(allocatable.get(key))
        used = _parse_quantity(allocated.get(key))

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

    raw_nodes, _ = _list_cluster_nodes(client)
    model_map = {}

    for node in raw_nodes:
        model = _extract_gpu_model(node)
        allocatable = _node_allocatable(node)
        count = _sum_resources(allocatable, GPU_COUNT_KEYS)
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
    })


def cards(query):
    node_result = nodes(query)
    if not node_result.get("is_success"):
        return node_result

    items = []

    for node in node_result.get("items", []):
        node_name = node.get("node_name") or "unknown-node"
        card_total = (
            int(node.get("vgpu_total") or 0)
            or int(node.get("gpu_total") or 0)
        )

        if card_total <= 0:
            continue

        for index in range(card_total):
            items.append({
                "card_id": f"{node_name}-card-{index + 1:02d}",
                "node_name": node_name,
                "gpu_model": node.get("gpu_model"),
                "card_status": (
                    "高负载"
                    if node.get("health_level") == "red"
                    else "运行中"
                    if node.get("gpu_used", 0) > 0 or node.get("vgpu_used", 0) > 0
                    else "空闲"
                ),
                "usage_mode": "vGPU 后台调度" if node.get("vgpu_total", 0) else "物理 GPU 调度",
                "vgpu": {
                    "allocated": node.get("vgpu_used"),
                    "total": node.get("vgpu_total"),
                },
                "gpu_core": {
                    "allocated": node.get("gpu_core_used"),
                    "total": node.get("gpu_core_total"),
                    "percent": node.get("gpu_core_percent"),
                },
                "gpu_memory": {
                    "allocated_gib": node.get("gpu_mem_used_gib"),
                    "total_gib": node.get("gpu_mem_total_gib"),
                    "percent": node.get("gpu_mem_percent"),
                },
                "data_precision": "node_resource_snapshot",
            })

    return _ok({
        "items": items,
        "total": len(items),
        "note": "当前按节点资源生成卡片。后续接入 DCGM / HAMI / Ascend exporter 后，可精确到真实物理卡 UUID。",
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
        "note": "当前未接入历史采集表，趋势接口返回当前快照序列。后续可接 Prometheus 或 MySQL 采集表。",
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
    status, result = client._request("GET", f"/api/v1/namespaces/{namespace}/resourcequotas")

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
