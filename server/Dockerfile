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

# 合并所有运行时依赖（包含音视频库、权限工具和中文字体库），并清理缓存
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gosu \
    libstdc++6 \
    ca-certificates \
    libavformat58 \
    libavcodec58 \
    libavutil56 \
    libswresample3 \
    libavfilter7 \
    libass9 \
    libssl3 \
    zlib1g \
    libuuid1 \
    libsqlite3-0 \
    fonts-noto-cjk \
    fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 拷贝核心产物
COPY --from=builder /app/build/av_service /app/av_service
COPY --from=builder /usr/local/lib/libworkflow.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/libwhisper.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/libggml*.so* /usr/local/lib/

# 生成权限动态修复脚本，使用花括号组合命令以增强可读性
RUN { \
    echo '#!/bin/bash'; \
    echo '# 如果容器是以 root 启动的（没有在 compose 里指定 user），则执行原有降权逻辑'; \
    echo 'if [ "$(id -u)" = "0" ]; then'; \
    echo '    PUID=${LOCAL_UID:-1000}'; \
    echo '    PGID=${LOCAL_GID:-1000}'; \
    echo '    groupadd -f -g $PGID avgroup'; \
    echo '    id -u avuser &>/dev/null || useradd -u $PUID -g $PGID -s /bin/bash -m avuser'; \
    echo '    chown -R $PUID:$PGID /data /models /app/logs 2>/dev/null || true'; \
    echo '    exec gosu avuser /app/av_service "$@"'; \
    echo 'else'; \
    echo '    # 如果已经在 compose 里指定了 user，则直接以该身份启动服务'; \
    echo '    echo "Starting with user: $(id -u):$(id -g)"'; \
    echo '    exec /app/av_service "$@"'; \
    echo 'fi'; \
} > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENV LD_LIBRARY_PATH=/usr/local/lib
EXPOSE 8888

ENTRYPOINT ["/app/entrypoint.sh"]