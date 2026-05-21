from flask import Blueprint, jsonify, request

from . import service
from .schema import normalize_resource_query


resources_bp = Blueprint("resources", __name__)


@resources_bp.get("/summary")
def summary():
    # 查询集群资源总览，用于资源中心顶部统计卡片。
    return jsonify(service.summary(normalize_resource_query(request.args)))


@resources_bp.get("/nodes")
def nodes():
    # 查询节点列表和节点资源状态。
    return jsonify(service.nodes(normalize_resource_query(request.args)))


@resources_bp.get("/gpus")
def gpus():
    # 按 NVIDIA / Huawei 等 GPU 类型统计总量、已用和可用数量。
    return jsonify(service.gpus(normalize_resource_query(request.args)))


@resources_bp.get("/quotas")
def quotas():
    # 查询资源配额信息，后续用于展示命名空间或用户维度限制。
    return jsonify(service.quotas(normalize_resource_query(request.args)))
