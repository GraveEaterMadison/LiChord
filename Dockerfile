FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY lichord ./lichord
COPY bitchord_addon_auth.py ./bitchord_addon_auth.py
RUN pip install --no-cache-dir .
ENV LICHORD_HOST=0.0.0.0 LICHORD_PORT=8787
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD python -c "import socket; s=socket.create_connection(('127.0.0.1',8787),timeout=2); s.close()" || exit 1
CMD ["lichord"]
