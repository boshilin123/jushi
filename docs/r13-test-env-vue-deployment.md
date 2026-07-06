# r13 测试环境部署步骤（保留老脚本端口）

本文档用于在老脚本已经运行的 r13 测试环境中部署新版聚时系统。

代码目录：

```text
/opt/software/jushi
/opt/software/jushiapi-ui-test
```

约束：

- 老脚本正在占用宿主机 `8080`、`8081`、`8082`、`8091`，这些端口不能关闭、不能抢占。
- 新版前端使用 `jushiapi-ui-test`，不使用 `jushi/ui` 历史 React 前端。
- 新版后端和 MySQL 使用 `jushi/docker-compose.backend.yml` 启动。
- 继续使用 `jushi/.env.example`，不新增 `.env.server`。
- `18000` 端口当前未被占用，前端继续使用 `18000:80`。
- 数据库密码保持当前配置不变：`MYSQL_ROOT_PASSWORD=root_pass`，`MYSQL_USER=jushi`，`MYSQL_PASSWORD=jushi_pass`。

## 一、本次会新增、减少、修改的内容

新增：

- 新增 Docker 容器 `jushi-mysql`，作为聚时项目独立 MySQL。
- 新增 Docker 容器 `jushi-api`，运行 Flask 后端。
- 新增 Docker 容器 `jushi-frontend`，运行 Vue 3 前端和 Nginx 反向代理。
- 新增 Docker 网络 `jushi_default`，由后端 compose 自动创建，前端 compose 加入该网络。
- 首次启动 MySQL 时新增数据目录 `/opt/software/jushi/mysql/data`。

减少 / 不再使用：

- 不启动 `jushi/docker-compose.yml` 中的历史 React 前端。
- 不启动独立 `jushi-port-list` 服务，端口避让由 `jushi-api` 内部提供 `/api/port-list/*`。
- 不把新版后端映射到宿主机 `8080`。
- 不把新版 MySQL 映射到宿主机 `3306`。

需要修改：

- 修改 `/opt/software/jushi/.env.example` 中的 DCE / K8s 配置。
- 如客户要求，可在 MySQL 初始化后修改 `sys_user` 中的默认登录账号和密码。
- 可选：在 `/opt/software/jushi/.env.example` 中设置 `WORKSHOP_MODE_ENABLED=false`，避免误进入旧脚本车间固定端口模式。

不修改：

- 不停止老脚本进程。
- 不释放或占用老脚本端口 `8080`、`8081`、`8082`、`8091`。
- 不修改 MySQL compose 默认密码。



## 二、端口冲突检查

部署前执行：

```bash
netstat -tulnp | grep -E ':18000|:8080|:8081|:8082|:8091|:3306'
docker ps -a | grep -E 'jushi-api|jushi-mysql|jushi-frontend'
```

预期：

- `8080`、`8081`、`8082`、`8091` 可能已有老脚本进程监听，不能处理它们。
- `18000` 当前应无占用。
- 宿主机 `3306` 即使被其他服务占用，也不影响新版部署，因为 `jushi-mysql` 不映射宿主机端口。

新版服务端口规划：


| 服务               | 容器端口   | 宿主机端口   | 是否与老脚本冲突 |
| ---------------- | ------ | ------- | -------- |
| `jushi-frontend` | `80`   | `18000` | 不冲突      |
| `jushi-api`      | `8080` | 不映射     | 不冲突      |
| `jushi-mysql`    | `3306` | 不映射     | 不冲突      |




## 三、准备后端环境变量

编辑：

```bash
cd /opt/software/jushi
vi .env.example
```

保留 MySQL 配置：

```env
MYSQL_HOST=jushi-mysql
MYSQL_PORT=3306
MYSQL_DATABASE=jushi
MYSQL_USER=jushi
MYSQL_PASSWORD=jushi_pass
```

确认或修改 DCE / K8s 配置：

```env
DCE_API_BASE=https://DCE地址/apis/kpanda.io/v1alpha1
DCE_CLUSTER=实际集群名
DCE_NAMESPACE=algorithm
DCE_TOKEN="DCE平台token"

K8S_API_BASE=https://192.168.10.227:6443
K8S_TOKEN="已验证成功的 Kubernetes ServiceAccount token"
```

确认 NVIDIA 创建依赖：

```env
NVIDIA_IMAGE=nvidia/cuda:11.6.2-cudnn8-devel-ubuntu20.04_v1
ALGORITHM_PACKAGE_HOST_DIR=/opt
NVIDIA_PACKAGE_NAME=mtworkflow_x86.zip
NVIDIA_WORKDIR=mtworkflow_x86
```

说明：

- `K8S_TOKEN` 必须使用已经通过 `curl` 验证的 token。
- 不要把真实 token 提交到代码仓库。
- 当前环境已确认 `/opt/mtworkflow_x86.zip`、`mtworkflow_x86/cfg/runmode.cfg`、`mtworkflow_x86/mtworkflow.sh` 和 NVIDIA 镜像存在。



## 四、确认 K8s 权限

如果已经执行过：

```bash
kubectl apply -f docs/jushi-alert-cluster-read-rbac.yaml
```

继续确认 ServiceAccount 权限：

```bash
kubectl auth can-i list pods -n algorithm --as=system:serviceaccount:algorithm:jushi-deploy-api
kubectl auth can-i list events -n algorithm --as=system:serviceaccount:algorithm:jushi-deploy-api
kubectl auth can-i list nodes --as=system:serviceaccount:algorithm:jushi-deploy-api
```

如果部署创建、停止、日志、Pod 运维也要通过该 token 使用，还需确认：

```bash
kubectl auth can-i create services -n algorithm --as=system:serviceaccount:algorithm:jushi-deploy-api
kubectl auth can-i delete services -n algorithm --as=system:serviceaccount:algorithm:jushi-deploy-api
kubectl auth can-i create deployments -n algorithm --as=system:serviceaccount:algorithm:jushi-deploy-api
kubectl auth can-i patch deployments -n algorithm --as=system:serviceaccount:algorithm:jushi-deploy-api
kubectl auth can-i delete deployments -n algorithm --as=system:serviceaccount:algorithm:jushi-deploy-api
kubectl auth can-i get pods/log -n algorithm --as=system:serviceaccount:algorithm:jushi-deploy-api
kubectl auth can-i delete pods -n algorithm --as=system:serviceaccount:algorithm:jushi-deploy-api
```

预期均返回：

```text
yes
```

如果返回 `no`，先补 Role / RoleBinding，再继续部署。

## 五、启动后端和 MySQL

只启动后端 compose，不使用 `docker-compose.yml`：

```bash
cd /opt/software/jushi
docker compose -f docker-compose.backend.yml up -d --build
docker compose -f docker-compose.backend.yml ps
```

预期：

```text
jushi-mysql   running / healthy
jushi-api     running
```

查看日志：

```bash
docker logs --tail=100 jushi-mysql
docker logs --tail=200 jushi-api
```

如果 MySQL 首次启动，`backend/db/init.sql` 会自动创建表和默认用户。已有 `/opt/software/jushi/mysql/data` 时，`init.sql` 不会重复执行。

## 五-A、内网离线镜像部署方案（三镜像方案）

r13 当前是内网环境，不能访问 Docker Hub、npm registry 或 PyPI。推荐在青海开发服务器或其他可联网服务器完成构建，再把镜像离线传入 r13。

本方案包含三个镜像：

```text
jushiapi-ui-test-jushi-frontend:latest
jushi-jushi-api:latest
mysql:8.0
```



### 1. 在可联网开发服务器确认镜像

```bash
docker images | grep -E 'jushi|mysql'
```

预期至少包含：

```text
jushiapi-ui-test-jushi-frontend
jushi-jushi-api
mysql
```

注意：`docker save` 使用的是镜像名，不是容器名。容器名如 `jushi-frontend`、`jushi-api`、`jushi-mysql` 只用于 `docker logs`、`docker stop` 等运行时命令。

### 2. 在可联网开发服务器打包镜像

```bash
mkdir -p /opt/software/offline-images

docker save -o /opt/software/offline-images/jushi-offline-images.tar \
  jushiapi-ui-test-jushi-frontend:latest \
  jushi-jushi-api:latest \
  mysql:8.0

gzip -f /opt/software/offline-images/jushi-offline-images.tar
ls -lh /opt/software/offline-images/jushi-offline-images.tar.gz
```

生成文件：

```text
/opt/software/offline-images/jushi-offline-images.tar.gz
```



### 3. 传输到 r13 测试环境

或在 r13 上从开发服务器拉取：

```bash
scp root@118.196.142.69:/opt/software/offline-images/jushi-offline-images.tar.gz /opt/software/
```



### 4. 在 r13 导入镜像

```bash
cd /opt/software
gunzip -f jushi-offline-images.tar.gz
docker load -i jushi-offline-images.tar
docker images | grep -E 'jushi|mysql'
```

预期看到：

```text
jushiapi-ui-test-jushi-frontend   latest
jushi-jushi-api                   latest
mysql                             8.0
```



### 5. 创建后端离线 compose 文件

为了避免 r13 再次触发 `build` 或外网拉取，复制一份离线 compose：

```bash
cd /opt/software/jushi
cp docker-compose.backend.yml docker-compose.backend.offline.yml
vi docker-compose.backend.offline.yml
```

将 `jushi-api` 改为使用本地镜像，并删除 `build:` 块：

```yaml
services:
  jushi-api:
    image: jushi-jushi-api:latest
    container_name: jushi-api
    env_file:
      - .env.example
    environment:
      TZ: Asia/Shanghai
    volumes:
      - /etc/localtime:/etc/localtime:ro
    depends_on:
      - jushi-mysql
    restart: unless-stopped

  jushi-mysql:
    image: mysql:8.0
    container_name: jushi-mysql
    command: ["--default-time-zone=+08:00"]
    environment:
      TZ: Asia/Shanghai
      MYSQL_ROOT_PASSWORD: root_pass
      MYSQL_DATABASE: jushi
      MYSQL_USER: jushi
      MYSQL_PASSWORD: jushi_pass
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - ./mysql/data:/var/lib/mysql
      - ./backend/db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    restart: unless-stopped
```

说明：

- `jushi-api` 必须使用 `image: jushi-jushi-api:latest`。
- `jushi-mysql` 使用离线导入的 `mysql:8.0`。
- r13 的 Compose 兼容实现可能忽略 `healthcheck` 和 `depends_on.condition`，因此离线文件可以使用普通 `depends_on`，或分步启动。

启动后端和 MySQL（⭐⭐⭐）：

```bash
cd /opt/software/jushi
docker compose -f docker-compose.backend.offline.yml up -d
docker compose -f docker-compose.backend.offline.yml ps
```

如果担心 MySQL 未就绪，可以分步启动：

```bash
docker compose -f docker-compose.backend.offline.yml up -d jushi-mysql
sleep 30
docker compose -f docker-compose.backend.offline.yml up -d jushi-api
```



### 6. 创建前端离线 compose 文件（前端只需要改地址，不需要删除build）

```bash
cd /opt/software/jushiapi-ui-test
cp docker-compose.frontend.yml docker-compose.frontend.offline.yml
vi docker-compose.frontend.offline.yml
```

将 `jushi-frontend` 改为使用本地镜像，并删除 `build:` 块：

```yaml
services:
  jushi-frontend:
    image: jushiapi-ui-test-jushi-frontend:latest
    container_name: jushi-frontend
    ports:
      - "${FRONTEND_PORT:-18000}:80"
    networks:
      - jushi_backend
    restart: unless-stopped

networks:
  jushi_backend:
    external: true
    name: ${BACKEND_NETWORK:-jushi_default}
```

启动 Vue 前端（⭐⭐⭐）：

```bash
cd /opt/software/jushiapi-ui-test
BACKEND_NETWORK=jushi_default FRONTEND_PORT=18000 \
docker compose --env-file .env.example -f docker-compose.frontend.offline.yml up -d
```

检查：

```bash
docker ps -a | grep jushi
docker logs --tail=100 jushi-frontend
```



### 7. 离线方案验证

```bash
curl -I http://127.0.0.1:18000/
curl -i http://127.0.0.1:18000/api/system/health
curl -I http://127.0.0.1:18000/api/docs
```

登录：

```bash
curl -s -X POST http://127.0.0.1:18000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"bluedot@123"}'
```

离线方案的原则：

- r13 只执行 `docker load` 和 `docker compose up -d`。
- r13 不执行 `docker compose up -d --build`。
- 后端环境差异通过 `/opt/software/jushi/.env.example` 调整。
- 前端镜像构建时 `VITE_API_BASE_URL` 应保持空值，让前端同源访问 `/api`。



## 六、验证数据库初始化

```bash
docker exec -it jushi-mysql mysql -ujushi -pjushi_pass jushi
```

进入 MySQL 后执行：

```sql
SHOW TABLES;
SELECT id, username, role, status FROM sys_user;
SELECT COUNT(*) FROM deploy_instance;
SELECT COUNT(*) FROM port_block_rule;
```

如需修改默认登录账号：

```sql
UPDATE sys_user
SET username='客户管理员账号',
    password='客户初始密码',
    real_name='客户管理员',
    role='admin',
    status='active'
WHERE username='admin';
```

当前后端仍是明文密码阶段，`password` 字段需要填明文；正式交付前建议改为哈希存储。

## 七、启动 Vue 前端

前端使用 `jushiapi-ui-test`：

```bash
cd /opt/software/jushiapi-ui-test
```

确认 `.env.example`：

```env
VITE_API_BASE_URL=
VITE_ENABLE_MOCK=false
VITE_DEV_PROXY_TARGET=http://14.103.139.131:18000
```

生产构建时 `VITE_API_BASE_URL` 留空，表示浏览器同源访问 `/api`，由 Nginx 反代到 `jushi-api:8080`。

启动：

```bash
BACKEND_NETWORK=jushi_default FRONTEND_PORT=18000 docker compose --env-file .env.example -f docker-compose.frontend.yml up -d --build
```

检查：

```bash
docker ps -a | grep jushi
docker logs --tail=100 jushi-frontend
```

预期：

```text
jushi-mysql
jushi-api
jushi-frontend
```



## 八、接口验证

健康检查：

```bash
curl -I http://127.0.0.1:18000/
curl -i http://127.0.0.1:18000/api/system/health
curl -I http://127.0.0.1:18000/api/docs
```

登录：

```bash
curl -s -X POST http://127.0.0.1:18000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"bluedot@123"}'
```

如果已改客户账号，替换为客户账号和密码。

未登录业务接口应返回 `401`：

```bash
curl -i http://127.0.0.1:18000/api/users/list
```

带登录 token 验证：

```bash
curl -i http://127.0.0.1:18000/api/users/list \
  -H "Authorization: Bearer 登录token"
```

验证 DCE 链路：

```bash
curl -s -X POST http://127.0.0.1:18000/api/cluster \
  -H "Authorization: Bearer 登录token" \
  -H "Content-Type: application/json" \
  -d '{"msg_id":"cluster-001","serial":"cluster-serial-001","context":"query cluster","content":{}}'
```

验证资源预检：

```bash
curl -s -X POST http://127.0.0.1:18000/api/deploy/check-available \
  -H "Authorization: Bearer 登录token" \
  -H "Content-Type: application/json" \
  -d '{
    "msg_id":"check-001",
    "serial":"check-serial-001",
    "context":"check deploy available",
    "content":{
      "devices":{"NVIDIA/GPU":1},
      "deployType":"NvidiaInfer",
      "creator":"admin"
    }
  }'
```



## 九、部署创建前最终检查

创建真实 NVIDIA 实例前确认：

```bash
ls -lh /opt/mtworkflow_x86.zip
unzip -l /opt/mtworkflow_x86.zip | grep -E 'mtworkflow_x86/cfg/runmode.cfg|mtworkflow_x86/mtworkflow.sh'
nk images | grep '11.6.2-cudnn8-devel-ubuntu20.04_v1'
```

如果 Pod 可能调度到多台 GPU 节点，每台节点都需要具备同名镜像和 `/opt/mtworkflow_x86.zip`。

## 十、禁止操作

不要执行：

```bash
kill 老脚本 python3 进程
docker stop 老脚本相关容器
docker compose -f docker-compose.yml up -d
```

不要新增以下端口映射：

```yaml
8080:8080
3306:3306
8091:8091
```

否则可能影响老脚本或平台现有服务。

## 十一、回滚新版服务

如果新版服务需要停止，使用：

```bash
cd /opt/software/jushiapi-ui-test
docker compose -f docker-compose.frontend.yml down

cd /opt/software/jushi
docker compose -f docker-compose.backend.yml down
```

这只会停止新版 `jushi-frontend`、`jushi-api`、`jushi-mysql`，不会停止老脚本。

如需保留数据库数据，不要删除：

```text
/opt/software/jushi/mysql/data
```

