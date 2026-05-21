def build_deploy_record(name: str, payload: dict) -> dict:
    # 构建部署实例记录，后续写入 deploy_instance 表。
    content = payload.get("content", {}) or {}
    devices = content.get("devices", {}) or {}
    gpu_type = next(iter(devices.keys()), "")
    return {
        "deployment_name": name,
        "gpu_type": gpu_type,
        "gpu_count": devices.get(gpu_type, 0) if gpu_type else 0,
        "deploy_type": content.get("deployType", ""),
        "creator": content.get("creator", ""),
    }
