# BackQuant 量化回测平台

本仓库包含后端（Flask + RQAlpha）与前端（Vue 3）两部分，并提供 Research 工作台（Jupyter Lab）集成能力。
**推荐使用 Docker 安装部署**，一次性包含 Flask、Jupyter、Nginx 与前端构建产物。

## Docker 安装与部署（推荐）

### 安装 Docker（Ubuntu 示例）

如需在其他系统安装，请参考 Docker 官方文档（`https://docs.docker.com/engine/install/`）。

```bash
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world
docker compose version
```

### 启动

```bash
cp .env.example .env
docker compose up --build
```

### 访问

- 前端：`http://localhost:8080`

说明：后端 API 与 Jupyter 已通过同域路径反向代理（`/api`、`/jupyter`），一般无需单独访问端口。

## 目录结构

- `backtest/` 后端与回测服务
- `frontend/` 前端页面
- `docs/` 说明文档与示例 Notebook

## 本地开发

### 后端

```bash
cd backtest
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.wsgi.example .env.wsgi
python3 wsgi.py
```

默认端口：`54321`。

### 前端

```bash
cd frontend
npm install
npm run serve
```

默认端口：`8080`。

### Jupyter

Jupyter 安装与配置见 `docs/jupyter.md`。

## 配置说明

后端主要配置在 `backtest/.env.wsgi`：

- `SECRET_KEY` JWT 签名密钥，必须修改
- `LOCAL_AUTH_MOBILE` / `LOCAL_AUTH_PASSWORD` 本地登录账号密码
- `LOCAL_AUTH_PASSWORD_HASH` 可选，bcrypt hash 优先级高于明文密码
- `RESEARCH_NOTEBOOK_*` Jupyter 相关配置
  说明：Jupyter token 可不设置（空值表示不启用 token 鉴权，仅建议用于内网/本机）。

前端支持两种方式配置 API 基址：

- 构建时环境变量 `VUE_APP_API_BASE`
- 运行时 `frontend/public/config.js`（无需重新构建）

## 安全提示

- 不要提交 `.env.wsgi`、`.env` 等本地配置文件。
- `SECRET_KEY` 必须自行生成替换。
- 若使用 bcrypt 密码，可用以下命令生成：

```bash
python3 - <<'PY'
import bcrypt
print(bcrypt.hashpw(b"replace_with_strong_password", bcrypt.gensalt()).decode())
PY
```

## Jupyter 示例

- 示例 Notebook：`docs/notebooks/example.ipynb`
- 详细说明：`docs/jupyter.md`

## Nginx 反代说明

生产环境可参考 `docs/nginx.md`。

## API 文档

后端 API 说明见 `backtest/README.md`。

## 微信公众号

ETF量化老司机
