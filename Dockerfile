FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade -r ./requirements.txt

COPY . .

USER 10000

ENTRYPOINT [ "./secrets-entrypoint.sh" ]
