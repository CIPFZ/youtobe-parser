#include "compose_worker.h"

#include <iostream>
#include <sstream>
#include <filesystem>
#include <cstdio>
#include <memory>
#include <regex>
#include <cstdlib>
#include <thread>      // 修复：添加 thread 头文件以支持 hardware_concurrency
#include <algorithm>   // 修复：添加 algorithm 头文件以支持 std::max 和 std::min

extern "C" {
#include <libavformat/avformat.h> // 仅用于快速获取视频总时长
}

#define LOG_INF(msg) std::cout << "[ComposeWorker][INFO] " << msg << std::endl
#define LOG_ERR(msg) std::cerr << "[ComposeWorker][ERROR] " << msg << std::endl

namespace avsvc {

std::string build_compose_fingerprint(const std::string& video_path,
                                      const std::string& audio_path,
                                      const std::string& subtitle_path,
                                      const std::string& output_path) {
    const auto key = "hardsub_compose_cli|" + video_path + "|" + audio_path + "|" + subtitle_path + "|" + output_path;
    const auto hashed = std::hash<std::string>{}(key);
    std::ostringstream oss;
    oss << std::hex << hashed;
    return oss.str();
}

// 辅助函数：处理 FFmpeg 滤镜路径中的特殊字符 (冒号、反斜杠等)
std::string escape_filter_path(const std::string& path) {
    std::string escaped;
    for (char c : path) {
        if (c == ':' || c == '\\' || c == '\'') escaped += '\\';
        escaped += c;
    }
    return escaped;
}

int ComposeWorker::run(const std::string& video_path,
                       const std::string& audio_path,
                       const std::string& subtitle_path,
                       const std::string& output_path,
                       ComposeProgressCallback on_progress) const {
    
    LOG_INF("Starting compose task using FFmpeg CLI Engine...");

    if (!std::filesystem::exists(video_path) || !std::filesystem::exists(audio_path) || !std::filesystem::exists(subtitle_path)) {
        LOG_ERR("Input files missing.");
        if (on_progress) on_progress(0, "failed: input file(s) not found");
        return -1;
    }

    // 1. 获取视频总时长，用于精确计算百分比进度
    int64_t duration_us = 0;
    AVFormatContext* fmt_ctx = nullptr;
    if (avformat_open_input(&fmt_ctx, video_path.c_str(), nullptr, nullptr) == 0) {
        if (avformat_find_stream_info(fmt_ctx, nullptr) >= 0) {
            duration_us = fmt_ctx->duration;
        }
        avformat_close_input(&fmt_ctx);
    }

    if (duration_us <= 0) {
        LOG_ERR("Could not determine video duration.");
        return -1;
    }

    // 2. 环境配置检查
    const char* env_nvenc = std::getenv("AV_ENABLE_NVENC");
    bool use_nvenc = (env_nvenc == nullptr || std::string(env_nvenc) != "false");
    
    const char* env_ratio = std::getenv("AV_THREAD_RATIO");
    std::string threads = "0"; // 默认 0 让 ffmpeg 自动拉满
    if (env_ratio != nullptr) {
        try {
            float ratio = std::stof(env_ratio);
            if (ratio > 0.0f && ratio <= 1.0f) {
                int cores = std::max(1, static_cast<int>(std::thread::hardware_concurrency() * ratio));
                threads = std::to_string(cores);
            }
        } catch (...) {}
    }

    // 3. 构建超级 FFmpeg 命令行
    // 一步到位：视频轨来自输入 0，音频轨来自输入 1，烧录字幕，控制画质
    std::string escaped_sub = escape_filter_path(subtitle_path);
    std::string vf_filter = "ass=filename='" + escaped_sub + "'";
    
    // 如果是 srt，强制指定我们 Docker 中的 Noto 字体防止方块字
    if (subtitle_path.find(".srt") != std::string::npos) {
        vf_filter = "subtitles=filename='" + escaped_sub + "':force_style='Fontname=Noto Sans CJK SC'";
    }

    std::ostringstream cmd;
    cmd << "ffmpeg -y ";
    if (use_nvenc) cmd << "-hwaccel auto "; // 开启硬件解码加速
    
    cmd << "-i \"" << video_path << "\" "
        << "-i \"" << audio_path << "\" "
        << "-vf \"" << vf_filter << "\" ";

    if (use_nvenc) {
        cmd << "-c:v h264_nvenc -preset p4 -cq 26 ";
    } else {
        cmd << "-c:v libx264 -preset fast -crf 23 -threads " << threads << " ";
    }

    // 复制音频轨，映射输入流
    cmd << "-c:a copy -map 0:v:0 -map 1:a:0 -shortest \"" << output_path << "\" 2>&1";

    LOG_INF("Executing Command: " << cmd.str());

    // 4. 执行命令并解析进度输出
    FILE* pipe = popen(cmd.str().c_str(), "r");
    if (!pipe) {
        LOG_ERR("Failed to run ffmpeg command.");
        return -1;
    }

    char buffer[256];
    // 正则匹配 ffmpeg 输出的时间: time=00:01:23.45
    std::regex time_regex("time=(\\d{2}):(\\d{2}):(\\d{2})\\.(\\d{2})");
    std::smatch match;

    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        std::string line(buffer);
        if (std::regex_search(line, match, time_regex)) {
            int h = std::stoi(match[1].str());
            int m = std::stoi(match[2].str());
            int s = std::stoi(match[3].str());
            int64_t current_us = (h * 3600 + m * 60 + s) * 1000000LL;
            
            int progress = static_cast<int>((current_us * 100) / duration_us);
            if (on_progress) {
                // 将进度限制在 1-99 之间，等待最后 pclose 成功才给 100
                on_progress(std::min(99, std::max(1, progress)), "Encoding with FFmpeg Engine...");
            }
        }
    }

    // 5. 检查执行结果
    int ret_code = pclose(pipe);
    if (ret_code == 0) {
        LOG_INF("FFmpeg Engine completed successfully.");
        if (on_progress) on_progress(100, "done");
        return 0;
    } else {
        LOG_ERR("FFmpeg Engine failed with exit code: " << ret_code);
        if (on_progress) on_progress(0, "failed: ffmpeg process exited with error");
        return -1;
    }
}

}  // namespace avsvc