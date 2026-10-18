FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/services/api
WORKDIR /app
COPY services/api/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock && useradd --create-home --uid 10001 proofpay
COPY --chown=proofpay:proofpay services/api services/api
COPY --chown=proofpay:proofpay scripts scripts
COPY --chown=proofpay:proofpay evaluation evaluation
USER proofpay
EXPOSE 8017
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8017", "--no-access-log", "--no-proxy-headers"]
