FROM python:3.12-slim

WORKDIR /app

# 如果服务器在国内，取消下面一行的注释以使用清华镜像加速
# RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY requirements.txt ./
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

COPY app.py ./
COPY db.py ./
COPY db_membership.py ./
COPY ai_insight.py ./
COPY scheduler.py ./
COPY middleware/ ./middleware/
COPY routes/ ./routes/

EXPOSE 3000

CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "4", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
