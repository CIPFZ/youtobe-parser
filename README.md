# RPD Parser 🚀

A premium, modern media and metadata extractor built with **FastAPI** and **React**. Effortlessly parse YouTube videos and playlists with a sleek, interactive interface.

![RPD Parser UI](https://via.placeholder.com/800x450.png?text=RPD+Parser+UI+Preview) <!-- Replace with actual screenshot later -->

## ✨ Features

- **Multi-Source Parsing**: Extract metadata from YouTube videos, playlists, and more using `yt-dlp`.
- **Real-time Streaming**: Watch playlist items appear in real-time as they are parsed.
- **Proxy Support**: Built-in proxy configuration to handle rate limits and regional restrictions.
- **Premium UI**: Ultra-modern design with glassmorphism, dark mode, and smooth animations.
- **Fully Dockerized**: Easy deployment with optimized multi-stage Docker builds.
- **CI/CD Ready**: Integrated GitHub Actions to build and push images to GitHub Container Registry (GHCR).

## 🛠️ Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [Pydantic](https://docs.pydantic.dev/)
- **Frontend**: [React](https://react.dev/), [Vite](https://vitejs.dev/), [Tailwind CSS 4](https://tailwindcss.com/), [Framer Motion](https://www.framer.com/motion/)
- **Infrastructure**: [Docker](https://www.docker.com/), [GitHub Actions](https://github.com/features/actions)

## 🚀 Getting Started

### Local Development

1. **Clone the repository**:
   ```bash
   git clone git@github.com:CIPFZ/youtobe-parser.git
   cd youtobe-parser
   ```

2. **Backend Setup**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

3. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Running with Docker

```bash
docker build -t youtobe-parser .
docker run -d -p 8000:8000 youtobe-parser
```

Access the app at `http://localhost:8000`.

## 🌐 Deployment

### GitHub Container Registry (GHCR)

This project includes a GitHub Actions workflow that automatically builds and pushes the Docker image to GHCR on every push to `main`.

1. **Pull and Run**:
   ```bash
   docker pull ghcr.io/cipfz/youtobe-parser:main
   docker run -d -p 8000:8000 ghcr.io/cipfz/youtobe-parser:main
   ```

### Direct Deployment (Recommended)

Since this is a full-stack application requiring a Python environment and `ffmpeg`, we recommend the following platforms for "direct from GitHub" deployment:

- **[Render](https://render.com/)**: Connect your GitHub repo, select "Web Service", and it will automatically detect the `Dockerfile`.
- **[Railway](https://railway.app/)**: Connect your GitHub repo and Railway will handle the Docker build and deployment automatically.

## 📄 License

[MIT License](LICENSE)
