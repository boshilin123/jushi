# BlueDot_Intelligence_v1.5 交付包清单

## 1. 项目说明

- 项目名称：BlueDot Intelligence AI 算力资源管理端
- 版本：BlueDot_Intelligence_v1.5
- 技术栈：React + Vite + TypeScript + Recharts + Lucide React
- 数据模式：默认假数据演示，已提供后端接口适配层
- 发布平台：Netlify
- 线上地址：https://bluedot-intelligence-v1-5.netlify.app

## 2. 工程文件

| 路径 | 说明 |
| --- | --- |
| `src/index.tsx` | 页面结构、交互逻辑、演示数据与主要状态 |
| `src/styles.css` | 全局视觉规范、响应式、自适应、动效与组件样式 |
| `src/api.ts` | 后端接口类型定义与请求封装 |
| `index.html` | Vite HTML 入口 |
| `package.json` | 依赖与脚本 |
| `package-lock.json` | 锁定依赖版本 |
| `netlify.toml` | Netlify 构建配置与 SPA fallback |
| `dist/` | 本次生产构建产物 |

## 3. 项目文档

| 路径 | 说明 |
| --- | --- |
| `README.md` | 项目总览、运行方式、发布信息 |
| `API_INTEGRATION.md` | 后端接口契约、字段说明、请求/响应示例 |
| `UI_STYLE_GUIDELINES.md` | 页面复现与扩展所需 UI 规范 |
| `DEPLOYMENT.md` | 本地开发、生产构建、Netlify 发布说明 |
| `DELIVERY_REPORT.md` | 交付审查结论、后端联调重点、已知非阻塞项 |
| `PACKAGE_MANIFEST.md` | 本文件，交付包结构说明 |

## 4. 不包含项

交付压缩包默认不包含：

- `node_modules/`
- `.DS_Store`
- 临时截图文件
- 本机缓存文件

## 5. 复现步骤

```bash
npm install
npm run build
npm run preview
```

如需真实后端：

```bash
VITE_API_BASE_URL=https://your-api-domain.example.com npm run build
```

## 6. 发布记录

- Site ID：`30e7f7b8-fb63-48bf-b94c-fb0d87e0d017`
- Production URL：https://bluedot-intelligence-v1-5.netlify.app
- Deploy URL：https://6a0acb699a26ec314f9ed5fa--bluedot-intelligence-v1-5.netlify.app
- Deploy Logs：https://app.netlify.com/projects/bluedot-intelligence-v1-5/deploys/6a0acb699a26ec314f9ed5fa
