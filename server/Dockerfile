# ==========================================
# 阶段 1: 编译环境 (builder)
# ==========================================
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
# 包含硬字幕需要的 libavfilter-dev 和 libass-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config git ca-certificates \
    libavformat-dev libavcodec-dev libavutil-dev libswresample-dev \
    libavfilter-dev libass-dev \
    libssl-dev zlib1g-dev uuid-dev libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# 1. 安装 sogou/workflow
RUN git clone --depth 1 https://github.com/sogou/workflow.git /tmp/workflow && \
    make -C /tmp/workflow -j"$(nproc)" && \
    make -C /tmp/workflow install

# 2. 安装 whisper.cpp
RUN git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git /tmp/whisper.cpp && \
    cmake -S /tmp/whisper.cpp -B /tmp/whisper.cpp/build \
      -DBUILD_SHARED_LIBS=ON -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=OFF && \
    cmake --build /tmp/whisper.cpp/build -j"$(nproc)" && \
    cp -a /tmp/whisper.cpp/include/whisper.h /usr/local/include/ && \
    mkdir -p /usr/local/include/whisper && \
    cp -a /tmp/whisper.cpp/ggml/include/ggml*.h /usr/local/include/whisper/ && \
    cp -a /tmp/whisper.cpp/build/src/libwhisper.so* /usr/local/lib/ && \
    cp -a /tmp/whisper.cpp/build/ggml/src/libggml*.so* /usr/local/lib/ && \
    ldconfig

# 3. 编译 C++ 服务 (av_service)
WORKDIR /app
COPY server /app
RUN cmake -S . -B build \
      -DENABLE_WORKFLOW=ON \
      -DENABLE_FFMPEG=ON \
      -DENABLE_WHISPERCPP=ON && \
    cmake --build build -j"$(nproc)"

# ==========================================
# 阶段 2: 运行环境 (runtime)
# ==========================================
FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
# 包含硬字幕需要的 libavfilter7 和 libass9，以及调试用的 ffmpeg 工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libstdc++6 ca-certificates \
    libavformat58 libavcodec58 libavutil56 libswresample3 \
    libavfilter7 libass9 \
    libssl3 zlib1g libuuid1 libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从 builder 阶段拷贝所需文件
COPY --from=builder /app/build/av_service /app/av_service
COPY --from=builder /usr/local/lib/libworkflow.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/libwhisper.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/libggml*.so* /usr/local/lib/

# 环境自检脚本：验证编码器和滤镜是否就绪
RUN echo '#!/bin/bash\n\
echo "--- Environment Check ---"\n\
ffmpeg -version | head -n 1\n\
echo -n "x264 Support: " && ffmpeg -encoders | grep libx264 || echo "MISSING"\n\
echo -n "Subtitles Filter: " && ffmpeg -filters | grep subtitles || echo "MISSING"\n\
echo "------------------------"\n\
exec /app/av_service "$@"' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENV LD_LIBRARY_PATH=/usr/local/lib
EXPOSE 8888

ENTRYPOINT ["/app/entrypoint.sh"]