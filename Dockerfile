# -------------------------
# Stage 1: Build Frontend
# -------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /build/frontend
# Install dependencies
COPY frontend/package*.json ./
RUN npm install

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# -------------------------
# Stage 2: Final Runtime Image
# -------------------------
FROM python:3.12-slim

WORKDIR /app

# Enable faster mirror and install required system packages (ffmpeg for yt-dlp)
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv globally for fast dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Install Python dependencies globally within the container using uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy FastAPI backend code
COPY . .

# Copy compiled React frontend from the builder stage
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

EXPOSE 8000

# Start the optimized Uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
