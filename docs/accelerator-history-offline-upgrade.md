# 节点单卡历史离线升级说明

## 1. 适用范围

本说明适用于已经存在 `jushi-mysql` 数据目录的上海环境和客户离线环境。本次升级：

- 不接入 VictoriaMetrics；
- 不增加长期运行的容器；
- 更新现有 `jushi-api` 和当前 Vue 前端镜像；
- 在现有 `jushi` 数据库中新建 `accelerator_metric_sample`；
- 由 `jushi-api` 每 60 秒从现有 Prometheus 采集物理卡显存指标；
- 1h、24h、7d 单卡趋势统一从 MySQL 分桶查询。

`backend/db/init.sql` 只服务全新数据库。已有 `mysql/data` 时必须显式执行迁移文件。

## 2. 离线包内容

交付包至少包含：

```text
backend/db/migrations/20260723_001_create_accelerator_metric_sample.sql
scripts/apply-accelerator-history-migration.sh
更新后的 jushi-api 镜像
更新后的当前 Vue 前端镜像
```

不需要新增 MySQL、Prometheus 或指标采集器镜像。

## 3. 升级前备份

在部署目录创建备份目录：

```bash
mkdir -p backup
```

使用 MySQL 容器已有环境变量进行备份，避免把密码写入命令：

```bash
docker exec jushi-mysql sh -c '
  export MYSQL_PWD="$MYSQL_PASSWORD"
  exec mysqldump \
    --single-transaction \
    --routines \
    --triggers \
    -u"$MYSQL_USER" \
    "$MYSQL_DATABASE"
' > backup/jushi-before-accelerator-history.sql
```

确认备份文件存在且不是空文件：

```bash
ls -lh backup/jushi-before-accelerator-history.sql
```

## 4. 执行建表迁移

推荐直接运行随离线包提供的脚本：

```bash
sh scripts/apply-accelerator-history-migration.sh
```

脚本只执行幂等的 `CREATE TABLE IF NOT EXISTS`，不会修改旧表和旧数据，也不依赖 `jq`。

也可以人工执行：

```bash
docker cp \
  backend/db/migrations/20260723_001_create_accelerator_metric_sample.sql \
  jushi-mysql:/tmp/create_accelerator_metric_sample.sql

docker exec -it jushi-mysql mysql -u jushi -p -D jushi
```

进入 MySQL 后执行：

```sql
SOURCE /tmp/create_accelerator_metric_sample.sql;
SHOW TABLES LIKE 'accelerator_metric_sample';
SHOW CREATE TABLE accelerator_metric_sample\G
```

如果应用数据库账号没有 `CREATE` 权限，应由客户数据库管理员执行迁移；不要为了升级长期扩大应用账号权限。

## 5. 环境变量

在 `jushi-api` 使用的环境文件中增加：

```env
ACCELERATOR_HISTORY_ENABLED=true
ACCELERATOR_HISTORY_INTERVAL_SECONDS=60
ACCELERATOR_HISTORY_RETENTION_DAYS=14
ACCELERATOR_HISTORY_BACKFILL_SECONDS=5400
ACCELERATOR_HISTORY_CLUSTER_NAME=default
```

继续保留现有 `PROMETHEUS_BASE_URL`、`PROMETHEUS_TOKEN`、`PROMETHEUS_TIMEOUT_SECONDS` 和 `PROMETHEUS_GPU_USAGE_ENABLED`。

## 6. 镜像升级

按现有离线流程导入并替换 `jushi-api` 和当前 Vue 前端镜像，然后只重新创建对应服务。容器数量不变。

启动后检查：

```bash
docker logs --tail 100 jushi-api
```

正常日志应包含：

```text
[Jushi] Accelerator history collector: started
[Jushi] Accelerator history: collection completed
```

## 7. 数据验证

运行两到三分钟后执行：

```bash
docker exec jushi-mysql sh -c '
  export MYSQL_PWD="$MYSQL_PASSWORD"
  exec mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -e "
    SELECT
      node_name,
      vendor,
      COUNT(DISTINCT card_id) AS card_count,
      COUNT(*) AS sample_count,
      MIN(sampled_at) AS first_sample,
      MAX(sampled_at) AS last_sample
    FROM accelerator_metric_sample
    GROUP BY node_name, vendor
    ORDER BY node_name, vendor;
  "
'
```

如果节点有 6 张卡，每分钟正常增加约 6 条记录。没有指标的周期不会写成 0。

## 8. 数据覆盖说明

首次启动会尝试从 Prometheus 补采最近 90 分钟。能够补回多少取决于现场 Prometheus 的实际保留时间。

- 不能恢复的时间区间返回空桶；
- 空桶在前端显示为断线，不补 0；
- 24h 和 7d 会从升级时间开始逐步积累；
- 采集记录默认保留 14 天。

## 9. 回滚

应用回滚只需要恢复旧版 `jushi-api`、旧版前端和原环境配置。旧版本不会读取新表，因此不需要删除 `accelerator_metric_sample`。

保留新表能够避免已采集历史丢失。除非已经备份并明确废弃该功能，否则回滚时不要执行 `DROP TABLE`。
