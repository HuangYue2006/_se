FROM python:3.12-slim

WORKDIR /app

# 先複製 requirements 再安裝：只要依賴沒變，這層 cache 就能重複使用
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# 不用 root 執行
RUN useradd -m appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
