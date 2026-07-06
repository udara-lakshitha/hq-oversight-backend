WORKDIR /

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /

# 6. Upgrade pip and install all listed Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /requirements.txt

COPY . /

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main.main:app --host 0.0.0.0 --port ${PORT:-8000}"]