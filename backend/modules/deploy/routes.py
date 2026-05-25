from flask import Blueprint, jsonify, request

from . import service


deploy_bp = Blueprint("deploy", __name__)


@deploy_bp.post("/check-available")
def check_available():
    # 资源预检接口：后续迁移 app_x86_195.py/app_arm_195.py 中的 GPU 余量、CPU/内存和端口避让检查。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.check_available(payload))


@deploy_bp.post("/create-default")
def create_default():
    # 创建推理实例：后续生成 PaaS Deployment + NodePort Service，并把创建结果写入 deploy_instance。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.create_default(payload)
    return jsonify(result), status_code


@deploy_bp.post("/retrieve")
def retrieve():
    # 查询单个部署详情：后续合并 Deployment 详情和 Pod 状态，供实例中心查看。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.retrieve(payload))


@deploy_bp.post("/release")
def release():
    # 释放部署资源：后续删除 PaaS Deployment 和 Service，并更新实例状态。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.release(payload))


@deploy_bp.post("/reset")
def reset():
    # 重启部署实例：后续复用 PaaS/Kubernetes restart 能力。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.reset(payload))


@deploy_bp.post("/list")
def list_deployments():
    # 查询部署列表，实例中心页面会优先使用这个接口。
    return jsonify(service.list_deployments())
