# 跨架构离线镜像打包与部署问题记录

> 适用场景：在 **x86/amd64 源服务器** 上打包 Docker 镜像，部署到 **ARM64/aarch64 目标服务器**。  
> 本次项目：聚时服务离线部署。  
> 源服务器：x86/amd64。  
> 目标服务器：ARM64/aarch64。  
> 最终目标镜像：
>
> - `jushiapi-ui-test-jushi-frontend:latest`
> - `jushi-jushi-api:latest`
> - `mysql:8.0`

---

## 1. 本次问题总览

本次遇到的问题本质上不是普通的 Docker 打包问题，而是 **跨 CPU 架构打包与导入问题**。

源服务器是 x86 架构，如果直接执行：

```bash
docker save -o jushi-offline-images.tar \
  jushiapi-ui-test-jushi-frontend:latest \
  jushi-jushi-api:latest \
  mysql:8.0
```

很容易把 x86/amd64 镜像打进离线包。该离线包传到 ARM64 服务器后，即使能 `docker load`，后续也可能无法正常运行，或者在加载时出现 manifest、layer、rootfs 相关错误。

本次最终处理思路是：

```text
在 x86 源服务器上使用 buildx + qemu/binfmt 交叉构建 ARM64 镜像
然后明确按 linux/arm64 平台导出离线包
最后在 ARM64 目标服务器导入并验证镜像平台
```

---



## 2. 架构确认



### 2.1 在目标服务器确认架构

目标服务器执行：

```bash
uname -m
docker info | grep -i architecture
```

如果看到：

```text
aarch64
Architecture: aarch64
```

说明目标服务器是 ARM64 架构。

常见架构对应关系：


| 显示值       | Docker 平台名    | 说明              |
| --------- | ------------- | --------------- |
| `x86_64`  | `linux/amd64` | Intel / AMD 服务器 |
| `amd64`   | `linux/amd64` | Docker 常用写法     |
| `aarch64` | `linux/arm64` | ARM64 服务器       |
| `arm64`   | `linux/arm64` | Docker 常用写法     |


---



## 3. 本次遇到的典型问题与原因



### 3.1 离线包传输不完整

现象：

```bash
gunzip -f jushi-offline-images.tar.gz
```

报错：

```text
gzip: jushi-offline-images.tar.gz: unexpected end of file
```

原因：目标服务器上的 `.tar.gz` 文件传输中断或大小不完整。

排查方式：

```bash
ls -lh jushi-offline-images.tar.gz
sha256sum jushi-offline-images.tar.gz
gzip -t jushi-offline-images.tar.gz
```

源服务器和目标服务器的 `sha256sum` 必须一致。

---



### 3.2 OCI 目录重新打 tar 后 `docker load` 失败

现象：

```bash
docker load -i jushi-offline-images.tar
```

报错类似：

```text
content digest sha256:213bbfaf...: not found
```

原因：解压后的目录是 OCI layout 结构：

```text
blobs/
index.json
manifest.json
oci-layout
```

该结构中 `index.json` 声明了某些架构的 digest，但实际 `blobs/sha256/` 里缺少对应文件，导致 `docker load` 失败。

注意：这不是简单的“x86 镜像不能导入 ARM”，而是 **OCI 索引引用的内容缺失**。

处理方式：不要手动重新 tar 这种不完整 OCI 目录，而是回到源服务器重新按正确架构 `docker save`。

---



### 3.3 `docker buildx inspect --bootstrap` 第一次超时

现象：

```bash
docker buildx inspect --bootstrap
```

报错：

```text
context deadline exceeded
```

但随后检查：

```bash
docker buildx ls
docker ps -a | grep buildx
docker logs --tail=100 buildx_buildkit_arm64-builder0
```

发现：

```text
arm64-builder running
Platforms: linux/amd64, linux/arm64, linux/386
```

原因：BuildKit 容器刚拉取并启动时，Docker 读取容器状态超时。

处理方式：等 1 分钟后重新执行：

```bash
docker buildx inspect arm64-builder --bootstrap
```

只要看到：

```text
Status: running
Platforms: linux/amd64, linux/arm64
```

就说明 buildx 初始化成功。

---



### 3.4 前端镜像查不到

误区：使用了：

```bash
docker ps
```

`docker ps` 只能查看正在运行的容器，不能查看所有镜像。

正确查看镜像：

```bash
docker images | grep -E 'jushi|mysql'
```

或者：

```bash
docker image ls | grep jushiapi-ui-test-jushi-frontend
```

查看镜像架构：

```bash
docker image inspect jushiapi-ui-test-jushi-frontend:latest \
  --format '{{.Architecture}} {{.Os}}'
```

本次前端目录不是 `/opt/software/jushi/ui`，而是：

```text
/opt/software/jushiapi-ui-test
```

前端构建命令应在该目录执行。

---



### 3.5 后端构建报 `Dockerfile` 不存在

错误命令：

```bash
cd /opt/software/jushi

docker buildx build \
  --platform linux/arm64 \
  -t jushi-jushi-api:latest \
  --load \
  .
```

报错：

```text
failed to read dockerfile: open Dockerfile: no such file or directory
```

原因：`/opt/software/jushi` 根目录下没有 `Dockerfile`。

根据 `docker-compose.yml`：

```yaml
jushi-api:
  build:
    context: ./backend
```

说明后端 Dockerfile 在：

```text
/opt/software/jushi/backend/Dockerfile
```

正确构建方式：

```bash
cd /opt/software/jushi

docker buildx build \
  --builder arm64-builder \
  --platform linux/arm64 \
  -t jushi-jushi-api:latest \
  --load \
  -f backend/Dockerfile \
  ./backend
```

---



### 3.6 MySQL 明明指定 ARM64 拉取，但普通 inspect 还是显示 amd64

执行：

```bash
docker pull --platform linux/arm64/v8 mysql:8.0
```

普通 inspect：

```bash
docker image inspect mysql:8.0 \
  --format 'ARCH={{.Architecture}} OS={{.Os}}'
```

可能仍显示：

```text
ARCH=amd64 OS=linux
```

原因：在 x86 源服务器上，同一个 tag 可能同时缓存多平台镜像，普通 inspect 可能默认显示本机平台 amd64。

正确检查 ARM64 版本：

```bash
docker image inspect --platform linux/arm64/v8 mysql:8.0 \
  --format 'MYSQL_ARM64: TAGS={{.RepoTags}} ARCH={{.Architecture}} OS={{.Os}} ID={{.Id}}'
```

本次成功结果：

```text
MYSQL_ARM64: TAGS=[mysql:8.0] ARCH=arm64 OS=linux ID=sha256:213bbfaf...
```

最终打包时也必须加：

```bash
--platform linux/arm64
```

---



### 3.7 目标 ARM 服务器上 `docker image inspect --format` 报错

现象：

```bash
docker image inspect \
  --format 'FRONTEND: TAGS={{.RepoTags}} ARCH={{.Architecture}} OS={{.Os}} ID={{.Id}}' \
  jushiapi-ui-test-jushi-frontend:latest
```

报错：

```text
invalid reference format: repository name ... must be lowercase
```

原因：目标环境中的 Docker CLI 解析 `--format` 的行为和标准 Docker CLI 不完全一致，可能把 `TAGS={{.RepoTags}}`、`ARCH={{.Architecture}}` 等内容误认为镜像名。

替代方式：

```bash
docker images | grep -E 'jushi|mysql'
```

本次目标服务器 `docker images` 已经显示三张镜像均为：

```text
linux/arm64
```

说明导入成功。

如果仍想用 inspect，可尝试无空格写法：

```bash
docker image inspect --format='{{.Architecture}}/{{.Os}}' mysql:8.0
```

---



### 3.8 `docker load` 最后报 `mismatched image rootfs and manifest layers`

现象：

```text
Loaded image: jushiapi-ui-test-jushi-frontend:latest
Loaded image: jushi-jushi-api:latest
Loaded image: mysql:8.0
FATA[0016] error unpacking image (overlayfs@sha256:...): mismatched image rootfs and manifest layers
```

判断：三张主镜像已经加载成功，最后失败的是异常的 `overlayfs@sha256...` 元数据项。

先检查主镜像：

```bash
docker images | grep -E 'jushi|mysql'
```

如果三张主镜像都显示：

```text
linux/arm64
```

则可以先启动验证。

更稳的长期方案：在源服务器分开导出三张镜像，目标服务器分别导入，避免一个异常元数据影响整个 tar。

---



## 4. 正确完整流程



## 4.1 在 x86 源服务器初始化 buildx

```bash
docker buildx version

docker run --privileged --rm tonistiigi/binfmt --install arm64

docker buildx create --name arm64-builder --use 2>/dev/null || docker buildx use arm64-builder

docker buildx inspect --bootstrap

docker buildx ls
```

成功标志：

```text
installing: arm64 OK
Platforms: linux/amd64, linux/arm64, linux/386
```

如果 `moby/buildkit:buildx-stable-1` 拉取慢，可以先等几分钟。若超过 10～15 分钟无变化，可改用镜像源。

---



## 4.2 构建前端 ARM64 镜像

前端目录：

```text
/opt/software/jushiapi-ui-test
```

构建：

```bash
cd /opt/software/jushiapi-ui-test

docker buildx build \
  --builder arm64-builder \
  --platform linux/arm64 \
  -t jushiapi-ui-test-jushi-frontend:latest \
  --load \
  .
```

验证：

```bash
docker image inspect jushiapi-ui-test-jushi-frontend:latest \
  --format '{{.RepoTags}} {{.Architecture}} {{.Os}}'
```

应输出：

```text
[jushiapi-ui-test-jushi-frontend:latest] arm64 linux
```

---



## 4.3 构建后端 ARM64 镜像

后端目录：

```text
/opt/software/jushi/backend
```

构建：

```bash
cd /opt/software/jushi

docker buildx build \
  --builder arm64-builder \
  --platform linux/arm64 \
  -t jushi-jushi-api:latest \
  --load \
  -f backend/Dockerfile \
  ./backend
```

验证：

```bash
docker image inspect jushi-jushi-api:latest \
  --format '{{.RepoTags}} {{.Architecture}} {{.Os}}'
```

应输出：

```text
[jushi-jushi-api:latest] arm64 linux
```

---



## 4.4 拉取并确认 ARM64 MySQL

拉取：

```bash
docker pull --platform linux/arm64/v8 mysql:8.0
```

确认 ARM64 版本：

```bash
docker image inspect --platform linux/arm64/v8 mysql:8.0 \
  --format 'MYSQL_ARM64: TAGS={{.RepoTags}} ARCH={{.Architecture}} OS={{.Os}} ID={{.Id}}'
```

应输出：

```text
ARCH=arm64 OS=linux
```

注意：在 x86 源服务器上，普通 inspect 可能仍显示 amd64，因此 MySQL 必须使用带 `--platform` 的 inspect 来确认。

---



## 4.5 最终打包前检查

```bash
docker image inspect jushiapi-ui-test-jushi-frontend:latest \
  --format 'FRONTEND={{.Architecture}}/{{.Os}}'

docker image inspect jushi-jushi-api:latest \
  --format 'API={{.Architecture}}/{{.Os}}'

docker image inspect --platform linux/arm64/v8 mysql:8.0 \
  --format 'MYSQL={{.Architecture}}/{{.Os}}'
```

三项都应该是：

```text
arm64/linux
```

---



## 4.6 生成单个 ARM64 离线包

```bash
mkdir -p /opt/software/offline-images

rm -f /opt/software/offline-images/jushi-offline-images.tar
rm -f /opt/software/offline-images/jushi-offline-images.tar.gz

docker save --platform linux/arm64 -o /opt/software/offline-images/jushi-offline-images.tar \
  jushiapi-ui-test-jushi-frontend:latest \
  jushi-jushi-api:latest \
  mysql:8.0

gzip -f /opt/software/offline-images/jushi-offline-images.tar

ls -lh /opt/software/offline-images/jushi-offline-images.tar.gz
sha256sum /opt/software/offline-images/jushi-offline-images.tar.gz
gzip -t /opt/software/offline-images/jushi-offline-images.tar.gz
```

`gzip -t` 没有输出即为正常。

---



## 4.7 更稳方案：分开导出三张镜像

如果单个大包导入时出现 `overlayfs` 或 manifest/layer 异常，推荐分开打包。

源服务器执行：

```bash
mkdir -p /opt/software/offline-images/split-arm64
cd /opt/software/offline-images/split-arm64

rm -f *.tar *.tar.gz

docker save --platform linux/arm64 \
  -o jushi-frontend-arm64.tar \
  jushiapi-ui-test-jushi-frontend:latest

docker save --platform linux/arm64 \
  -o jushi-api-arm64.tar \
  jushi-jushi-api:latest

docker save --platform linux/arm64 \
  -o mysql-8-arm64.tar \
  mysql:8.0

gzip -f jushi-frontend-arm64.tar
gzip -f jushi-api-arm64.tar
gzip -f mysql-8-arm64.tar

ls -lh
sha256sum *.tar.gz

gzip -t jushi-frontend-arm64.tar.gz
gzip -t jushi-api-arm64.tar.gz
gzip -t mysql-8-arm64.tar.gz
```

目标服务器分别导入：

```bash
cd /opt/software

gunzip -f jushi-frontend-arm64.tar.gz
docker load -i jushi-frontend-arm64.tar

gunzip -f jushi-api-arm64.tar.gz
docker load -i jushi-api-arm64.tar

gunzip -f mysql-8-arm64.tar.gz
docker load -i mysql-8-arm64.tar
```

---



## 5. 目标 ARM 服务器导入流程

---



### 5.2 解压并加载

```bash
cd /opt/software

gunzip -f jushi-offline-images.tar.gz

docker load -i jushi-offline-images.tar
```

如果出现：

```text
Loaded image: jushiapi-ui-test-jushi-frontend:latest
Loaded image: jushi-jushi-api:latest
Loaded image: mysql:8.0
```

说明三张主镜像已加载。

---



### 5.3 检查镜像平台

目标服务器如果 `docker images` 带 `PLATFORM` 列，直接执行：

```bash
docker images | grep -E 'jushi|mysql'
```

期望结果：

```text
mysql                         8.0       ...   linux/arm64
jushi-jushi-api               latest    ...   linux/arm64
jushiapi-ui-test-jushi-frontend latest  ...   linux/arm64
```

如果标准 Docker CLI 可用，也可以执行：

```bash
docker image inspect --format='{{.Architecture}}/{{.Os}}' mysql:8.0
docker image inspect --format='{{.Architecture}}/{{.Os}}' jushi-jushi-api:latest
docker image inspect --format='{{.Architecture}}/{{.Os}}' jushiapi-ui-test-jushi-frontend:latest
```

期望：

```text
arm64/linux
```

---



## 6. 目标服务器启动验证

如果目标服务器已有源码目录：

```text
/opt/software/jushi
```

进入目录：

```bash
cd /opt/software/jushi
```

使用 compose 启动：

```bash
docker compose up -d --no-build
```

检查容器：

```bash
docker ps | grep jushi
```

查看日志：

```bash
docker logs --tail=100 jushi-mysql
docker logs --tail=100 jushi-api
docker logs --tail=100 jushi-frontend
```

---



## 7. 关于是否可以使用相同 tag

本次源服务器只是离线打包机，不用于开发测试，因此可以继续使用原来的 tag：

```text
jushiapi-ui-test-jushi-frontend:latest
jushi-jushi-api:latest
mysql:8.0
```

这样导入目标服务器后，不需要额外改 compose 的镜像名。

但要注意：

- 如果源服务器还要继续运行 x86 服务，不建议用同一个 `latest` tag。
- 如果只是打包机，同 tag 没问题。
- 打包前必须确认 tag 对应的是 ARM64 镜像。
- MySQL 多架构镜像必须在 `docker save` 时显式指定：

```bash
docker save --platform linux/arm64 ...
```

---



## 8. 最终推荐命令汇总



### 8.1 源服务器完整构建与打包

```bash
# 初始化 buildx

docker run --privileged --rm tonistiigi/binfmt --install arm64

docker buildx create --name arm64-builder --use 2>/dev/null || docker buildx use arm64-builder

docker buildx inspect --bootstrap

# 构建前端

cd /opt/software/jushiapi-ui-test

docker buildx build \
  --builder arm64-builder \
  --platform linux/arm64 \
  -t jushiapi-ui-test-jushi-frontend:latest \
  --load \
  .

# 构建后端

cd /opt/software/jushi

docker buildx build \
  --builder arm64-builder \
  --platform linux/arm64 \
  -t jushi-jushi-api:latest \
  --load \
  -f backend/Dockerfile \
  ./backend

# 拉取 ARM64 MySQL

docker pull --platform linux/arm64/v8 mysql:8.0

# 架构检查

docker image inspect jushiapi-ui-test-jushi-frontend:latest \
  --format 'FRONTEND={{.Architecture}}/{{.Os}}'

docker image inspect jushi-jushi-api:latest \
  --format 'API={{.Architecture}}/{{.Os}}'

docker image inspect --platform linux/arm64/v8 mysql:8.0 \
  --format 'MYSQL={{.Architecture}}/{{.Os}}'

# 打包

mkdir -p /opt/software/offline-images

rm -f /opt/software/offline-images/jushi-offline-images.tar
rm -f /opt/software/offline-images/jushi-offline-images.tar.gz

docker save --platform linux/arm64 -o /opt/software/offline-images/jushi-offline-images.tar \
  jushiapi-ui-test-jushi-frontend:latest \
  jushi-jushi-api:latest \
  mysql:8.0

gzip -f /opt/software/offline-images/jushi-offline-images.tar

ls -lh /opt/software/offline-images/jushi-offline-images.tar.gz
sha256sum /opt/software/offline-images/jushi-offline-images.tar.gz
gzip -t /opt/software/offline-images/jushi-offline-images.tar.gz
```

---



### 8.2 目标服务器导入与验证

```bash
cd /opt/software

gunzip -f jushi-offline-images.tar.gz

docker load -i jushi-offline-images.tar

docker images | grep -E 'jushi|mysql'

cd /opt/software/jushi

docker compose up -d --no-build

docker ps | grep jushi

docker logs --tail=100 jushi-mysql
docker logs --tail=100 jushi-api
docker logs --tail=100 jushi-frontend
```

---



## 9. 快速判断标准


| 检查项                               | 正常结果                  |
| --------------------------------- | --------------------- |
| 目标机 `uname -m`                    | `aarch64`             |
| buildx platforms                  | 包含 `linux/arm64`      |
| 前端镜像                              | `arm64 linux`         |
| 后端镜像                              | `arm64 linux`         |
| MySQL inspect with platform       | `ARCH=arm64 OS=linux` |
| `gzip -t`                         | 无输出                   |
| 目标机 `docker images`               | 三张镜像均为 `linux/arm64`  |
| `docker compose up -d --no-build` | 三个容器正常启动              |


---



## 10. 关键经验总结

1. x86 源服务器直接 `docker save`，默认很可能打出 x86 镜像。
2. 跨架构必须使用 `buildx` 构建 ARM64 镜像。
3. `docker ps` 看的是容器，`docker images` 才看镜像。
4. 后端不能在项目根目录直接 build，要按 compose 中的 `context: ./backend` 构建。
5. MySQL 是多架构镜像，普通 inspect 在 x86 上可能显示 amd64，必须用 `--platform linux/arm64/v8` 检查。
6. 最终 `docker save` 建议加 `--platform linux/arm64`。
7. 目标服务器如果 `docker load` 最后报 `overlayfs` 异常，但三张主镜像已经 `Loaded image` 并显示 `linux/arm64`，可以先启动验证。
8. 如果大包反复异常，改成三张镜像分开 save/load，最稳。
9. 只作为离线打包机时，可以继续使用相同 `latest` tag；如果源服务器还要运行 x86 服务，则建议使用 `:arm64` 独立 tag。

