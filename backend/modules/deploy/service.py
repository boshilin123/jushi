from . import repository
from .model import build_deploy_record
from .schema import get_deploy_name, validate_create_payload


def check_available(payload: dict) -> dict:
    # TODO: 迁移旧脚本 check_resources_sufficient，并直接复用 ports.repository.resolve_blocked_ports 做端口避让。
    return {"can_create": True, "payload": payload}


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
