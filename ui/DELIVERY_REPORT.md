# BlueDot 交付审查报告

## 1. 当前状态

- 项目类型：React + Vite 单页应用。
- 数据模式：默认假数据演示。
- 后端对接：已完善 `src/api.ts` 与 `API_INTEGRATION.md`。
- 发布配置：已新增 `netlify.toml`，生产构建目录为 `dist/`。
- 构建状态：`npm run build` 已通过。
- 发布状态：已发布到 Netlify 新项目 `bluedot-intelligence-v1-5`。

## 2. 代码审查结论

当前工程可作为前端演示版交付给后端联调，具备以下条件：

- 页面主流程完整：首页、资源中心、实例中心、待发布、端口白名单、告警中心、审计日志、登录页。
- 创建实例弹窗已按素材接口字段收敛，不再暴露后端不接收的镜像、手动端口、健康检查路径等字段。
- 资源预检具备加载态与结果态，可映射后端 `can_create`。
- 运维操作已有日志、停止、重启、释放的前端交互壳。
- 端口白名单具备唯一性校验提示，后端接口契约已补齐。
- 告警中心和审计日志具备筛选、解决、导入、导出等对接契约。
- 登录页、顶部栏、侧边栏、卡片和表单样式已统一。
- 构建产物已生成在 `dist/`。

## 3. 后端联调重点

优先接入接口：

1. `POST /api/deploy/check-available`
2. `POST /api/deploy/create-default`
3. `POST /api/deploy/list`
4. `POST /api/deploy/retrieve`
5. `POST /api/deploy/reset`
6. `POST /api/deploy/release`
7. `POST /api/deploy/stop`
8. `POST /api/deploy/logs`，成功响应为 `text/plain` Pod describe 文本
9. `GET /api/port-list/list`
10. `POST /api/port-list/add`
11. `PUT /api/port-list/update/{item_id}`
12. `DELETE /api/port-list/delete/{item_id}`
13. `GET /api/port-list/resolve`
14. `POST /api/alerts/list`
15. `POST /api/alerts/resolve`
16. `POST /api/alerts/ignore`

待后端确认：

- 资源不足排队 `/api/deploy/queue` 是否重新纳入范围。
- vGPU 预测占用是否由后端返回。
- 审计日志导入、导出是否继续保留在一期范围。

## 4. 已知非阻塞项

- Vite 构建提示 JS chunk 大于 500 kB，原因是演示页集中在一个入口文件且包含图表库。当前演示交付不阻塞，后续生产化可按页面拆分动态 import。
- 当前未接真实认证后端，登录为前端演示流程。
- 页面数据仍为静态假数据，接口适配层已准备但尚未切换页面数据源。

## 5. 发布说明

Netlify 登录授权已完成，并已按本次要求创建新项目发布。

- 产品版本名：`BlueDot_Intelligence_v1.5`
- Netlify 站点名：`bluedot-intelligence-v1-5`
- Production URL：https://bluedot-intelligence-v1-5.netlify.app
- Deploy URL：https://6a0acb699a26ec314f9ed5fa--bluedot-intelligence-v1-5.netlify.app
- Deploy Logs：https://app.netlify.com/projects/bluedot-intelligence-v1-5/deploys/6a0acb699a26ec314f9ed5fa

Netlify 站点 slug 只允许字母、数字与连字符，因此原始版本名 `BlueDot_Intelligence_v1.5` 在 Netlify 中使用等价 slug `bluedot-intelligence-v1-5`。

后续再次发布：

```bash
npm run build
npx netlify deploy --prod --dir=dist
```
