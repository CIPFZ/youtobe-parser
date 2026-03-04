#pragma once
#include <iostream>
#include <string>
#include <vector>
#include <chrono>

// 定义简单的线程安全日志宏
#define LOG_INFO(msg)  std::cout << "[INFO][" << avsvc::get_timestamp() << "] " << msg << std::endl
#define LOG_ERROR(msg) std::cerr << "[ERROR][" << avsvc::get_timestamp() << "] " << msg << std::endl

namespace avsvc {
    inline std::string get_timestamp() {
        auto now = std::chrono::system_clock::now();
        auto in_time_t = std::chrono::system_clock::to_time_t(now);
        char buf[20];
        std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", std::localtime(&in_time_t));
        return std::string(buf);
    }
}