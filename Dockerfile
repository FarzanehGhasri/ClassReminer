# The registration form and the reminder job share one image — they are the
# same codebase with two entry points (run_web.py and main.py).
FROM python:3.12-slim

# Bytecode files and stdout buffering both get in the way inside a container:
# the first bloats the image, the second hides logs until the buffer flushes.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Requirements first: this layer is cached and only rebuilt when the file
# changes, so editing application code does not reinstall dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user. The logs directory has to be writable by that user,
# which is why it is created and chowned rather than left to the volume mount.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/logs /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status==200 else 1)"

# Gunicorn, not Flask's development server: that one is single-threaded and
# explicitly not meant for anything but local debugging.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--threads", "4", \
     "--timeout", "30", "--graceful-timeout", "30", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "run_web:application"]
