FROM python:3.11-slim
RUN pip install --no-cache-dir "Flask>=3.0"
COPY mock_hornet.py /app/mock_hornet.py
EXPOSE 14265
CMD ["python", "/app/mock_hornet.py"]
