from flask import Blueprint, jsonify, request

from . import service


deploy_bp = Blueprint("deploy", __name__)


@deploy_bp.post("/check-available")
def check_available():
    # 资源预检接口，后续迁移现有 app_x86_195.py 中的资源校验逻辑。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.check_available(payload))


@deploy_bp.post("/create-default")
def create_default():
    # 创建推理实例，后续负责生成 Deployment、Service、端口和实例记录。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.create_default(payload)
    return jsonify(result), status_code


@deploy_bp.post("/retrieve")
def retrieve():
    # 查询单个部署详情，返回 Deployment、Pod 状态和运行摘要。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.retrieve(payload))


@deploy_bp.post("/release")
def release():
    # 释放部署资源，后续删除 Deployment、Service 并更新实例状态。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.release(payload))


@deploy_bp.post("/reset")
def reset():
    # 重启部署实例，后续复用 PaaS/Kubernetes 的 restart 能力。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.reset(payload))


@deploy_bp.post("/list")
def list_deployments():
    # 查询部署列表，实例中心页面会优先使用这个接口。
    return jsonify(service.list_deployments())
