Part 1: Requirements & Proposal Document (RPD)1. 项目概述 (Project Overview)构建一个私有的、高性能的 YouTube 视频解析与下载 Web 系统，支持高并发处理、自动化反爬绕过，并提供极客友好的全格式选择界面。2. 功能需求 (Functional Requirements)异步解析逻辑： 采用“提交任务 -> 获取 TaskID -> 轮询进度 -> 获得结果”的异步模型。全格式提取： 提取视频的所有清晰度（8K/4K/1080p等）、编码（AV1/VP9/H264）及纯音频流。元数据展示： 实时展示视频标题、封面、时长、频道信息。反爬自动处理： 集成 PO Token 机制，无需手动更新 Cookies。网络适配： 支持通过 .env 配置全局代理，确保内地环境可直接访问。流式下载： 支持后端作为“流式网关”，不占用磁盘存储，直接转发字节流。3. 非功能需求 (Non-Functional Requirements)高并发/低占用： 采用异步 IO (FastAPI) 和流式转发，避免内存和磁盘 I/O 瓶颈。高可扩展性： 核心组件（API、Worker、Redis、Token Provider）全部容器化。安全性： 配置脱敏，所有敏感信息（代理、Token 地址）均在 .env 中管理。4. 技术栈 (Technical Stack)后端： Python 3.10+ / FastAPI核心： yt-dlp (Library mode)任务队列： Redis + Celery 或 FastAPI BackgroundTasks辅助服务： Node.js 基于 Docker 的 PO Token Provider前端： Vue 3 / Vite / Tailwind CSS / TanStack QueryPart 
2: 架构示意图
```
graph TD
    subgraph Frontend [用户接入层 - Vue 3 / Vite]
        UI[Web 界面] -->|1. 提交 URL| API
        API -->|4. 轮询进度| UI
        UI -->|5. 点击下载| DL[流式转发接口]
    end

    subgraph Backend [逻辑调度层 - FastAPI]
        API[API Gateway] -->|2. 创建任务| Redis[(Redis Queue)]
        API -.->|缓存读取| Cache[(Result Cache)]
    end

    subgraph Worker_Layer [执行核心层 - yt-dlp Cluster]
        Redis -->|3. 领取任务| Worker[yt-dlp Worker]
        Worker -->|请求 Token| POT[PO Token Provider]
        Worker -->|带 Token 解析| YT((YouTube Server))
        Worker -->|更新进度| Redis
        Worker -->|存储结果| Cache
    end

    subgraph Network [网络出口层 - .env Config]
        Proxy{GLOBAL_PROXY}
        POT --> Proxy
        Worker --> Proxy
        DL --> Proxy
    end
```
架构关键点深度解析 (配合上图理解)
任务解耦层 (Redis Task Queue)：

为什么这样做： 当用户点击“解析”时，FastAPI 只负责把任务丢进 Redis 并返回一个 task_id。这样 API 响应是毫秒级的。

高并发保障： 即使 1000 人同时访问，也只是 Redis 里的 1000 条数据，不会阻塞 Web 线程。

执行核心 (Worker Cluster)：

yt-dlp 实例： 这里的 Worker 是真正干活的。它们从 Redis 拿任务，通过 .env 中配置的 GLOBAL_PROXY 翻墙去 YouTube。

PO Token 注入： Worker 在请求 YouTube 前，先向旁路的 PO Token Provider 拿“通行证”。

零拷贝流式转发 (Stream Proxying)：

避开磁盘： 视频流直接从 YouTube 经过 Worker 的内存缓冲区 (Chunk Buffer) 转发给用户浏览器。

内存控制： 无论视频是 100MB 还是 10GB，Worker 消耗的内存始终稳定在几个 MB 的缓冲区大小。

环境配置中心 (.env)：

所有的代理地址、Token 服务地址、并发限制参数都集中管理。实现“一处修改，全局生效”。

Part 3: 实施计划 (Implementation Plan)我将开发过程分为四个阶段，每个阶段都有明确的交付物。阶段一：环境搭建与核心验证 (Infrastructure & Core)Task 1.1: 准备 .env 模板，配置 GLOBAL_PROXY 和基础参数。Task 1.2: 部署 PO Token Provider 容器，验证 Token 获取接口。Task 1.3: 编写最小化 Python 脚本，验证 yt-dlp 结合代理与 PO Token 能在内地环境成功解析 4K 视频元数据。阶段二：后端异步框架开发 (Backend & Async Logic)Task 2.1: 搭建 FastAPI 基础骨架，实现 POST /v1/analyze 接口。Task 2.2: 集成 Redis。实现任务状态机（Pending -> Processing -> Completed/Failed）。Task 2.3: 编写 Worker 逻辑，使用 yt-dlp 的进度钩子（Progress Hooks）实时更新 Redis 中的百分比。Task 2.4: 实现 StreamingResponse 下载接口，验证“不落盘下载”。阶段三：前端界面开发 (Frontend & UI)Task 3.1: 使用 Tailwind CSS 搭建响应式布局（输入框、进度条、结果卡片）。Task 3.2: 实现解析结果分类逻辑，将几百个格式按“音画合一”、“仅视频”、“仅音频”自动归类。Task 3.3: 对接后端轮询接口，实现平滑的进度展示动画。阶段四：高并发优化与部署 (Optimization & Deploy)Task 4.1: 并发限流： 加入异步信号量（Semaphore），限制同时解析的数量。Task 4.2: 结果缓存： 实现基于 URL 哈希的 Redis 缓存，避免 1 小时内重复请求 YouTube。Task 4.3: Docker Compose： 编写一键启动脚本，包含 Web、API、Redis、Worker 和 Token Provider。Part 4: 风险评估与对策风险点应对方案YouTube 算法更新导致 PO Token 失效定期更新 Token Provider 的 Docker 镜像。代理带宽被撑爆在 .env 中限制 MAX_CONCURRENT_DOWNLOADS。内网穿透与 IP 绑定确保后端解析与用户下载时，IP 的地理位置（如都在香港）尽量接近。