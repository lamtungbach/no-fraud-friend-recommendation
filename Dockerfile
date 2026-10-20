FROM python:3.11-slim

WORKDIR /app

# Cài đặt công cụ hệ thống tối thiểu
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt PyTorch CPU độc lập để tối ưu dung lượng (chỉ ~180MB thay vì kéo 2.5GB CUDA)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu

# Cài đặt các thư viện serving gọn nhẹ (bỏ qua JupyterLab, Notebook...)
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# Copy mã nguồn, weights, artifacts và hồ sơ tín nhiệm CSV
COPY src/ ./src/
COPY artifacts/ ./artifacts/
COPY weights/ ./weights/
COPY data/mgtab_user_trust_profiles_v2.csv ./data/mgtab_user_trust_profiles_v2.csv

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    API_ENVIRONMENT=development \
    TRUST_PROVIDER=csv \
    TRUST_PROFILES_PATH=/app/data/mgtab_user_trust_profiles_v2.csv

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
