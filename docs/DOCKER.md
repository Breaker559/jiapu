# 家谱 Docker 部署

家谱使用一个镜像提供网页和 API，容器内部监听 `8765`。需要 Docker Engine / Docker Desktop 的 Linux 容器，以及 Docker Compose v2.20+。初次构建需要联网下载基础镜像和依赖；运行时前端资源均由应用提供。

## SQLite：单容器部署

在包含 Dockerfile 的项目目录执行：

```sh
docker compose -f compose.sqlite.yaml up -d --build --wait
docker compose -f compose.sqlite.yaml ps
```

等待 `app` 健康后打开 http://127.0.0.1:8765。首次进入由站点所有者创建管理员，没有默认账号密码。之后登录页提供“注册账号”，新用户可以创建独立家族。直接部署无需 `.env`，也无需独立数据库。

开放注册默认开启。站点管理员登录后进入左侧“站点管理”（`/#admin`），可查看全站注册账号、搜索姓名/邮箱、筛选角色、分页查看注册与最近登录时间及所属家族，并即时开关公开注册。开关保存到数据库，容器重启和重建后保留；升级前未记录过的账号时间显示为“未记录”。

在 `.env` 设置 `QINPU_ALLOW_REGISTRATION=0` 并重新启动 Compose 服务可从部署层关闭注册入口与注册 API，保留邀请码加入；后台不能覆盖此关闭设置，需要先将环境变量改为 `1` 并重新创建服务。普通注册账号不是站点管理员，不会读取已有家族资料，也不能访问站点后台。注册和登录有基本频率限制；邮箱目前用作登录名，不发送验证或找回邮件，用户需保存恢复码。登录后点击右上角头像菜单，可查看账号、修改密码或退出登录；左下角提供“使用帮助”。

项目名固定为 `jiapu`，中文路径可直接使用；默认命名卷为 `jiapu_family_data`。数据库、照片和相关数据均挂载在 `/app/data`。应用以 UID `10001` 的非 root 用户运行，新命名卷会沿用镜像中的目录权限。容器使用单个 API 进程，请保持单副本，不要增加 Uvicorn workers。

## 局域网 / NAS

复制 `.env.example` 为 `.env`，按实际机器地址修改，例如：

```dotenv
QINPU_BIND_ADDRESS=0.0.0.0
QINPU_PORT=8765
QINPU_ALLOWED_HOSTS=192.168.1.20
QINPU_ORIGINS=http://192.168.1.20:8765
QINPU_SECURE_COOKIE=0
```

再次执行启动命令，访问 http://192.168.1.20:8765。端口被占用时修改 `QINPU_PORT`，并同步修改 `QINPU_ORIGINS` 中的端口。多个域名/IP 使用逗号分隔，`QINPU_ALLOWED_HOSTS` 不包含协议或端口。

默认只绑定 `127.0.0.1`，供本机访问；远程服务器也可用 SSH 隧道：`ssh -L 8765:127.0.0.1:8765 user@server`。局域网部署需确保宿主机防火墙允许配置的端口。

## 域名和 HTTPS

在 Nginx / Caddy 中把域名反向代理到 `http://127.0.0.1:8765`。若代理也在容器中，应将两个服务连接到同一 Docker 网络，并代理到 `http://app:8765`，容器内的 `127.0.0.1` 不能指向另一个容器。

`.env` 示例：

```dotenv
QINPU_BIND_ADDRESS=127.0.0.1
QINPU_PORT=8765
QINPU_ALLOWED_HOSTS=family.example.com
QINPU_ORIGINS=https://family.example.com
QINPU_SECURE_COOKIE=1
QINPU_TRUSTED_PROXIES=172.30.0.0/24
```

`family.example.com` 和 `172.30.0.0/24` 均需替换为实际域名和代理的来源 IP / 容器网络。仅信任真实代理，避免对可直接访问的应用端口设置 `*`。代理需转发原始 `Host`、`X-Forwarded-For`、`X-Forwarded-Proto`。Nginx 的上传限制应设置为至少 `260m`，超时应覆盖照片上传和加密备份操作。宿主机 Caddy 最小配置如下：

```caddyfile
family.example.com {
    reverse_proxy 127.0.0.1:8765
}
```

开启安全 Cookie 后应始终通过 HTTPS 域名登录；在纯 HTTP 页面登录时浏览器不会发送安全 Cookie。健康检查保留本机访问，不受自定义域名影响。

## PostgreSQL：独立数据库部署

此方案使用原有 `compose.yaml`，包括应用和 PostgreSQL 16。先复制 `.env.example` 为 `.env`，填写随机 `QINPU_DB_PASSWORD`；可用下面的命令生成 URL 安全的随机密码，写入 `.env`：

```sh
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32))"
docker compose up -d --build --wait
docker compose ps
```

空密码会使 Compose 明确报错。默认项目名为 `jiapu-postgres`，数据卷为 `jiapu-postgres_database`（数据库）和 `jiapu-postgres_media`（照片）；数据库端口不发布到宿主机。

已有部署升级时使用 `docker compose -p 原项目名 up -d --build --wait`，原项目名可从 `docker compose ls` 查看。不要因为产品改名而更换项目名，否则会创建新的空数据卷。已初始化数据库的密码保存在数据库中，单改 `.env` 不会修改数据库密码。

SQLite 和 PostgreSQL 是两个独立实例。两者都默认使用宿主机 `8765`，同时运行时需为其中一个设置不同的 `QINPU_PORT`。需要迁移家族时，通过页面导出 `.qinpu` 加密家族包再导入目标实例；不会直接复制 SQLite 文件到 PostgreSQL。

## 更新、停止和查看日志

以下为 SQLite 命令；PostgreSQL 方案去掉 `-f compose.sqlite.yaml`：

```sh
docker compose -f compose.sqlite.yaml logs --tail=100 -f app
docker compose -f compose.sqlite.yaml stop
docker compose -f compose.sqlite.yaml start
# 更新项目文件后重新构建、启动，命名卷会继续复用。
docker compose -f compose.sqlite.yaml up -d --build --wait
# 移除容器和网络，保留资料卷。
docker compose -f compose.sqlite.yaml down
```

`down -v` 会删除命名卷中的数据库和照片，不用于日常停止或升级。更换部署目录时保持项目名不变；升级前先备份。家族包保存某个家族的资料和照片，完整实例备份还包含账号、会话及其他家族。

## 完整实例备份与恢复

以下二进制重定向示例在 Linux / NAS shell 中执行。不要使用 Windows PowerShell 5 的 `>` 重定向备份二进制流；Windows 用户可在 WSL 中执行，或从网页导出家族加密包。

SQLite：先停止应用写入，再导出完整数据卷，成功后启动应用：

```sh
mkdir -p backups
docker compose -f compose.sqlite.yaml stop app
docker compose -f compose.sqlite.yaml run --rm --no-deps -T --entrypoint tar app -C /app/data -czf - . > backups/jiapu-data.tar.gz
docker compose -f compose.sqlite.yaml start app
```

恢复到**全新的项目名** `jiapu-restored`，使用空卷避免混入旧数据库的 WAL 文件。先停止原实例以释放端口，然后执行：

```sh
docker compose -p jiapu-restored -f compose.sqlite.yaml build app
docker compose -p jiapu-restored -f compose.sqlite.yaml run --rm --no-deps -T --entrypoint tar app -C /app/data -xzf - < backups/jiapu-data.tar.gz
docker compose -p jiapu-restored -f compose.sqlite.yaml up -d --wait
```

恢复后用原账号登录，检查人物和照片；后续命令继续带 `-p jiapu-restored`。命名卷使用 UID `10001`，解包也以同一用户执行。应用自身最多保存 30 步的排版撤销记录，图谱位置属于浏览器偏好，不进入服务器备份。

PostgreSQL：停止应用但保持数据库运行，同时备份数据库和照片卷：

```sh
mkdir -p backups
docker compose stop app
docker compose exec -T db pg_dump -U qinpu -d qinpu -Fc > backups/jiapu-database.dump
docker compose run --rm --no-deps -T --entrypoint tar app -C /app/data -czf - . > backups/jiapu-media.tar.gz
docker compose start app
```

恢复到全新的 `jiapu-pg-restored` 项目，先确保原实例已停止、`.env` 的数据库密码已设置：

```sh
docker compose -p jiapu-pg-restored build app
docker compose -p jiapu-pg-restored up -d --wait db
docker compose -p jiapu-pg-restored exec -T db pg_restore --no-owner --no-privileges -U qinpu -d qinpu < backups/jiapu-database.dump
docker compose -p jiapu-pg-restored run --rm --no-deps -T --entrypoint tar app -C /app/data -xzf - < backups/jiapu-media.tar.gz
docker compose -p jiapu-pg-restored up -d --wait
```

备份恢复命令均需逐条确认成功；备份结束后把文件保存到另一台设备或磁盘。PostgreSQL dump 与照片卷必须来自同一轮停止应用后的备份。

## 验收与排错

```sh
# 配置解析；该命令可能显示密码，勿公开其输出。
docker compose -f compose.sqlite.yaml config --quiet
docker compose config --quiet
# 运行状态及健康检查。
docker compose -f compose.sqlite.yaml ps
curl --fail http://127.0.0.1:8765/api/health
```

有 Docker 和 Python 的机器可运行 `python scripts/qa_docker.py --backend sqlite`，或 `--backend postgres`。脚本使用独立随机项目名、临时端口和随机账号，验证构建、初始化、人物与照片、容器重建持久化，再删除自己创建的测试容器和数据卷；不操作正常部署。容器创建的数据不复制进源代码目录。

- `Invalid host header`：把访问使用的 IP / 域名加入 `QINPU_ALLOWED_HOSTS` 后重新 `up -d`。
- `请求来源不被允许`：核对 `QINPU_ORIGINS` 的协议、域名和对外端口，以及代理转发的 Host。
- 登录后仍提示未登录：纯 HTTP 下将 `QINPU_SECURE_COOKIE=0`；HTTPS 下检查代理配置。
- 数据目录无权限：优先使用配置中的命名卷；自定义宿主目录绑定时，其部署数据目录需允许 UID `10001` 读写。
- 数据看似消失：检查当前项目名和卷是否与原部署一致，再检查使用的是 SQLite 还是 PostgreSQL。

当前开发机没有 Docker 引擎。已进行应用构建、后端测试和配置静态校验；Linux 镜像构建、数据库服务、卷重建持久化需在 Docker 主机运行以上脚本确认。
