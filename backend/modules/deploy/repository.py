def save_deploy_instance(record: dict):
    # 保存部署实例记录，后续写入 deploy_instance 表。
    return record


def list_deploy_instances():
    # 查询部署实例列表，后续优先从 deploy_instance 表读取并补充实时状态。
    return []


def update_deploy_status(name: str, status: str):
    # 更新部署实例状态，如 created、running、released、failed。
    return {"deployment_name": name, "status": status}
