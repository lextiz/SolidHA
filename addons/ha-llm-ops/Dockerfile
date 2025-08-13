FROM alpine:3.19.1

RUN apk add --no-cache python3 py3-pip jq

WORKDIR /app
COPY agent /app/agent
ENV PYTHONPATH=/app

COPY addons/ha-llm-ops/run.sh /run.sh
RUN chmod +x /run.sh

HEALTHCHECK --interval=30s --timeout=5s CMD [ -f /tmp/healthy ] || exit 1

CMD ["/run.sh"]
