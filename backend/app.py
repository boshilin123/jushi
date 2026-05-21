import os

from flask import Flask

from modules.alerts import alerts_bp
from modules.auth import auth_bp
from modules.deploy import deploy_bp
from modules.docs import docs_bp
from modules.logs import logs_bp
from modules.pods import pods_bp
from modules.ports import ports_bp
from modules.resources import resources_bp
from modules.system import system_bp
from modules.users import users_bp


def _resolve_docs_port() -> str:
    # 兼容 python app.py 和 flask run 两种启动方式，尽量打印正确的 Swagger 端口。
    if os.getenv("FLASK_RUN_PORT"):
        return os.getenv("FLASK_RUN_PORT", "")
    if os.getenv("PORT"):
        return os.getenv("PORT", "")
    if os.getenv("FLASK_RUN_FROM_CLI") == "true":
        return "5000"
    return "8080"


def create_app() -> Flask:
    app = Flask(__name__)

    # 按业务域注册接口模块；根路径 "/" 暂不占用，后续留给前端或网关。
    app.register_blueprint(system_bp)
    app.register_blueprint(docs_bp, url_prefix="/api/docs")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(deploy_bp, url_prefix="/api/deploy")
    app.register_blueprint(ports_bp, url_prefix="/api/port-list")
    app.register_blueprint(resources_bp, url_prefix="/api/resources")
    app.register_blueprint(pods_bp, url_prefix="/api/pods")
    app.register_blueprint(alerts_bp, url_prefix="/api/alerts")
    app.register_blueprint(logs_bp, url_prefix="/api/logs")

    docs_port = _resolve_docs_port()
    print(f"[Jushi] Swagger UI: http://127.0.0.1:{docs_port}/api/docs")
    print(f"[Jushi] OpenAPI JSON: http://127.0.0.1:{docs_port}/api/docs/openapi.json")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
