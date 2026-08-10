# Paddy 量化工作台 - Streamlit 运行镜像
FROM python:3.11-slim

# 环境变量: 关闭 Streamlit 自动开浏览器, 输出不缓冲
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

# 先仅复制依赖清单并安装, 利用 Docker 层缓存 (源码改动不触发重装)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码 (data/ 与本地生成的产物已在 .dockerignore 排除)
COPY . .

# 运行时数据目录 (关注列表 / 价格预警), 交由非 root 用户写入
RUN mkdir -p /app/data && \
    useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

# Streamlit 默认端口
EXPOSE 8501

# 健康检查: 命中 Streamlit 内置 health 端点
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8501/_stcore/health'); sys.exit(0)" || exit 1

ENTRYPOINT ["streamlit", "run", "dashboard.py", \
            "--server.port=8501", "--server.address=0.0.0.0", \
            "--server.headless=true"]
