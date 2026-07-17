FROM python:3.12-alpine

RUN addgroup -S ops && adduser -S -G ops ops
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY stampn_ops_collector ./stampn_ops_collector
USER ops
EXPOSE 9800
CMD ["uvicorn", "stampn_ops_collector.app:app", "--host", "0.0.0.0", "--port", "9800", "--no-access-log"]
