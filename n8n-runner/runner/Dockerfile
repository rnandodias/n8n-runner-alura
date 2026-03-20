FROM python:3.11-slim

# Dependencias para cairosvg (rasterizacao de SVG)
RUN apt-get update && apt-get install -y \
    libcairo2 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/req.txt
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r /tmp/req.txt

COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8000
CMD ["/start.sh"]
