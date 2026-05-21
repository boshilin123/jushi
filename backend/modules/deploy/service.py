from . import repository
from .model import build_deploy_record
from .schema import get_deploy_name, validate_create_payload


def check_available(payload: dict) -> dict:
    # 资源预检业务，后续迁移现有资源校验、GPU 余量和端口避让逻辑。
    return {"can_create": True, "payload": payload}


def create_default(payload: dict) -> tuple[dict, int]:
    # 创建部署业务，后续编排 PaaS 调用、Service 创建、端口返回和实例入库。
    valid, message = validate_create_payload(payload)
    if not valid:
        return {"is_success": False, "msg": message}, 400

    name = "pending-implementation"
    repository.save_deploy_instance(build_deploy_record(name, payload))
    return {"deployment_name": name, "payload": payload}, 200


def retrieve(payload: dict) -> dict:
    # 查询部署详情，后续同时返回 Deployment、Pod 状态和运行摘要。
    name = get_deploy_name(payload)
    return {"deployment_name": name, "deployment": None, "pods": [], "summary": {}}


def release(payload: dict) -> dict:
    # 释放部署业务，后续删除 Deployment、Service 并更新实例状态。
    name = get_deploy_name(payload)
    return repository.update_deploy_status(name, "released")


def reset(payload: dict) -> dict:
    # 重启部署业务，后续调用 PaaS/Kubernetes restart 能力。
    name = get_deploy_name(payload)
    return {"deployment_name": name, "is_success": True}


def list_deployments() -> dict:
    # 查询部署列表，后续合并数据库实例记录和 PaaS 实时状态。
    return {"items": repository.list_deploy_instances()}
