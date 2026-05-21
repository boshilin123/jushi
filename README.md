# jushi

## 文档

- [聚时 AI 推理资源管理平台一期开发方案](docs/phase1-development-plan.md)
- Swagger UI：启动后访问 `http://localhost:8080/api/docs`
- OpenAPI JSON：启动后访问 `http://localhost:8080/api/docs/openapi.json`

## 本地启动

后端 API / Swagger：

```powershell
cd backend
python app.py
```

访问：

```text
http://localhost:8080/api/docs
```

如果使用 PyCharm 的 Flask 配置直接 `flask run`，默认端口通常是 `5000`。此时访问：

```text
http://localhost:5000/api/docs
```

前端页面需要单独启动：

```powershell
cd ui
npm run dev
```

访问 Vite 输出的地址，通常是：

```text
http://localhost:5173
```

## 目录

```text
.
├── backend/              # Flask 后端一期工程骨架
│   ├── modules/          # 按业务模块拆分，每个模块独立 routes.py
│   ├── services/         # PaaS、K8s、GPU profile、Shell runner
│   ├── db/               # MySQL 连接与初始化 SQL
│   └── scripts/          # 启停脚本
├── ui/                   # React + TypeScript + Vite 前端
├── docs/                 # 项目方案与交付文档
├── docker-compose.yml    # 一期本地/容器化编排
└── .env.example          # 环境变量模板
```
