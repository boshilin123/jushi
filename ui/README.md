# BlueDot Intelligence AI 算力资源管理端

这是一个基于 React + Vite 的演示版管理端，用于复现 BlueDot AI 算力资源管理、vGPU 后台调度、实例部署运维、资源预检、告警与审计等核心页面。

当前版本以假数据演示为主，已补充后端接口适配层与接口文档，方便后续接入真实 API。

## 发布信息

- 产品版本名：`BlueDot_Intelligence_v1.5`
- Netlify 站点名：`bluedot-intelligence-v1-5`
- 线上地址：https://bluedot-intelligence-v1-5.netlify.app
- Netlify Project ID：`30e7f7b8-fb63-48bf-b94c-fb0d87e0d017`

## 本地运行

```bash
npm install
npm run dev
```

## 构建

```bash
npm run build
```

构建产物输出到 `dist/`。

## 主要文件

- `src/index.tsx`：页面结构、交互和假数据。
- `src/styles.css`：统一视觉规范、响应式、动效。
- `src/api.ts`：后端接口适配层。
- `API_INTEGRATION.md`：后端接口字段、请求体、响应建议与待确认项。
- `UI_STYLE_GUIDELINES.md`：UI 规范文档。
- `DEPLOYMENT.md`：部署说明。
- `DELIVERY_REPORT.md`：交付审查报告。
- `PACKAGE_MANIFEST.md`：交付包清单。
- `netlify.toml`：Netlify 发布配置。

## 接口接入

正式接入后端时设置：

```bash
VITE_API_BASE_URL=https://your-api-domain.example.com
```

创建实例、资源预检、查询、停止、释放、重启、排队、实例日志、端口白名单、告警、审计日志、日志导入与导出接口已在 `src/api.ts` 中按素材接口结构封装。
