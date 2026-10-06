# Test runner: same pinned libraries as the services, plus pytest. Build context = repo root.
FROM python:3.11-slim
COPY explorer/requirements.txt /tmp/explorer-requirements.txt
COPY messages-api/requirements.txt /tmp/messages-api-requirements.txt
COPY tests/requirements.txt /tmp/tests-requirements.txt
RUN pip install --no-cache-dir -r /tmp/explorer-requirements.txt \
    -r /tmp/messages-api-requirements.txt -r /tmp/tests-requirements.txt
WORKDIR /repo
ENV PYTHONDONTWRITEBYTECODE=1
