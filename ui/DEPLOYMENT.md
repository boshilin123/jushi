# BlueDot 前端部署说明

## 本地开发

```bash
npm install
npm run dev
```

默认开发服务：

```text
http://localhost:5173
```

## 生产构建

```bash
npm run build
```

构建产物输出：

```text
dist/
```

## 本地预览生产包

```bash
npm run preview
```

## 后端接口地址

如需接入真实后端，在部署环境中设置：

```bash
VITE_API_BASE_URL=https://your-api-domain.example.com
```

当前演示版页面默认使用本地假数据，接口适配文件已准备在：

```text
src/api.ts
```

## Netlify 部署

项目已包含 `netlify.toml`：

```toml
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

部署命令：

```bash
npx netlify deploy --prod
```

如果需要预览部署：

```bash
npx netlify deploy
```

## 当前生产发布

- 产品版本名：`BlueDot_Intelligence_v1.5`
- Netlify 站点名：`bluedot-intelligence-v1-5`
- Site ID：`30e7f7b8-fb63-48bf-b94c-fb0d87e0d017`
- Production URL：https://bluedot-intelligence-v1-5.netlify.app
- Deploy URL：https://6a0acb699a26ec314f9ed5fa--bluedot-intelligence-v1-5.netlify.app
- Deploy Logs：https://app.netlify.com/projects/bluedot-intelligence-v1-5/deploys/6a0acb699a26ec314f9ed5fa

说明：Netlify 站点 slug 只允许字母、数字与连字符，因此 `BlueDot_Intelligence_v1.5` 对应发布 slug 为 `bluedot-intelligence-v1-5`。

## 交付清单

- `src/index.tsx`：页面与交互主文件。
- `src/styles.css`：视觉规范与响应式样式。
- `src/api.ts`：后端接口适配层。
- `API_INTEGRATION.md`：接口字段、请求体、后端待确认项。
- `UI_STYLE_GUIDELINES.md`：最终 UI 规范。
- `DEPLOYMENT.md`：部署说明。
- `README.md`：项目总览。
- `netlify.toml`：Netlify 部署配置。
- `dist/`：生产构建产物。
