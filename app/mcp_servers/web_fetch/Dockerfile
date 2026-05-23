FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8765

WORKDIR /srv

RUN pip install \
    "mcp>=1.2.0" \
    "httpx>=0.28.0" \
    "beautifulsoup4>=4.12.0" \
    "readability-lxml>=0.8.1" \
    "lxml>=5.0.0" \
    "lxml_html_clean>=0.2.0"

COPY fetcher.py server.py ./

EXPOSE 8765

CMD ["python", "server.py"]
