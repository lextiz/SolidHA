FROM python:3.11-alpine

WORKDIR /app
RUN apk add --no-cache jq

COPY agent /app/agent
COPY addons/ha-llm-ops/run.sh /run.sh
COPY pyproject.toml /app/

RUN pip install --no-cache-dir /app

HEALTHCHECK CMD pgrep -f agent.main >/dev/null || exit 1

CMD ["/run.sh"]
