FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY lichord ./lichord
RUN pip install --no-cache-dir .
ENV LICHORD_HOST=0.0.0.0 LICHORD_PORT=8787
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=2)" || exit 1
CMD ["lichord"]
