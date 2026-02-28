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

### Frontend (GitHub Pages)

The frontend is automatically deployed to **GitHub Pages** via GitHub Actions.

- **URL**: `https://CIPFZ.github.io/youtobe-parser/` (Once the Action completes)
- **Configuration**: If you host the backend on a different domain, set the `VITE_API_BASE` environment variable in the GitHub Action or as a secret.

### Backend (Required for Parsing)

Since GitHub Pages is static-only, the Python backend must be hosted separately.

- **[Render](https://render.com/) / [Railway](https://railway.app/)**: Connect your GitHub repo and deploy using the `Dockerfile`.
- **Manual**:
  ```bash
  docker pull ghcr.io/cipfz/youtobe-parser:main
  docker run -d -p 8000:8000 ghcr.io/cipfz/youtobe-parser:main
  ```

## 📄 License

[MIT License](LICENSE)
