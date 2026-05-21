from flask import Blueprint, jsonify, request

from . import service


ports_bp = Blueprint("ports", __name__)


@ports_bp.get("/list")
def list_ports():
    # 查询封闭端口列表，后续可从 port_block_rule 表读取。
    return jsonify(service.list_ports())


@ports_bp.post("/add")
def add_port():
    # 新增封闭端口规则，创建实例随机端口时需要避开这些端口。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.add_port(payload)
    return jsonify(result), status_code


@ports_bp.put("/update/<item_id>")
def update_port(item_id):
    # 更新封闭端口规则，通常用于修改备注或端口值。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.update_port(item_id, payload)
    return jsonify(result), status_code


@ports_bp.delete("/delete/<item_id>")
def delete_port(item_id):
    # 删除封闭端口规则，删除后该端口可重新进入随机分配范围。
    return jsonify(service.delete_port(item_id))


@ports_bp.get("/resolve")
def resolve_ports():
    # 输出端口避让快照，主服务创建实例前会调用这个接口。
    return jsonify(service.resolve_ports())
