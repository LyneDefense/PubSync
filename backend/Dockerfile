# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
ARG PIP_TRUSTED_HOST=mirrors.cloud.tencent.com

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}
ENV PIP_DEFAULT_TIMEOUT=120

WORKDIR /app

RUN sed -i \
        -e 's|http://deb.debian.org/debian|http://mirrors.cloud.tencent.com/debian|g' \
        -e 's|http://deb.debian.org/debian-security|http://mirrors.cloud.tencent.com/debian-security|g' \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Vendored SkillOpt(锁定源码、含 prompts):PyPI wheel 不打包 prompts,故 vendored 进仓库并以
# editable 方式安装——保留源码树(prompts 可被 load_prompt 解析),并自动拉取其轻量依赖。
COPY vendor ./vendor
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e ./vendor/skillopt

COPY app ./app
# Alembic 配置与迁移脚本（放在 app/ 之外），打包进镜像以便容器内运行
# `alembic upgrade head`。应用启动仍由 ensure_runtime_schema 兜底建表，此处仅为可用性。
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
