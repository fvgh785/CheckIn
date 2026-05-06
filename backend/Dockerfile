FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY db.py ./
COPY middleware/ ./middleware/
COPY routes/ ./routes/

EXPOSE 3000

CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "4", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
