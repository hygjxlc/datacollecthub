FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY seed.py .

EXPOSE 8080

# 启动前幂等种子（首个 admin 账号），再起 uvicorn（架构 7.1 单实例，不横向多副本）
CMD ["sh", "-c", "python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8080"]
