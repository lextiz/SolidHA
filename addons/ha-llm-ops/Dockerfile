FROM alpine:3.19.1

RUN apk add --no-cache python3 py3-pip jq

WORKDIR /app
COPY pyproject.toml README.md .
COPY agent ./agent
RUN pip install --no-cache-dir --break-system-packages .
ENV PYTHONPATH=/app

COPY run.sh /run.sh
RUN chmod +x /run.sh

HEALTHCHECK --interval=30s --timeout=5s CMD [ -f /tmp/healthy ] || exit 1

CMD ["/run.sh"]
