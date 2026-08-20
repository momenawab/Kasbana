FROM python:3.12-alpine

WORKDIR /app
COPY requirements.txt ./
RUN apk add --no-cache --virtual .build-deps gcc python3-dev musl-dev linux-headers \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps
COPY stampn_ops_collector ./stampn_ops_collector
EXPOSE 9800
CMD ["uvicorn", "stampn_ops_collector.app:app", "--host", "0.0.0.0", "--port", "9800", "--no-access-log"]
