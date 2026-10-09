# Samvit — local-first personal AI (CLI + MCP server).
#
# Samvit is standard-library only, so the image stays tiny.
FROM python:3.12-slim

WORKDIR /app

COPY . .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

# Default: report status. Override with e.g. `docker run samvit ask "hello"`.
ENTRYPOINT ["samvit"]
CMD ["status"]
