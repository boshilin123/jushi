from flask import Blueprint, Response, jsonify

from .openapi_specs import build_openapi_spec


docs_bp = Blueprint("docs", __name__)

# Swagger 页面读取的完整 OpenAPI 配置由 openapi_specs 分模块拼装。
OPENAPI_SPEC = build_openapi_spec()


@docs_bp.get("/openapi.json")
def openapi_json():
    # 返回 Swagger UI 读取的 OpenAPI JSON。
    return jsonify(OPENAPI_SPEC)


@docs_bp.get("")
@docs_bp.get("/")
def swagger_ui():
    # 渲染 Swagger UI 页面，方便开发和联调阶段直接调试接口。
    html = """
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>聚时 API Docs</title>
        <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
        <style>body { margin: 0; }</style>
      </head>
      <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
          window.ui = SwaggerUIBundle({
            url: "/api/docs/openapi.json",
            dom_id: "#swagger-ui",
            deepLinking: true,
            presets: [SwaggerUIBundle.presets.apis],
          });
        </script>
      </body>
    </html>
    """
    return Response(html, mimetype="text/html")
