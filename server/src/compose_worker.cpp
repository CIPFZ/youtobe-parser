#include "compose_worker.h"

#include <iostream>
#include <sstream>
#include <filesystem>
#include <vector>
#include <algorithm>

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavfilter/buffersink.h>
#include <libavfilter/buffersrc.h>
#include <libavfilter/avfilter.h>
#include <libavutil/opt.h>
#include <libavutil/pixdesc.h>
#include <libavutil/error.h>
}

#define LOG_INF(msg) std::cout << "[ComposeWorker][INFO] " << msg << std::endl
#define LOG_ERR(msg) std::cerr << "[ComposeWorker][ERROR] " << msg << std::endl

namespace avsvc {

std::string build_compose_fingerprint(const std::string& video_path,
                                      const std::string& audio_path,
                                      const std::string& subtitle_path,
                                      const std::string& output_path) {
    const auto key = "hardsub_compose|" + video_path + "|" + audio_path + "|" + subtitle_path + "|" + output_path;
    const auto hashed = std::hash<std::string>{}(key);
    std::ostringstream oss;
    oss << std::hex << hashed;
    return oss.str();
}

int ComposeWorker::run(const std::string& video_path,
                       const std::string& audio_path,
                       const std::string& subtitle_path,
                       const std::string& output_path,
                       ComposeProgressCallback on_progress) const {
    
    LOG_INF("Starting hardsub compose task...");
    LOG_INF("Video: " << video_path);
    LOG_INF("Audio: " << audio_path);
    LOG_INF("Subtitle: " << subtitle_path);
    LOG_INF("Output: " << output_path);

    if (!std::filesystem::exists(video_path) || !std::filesystem::exists(audio_path) || !std::filesystem::exists(subtitle_path)) {
        LOG_ERR("Input files missing.");
        if (on_progress) on_progress(0, "failed: input file(s) not found");
        return -1;
    }

    int ret = 0;
    AVFormatContext *ifmt_ctx_v = nullptr, *ifmt_ctx_a = nullptr, *ofmt_ctx = nullptr;
    AVCodecContext *dec_ctx = nullptr, *enc_ctx = nullptr;
    AVFilterGraph *filter_graph = nullptr;
    AVFilterContext *buffersink_ctx = nullptr, *buffersrc_ctx = nullptr;
    AVPacket *pkt = nullptr, *enc_pkt = nullptr, *audio_pkt = nullptr;
    AVFrame *frame = nullptr, *filt_frame = nullptr;
    
    int video_stream_idx = -1, audio_stream_idx = -1;
    int out_video_idx = -1, out_audio_idx = -1;
    
    int64_t v_pts_us = 0, a_pts_us = 0;
    bool video_eof = false, audio_eof = false, decode_eof = false;

    // 1. 打开视频输入
    LOG_INF("Opening video input...");
    if ((ret = avformat_open_input(&ifmt_ctx_v, video_path.c_str(), nullptr, nullptr)) < 0) {
        LOG_ERR("Cannot open video input.");
        goto end;
    }
    avformat_find_stream_info(ifmt_ctx_v, nullptr);
    video_stream_idx = av_find_best_stream(ifmt_ctx_v, AVMEDIA_TYPE_VIDEO, -1, -1, nullptr, 0);
    
    // 2. 打开音频输入
    LOG_INF("Opening audio input...");
    if ((ret = avformat_open_input(&ifmt_ctx_a, audio_path.c_str(), nullptr, nullptr)) < 0) {
        LOG_ERR("Cannot open audio input.");
        goto end;
    }
    avformat_find_stream_info(ifmt_ctx_a, nullptr);
    audio_stream_idx = av_find_best_stream(ifmt_ctx_a, AVMEDIA_TYPE_AUDIO, -1, -1, nullptr, 0);

    // 3. 打开输出容器
    LOG_INF("Allocating output context...");
    avformat_alloc_output_context2(&ofmt_ctx, nullptr, nullptr, output_path.c_str());
    if (!ofmt_ctx) { ret = -1; goto end; }

    // 4. 配置视频解码器
    {
        AVStream *in_v_stream = ifmt_ctx_v->streams[video_stream_idx];
        const AVCodec *dec = avcodec_find_decoder(in_v_stream->codecpar->codec_id);
        dec_ctx = avcodec_alloc_context3(dec);
        avcodec_parameters_to_context(dec_ctx, in_v_stream->codecpar);
        avcodec_open2(dec_ctx, dec, nullptr);
        LOG_INF("Video decoder opened.");
    }

    // 5. 配置视频编码器 (libx264)
    {
        const AVCodec *enc = avcodec_find_encoder_by_name("libx264");
        if (!enc) { LOG_ERR("libx264 not found!"); ret = -1; goto end; }
        enc_ctx = avcodec_alloc_context3(enc);
        enc_ctx->height = dec_ctx->height;
        enc_ctx->width = dec_ctx->width;
        enc_ctx->sample_aspect_ratio = dec_ctx->sample_aspect_ratio;
        enc_ctx->pix_fmt = AV_PIX_FMT_YUV420P; // 强制标准像素格式
        enc_ctx->time_base = av_inv_q(dec_ctx->framerate);
        
        if (ofmt_ctx->oformat->flags & AVFMT_GLOBALHEADER)
            enc_ctx->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
            
        // 性能优化：使用 fast 预设降低 CPU 占用，crf=23 保证质量
        av_opt_set(enc_ctx->priv_data, "preset", "fast", 0);
        av_opt_set(enc_ctx->priv_data, "crf", "23", 0);
        
        if ((ret = avcodec_open2(enc_ctx, enc, nullptr)) < 0) {
            LOG_ERR("Cannot open video encoder.");
            goto end;
        }
        
        AVStream *out_v_stream = avformat_new_stream(ofmt_ctx, nullptr);
        out_video_idx = out_v_stream->index;
        avcodec_parameters_from_context(out_v_stream->codecpar, enc_ctx);
        out_v_stream->time_base = enc_ctx->time_base;
        LOG_INF("Video encoder libx264 configured.");
    }

    // 6. 配置音频输出流 (Stream Copy)
    {
        AVStream *in_a_stream = ifmt_ctx_a->streams[audio_stream_idx];
        AVStream *out_a_stream = avformat_new_stream(ofmt_ctx, nullptr);
        out_audio_idx = out_a_stream->index;
        avcodec_parameters_copy(out_a_stream->codecpar, in_a_stream->codecpar);
        out_a_stream->codecpar->codec_tag = 0;
        out_a_stream->time_base = in_a_stream->time_base;
        LOG_INF("Audio output stream configured for copying.");
    }

    // 7. 配置滤镜图 (Filter Graph: buffer -> ass -> buffersink)
    {
        LOG_INF("Setting up subtitle filter graph...");
        filter_graph = avfilter_graph_alloc();
        const AVFilter *buffersrc  = avfilter_get_by_name("buffer");
        const AVFilter *buffersink = avfilter_get_by_name("buffersink");

        char args[512];
        AVStream *in_v_stream = ifmt_ctx_v->streams[video_stream_idx];
        snprintf(args, sizeof(args),
                 "video_size=%dx%d:pix_fmt=%d:time_base=%d/%d:pixel_aspect=%d/%d",
                 dec_ctx->width, dec_ctx->height, dec_ctx->pix_fmt,
                 in_v_stream->time_base.num, in_v_stream->time_base.den,
                 dec_ctx->sample_aspect_ratio.num, dec_ctx->sample_aspect_ratio.den);

        avfilter_graph_create_filter(&buffersrc_ctx, buffersrc, "in", args, nullptr, filter_graph);
        avfilter_graph_create_filter(&buffersink_ctx, buffersink, "out", nullptr, nullptr, filter_graph);
        
        enum AVPixelFormat pix_fmts[] = { enc_ctx->pix_fmt, AV_PIX_FMT_NONE };
        av_opt_set_int_list(buffersink_ctx, "pix_fmts", pix_fmts, AV_PIX_FMT_NONE, AV_OPT_SEARCH_CHILDREN);

        AVFilterInOut *outputs = avfilter_inout_alloc();
        AVFilterInOut *inputs  = avfilter_inout_alloc();
        outputs->name       = av_strdup("in");
        outputs->filter_ctx = buffersrc_ctx;
        outputs->pad_idx    = 0;
        outputs->next       = nullptr;
        inputs->name       = av_strdup("out");
        inputs->filter_ctx = buffersink_ctx;
        inputs->pad_idx    = 0;
        inputs->next       = nullptr;

        // 构造 ass 滤镜参数
        std::string filter_str = "ass='" + subtitle_path + "'";
        if ((ret = avfilter_graph_parse_ptr(filter_graph, filter_str.c_str(), &inputs, &outputs, nullptr)) < 0) {
            LOG_ERR("Cannot parse filter graph.");
            goto end;
        }
        if ((ret = avfilter_graph_config(filter_graph, nullptr)) < 0) {
            LOG_ERR("Cannot config filter graph.");
            goto end;
        }
        avfilter_inout_free(&inputs);
        avfilter_inout_free(&outputs);
        LOG_INF("Filter graph created successfully.");
    }

    // 8. 写入文件头
    if (!(ofmt_ctx->oformat->flags & AVFMT_NOFILE)) {
        if (avio_open(&ofmt_ctx->pb, output_path.c_str(), AVIO_FLAG_WRITE) < 0) {
            LOG_ERR("Cannot open output file."); ret = -1; goto end;
        }
    }
    if ((ret = avformat_write_header(ofmt_ctx, nullptr)) < 0) {
        LOG_ERR("Error occurred when opening output file."); goto end;
    }

    // 初始化包和帧
    pkt = av_packet_alloc();
    enc_pkt = av_packet_alloc();
    audio_pkt = av_packet_alloc();
    frame = av_frame_alloc();
    filt_frame = av_frame_alloc();
    
    if (on_progress) on_progress(10, "starting hardsub process...");

    LOG_INF("Entering main processing loop...");
    // 9. 主处理循环：交替读取视频和音频，以保证时间戳单调递增
    while (!video_eof || !audio_eof) {
        // 如果音频已经结束，或者视频进度落后于音频，且视频没结束，则处理视频
        if (!video_eof && (audio_eof || v_pts_us <= a_pts_us)) {
            ret = av_read_frame(ifmt_ctx_v, pkt);
            if (ret < 0) {
                video_eof = true;
                // 向解码器发送 EOF flush
                avcodec_send_packet(dec_ctx, nullptr);
            } else if (pkt->stream_index == video_stream_idx) {
                avcodec_send_packet(dec_ctx, pkt);
            }
            av_packet_unref(pkt);

            // 接收解码后的帧
            while (avcodec_receive_frame(dec_ctx, frame) >= 0) {
                // 送入滤镜图烧录字幕
                av_buffersrc_add_frame_flags(buffersrc_ctx, frame, AV_BUFFERSRC_FLAG_KEEP_REF);
                
                while (av_buffersink_get_frame(buffersink_ctx, filt_frame) >= 0) {
                    // 更新视频进度
                    v_pts_us = av_rescale_q(filt_frame->pts, ifmt_ctx_v->streams[video_stream_idx]->time_base, {1, AV_TIME_BASE});
                    
                    // 送入编码器
                    avcodec_send_frame(enc_ctx, filt_frame);
                    while (avcodec_receive_packet(enc_ctx, enc_pkt) >= 0) {
                        av_packet_rescale_ts(enc_pkt, enc_ctx->time_base, ofmt_ctx->streams[out_video_idx]->time_base);
                        enc_pkt->stream_index = out_video_idx;
                        av_interleaved_write_frame(ofmt_ctx, enc_pkt);
                        av_packet_unref(enc_pkt);
                    }
                    av_frame_unref(filt_frame);
                }
                av_frame_unref(frame);
            }
        } 
        // 处理音频 (Stream Copy)
        else if (!audio_eof) {
            ret = av_read_frame(ifmt_ctx_a, audio_pkt);
            if (ret < 0) {
                audio_eof = true;
            } else if (audio_pkt->stream_index == audio_stream_idx) {
                // 更新音频进度
                a_pts_us = av_rescale_q(audio_pkt->pts, ifmt_ctx_a->streams[audio_stream_idx]->time_base, {1, AV_TIME_BASE});
                
                av_packet_rescale_ts(audio_pkt, ifmt_ctx_a->streams[audio_stream_idx]->time_base, ofmt_ctx->streams[out_audio_idx]->time_base);
                audio_pkt->stream_index = out_audio_idx;
                av_interleaved_write_frame(ofmt_ctx, audio_pkt);
            }
            av_packet_unref(audio_pkt);
        }
        
        // 进度汇报 (假设视频更长，用视频进度计算)
        if (on_progress && ifmt_ctx_v->duration > 0 && !video_eof) {
            int p = 10 + (v_pts_us * 85 / ifmt_ctx_v->duration);
            on_progress(std::min(95, std::max(10, p)), "hardsub encoding...");
        }
    }

    // 10. Flush filter and encoder
    LOG_INF("Flushing filters and encoders...");
    av_buffersrc_add_frame_flags(buffersrc_ctx, nullptr, 0);
    while (av_buffersink_get_frame(buffersink_ctx, filt_frame) >= 0) {
        avcodec_send_frame(enc_ctx, filt_frame);
        while (avcodec_receive_packet(enc_ctx, enc_pkt) >= 0) {
            av_packet_rescale_ts(enc_pkt, enc_ctx->time_base, ofmt_ctx->streams[out_video_idx]->time_base);
            enc_pkt->stream_index = out_video_idx;
            av_interleaved_write_frame(ofmt_ctx, enc_pkt);
            av_packet_unref(enc_pkt);
        }
        av_frame_unref(filt_frame);
    }
    
    // Flush encoder
    avcodec_send_frame(enc_ctx, nullptr);
    while (avcodec_receive_packet(enc_ctx, enc_pkt) >= 0) {
        av_packet_rescale_ts(enc_pkt, enc_ctx->time_base, ofmt_ctx->streams[out_video_idx]->time_base);
        enc_pkt->stream_index = out_video_idx;
        av_interleaved_write_frame(ofmt_ctx, enc_pkt);
        av_packet_unref(enc_pkt);
    }

    av_write_trailer(ofmt_ctx);
    LOG_INF("Output file written successfully.");
    if (on_progress) on_progress(100, "done");
    ret = 0;

end:
    // 11. 完美的 RAII/Goto 资源释放，杜绝内存泄漏
    LOG_INF("Cleaning up resources...");
    if (pkt) av_packet_free(&pkt);
    if (enc_pkt) av_packet_free(&enc_pkt);
    if (audio_pkt) av_packet_free(&audio_pkt);
    if (frame) av_frame_free(&frame);
    if (filt_frame) av_frame_free(&filt_frame);
    if (dec_ctx) avcodec_free_context(&dec_ctx);
    if (enc_ctx) avcodec_free_context(&enc_ctx);
    if (filter_graph) avfilter_graph_free(&filter_graph);
    if (ifmt_ctx_v) avformat_close_input(&ifmt_ctx_v);
    if (ifmt_ctx_a) avformat_close_input(&ifmt_ctx_a);
    if (ofmt_ctx) {
        if (!(ofmt_ctx->oformat->flags & AVFMT_NOFILE)) avio_closep(&ofmt_ctx->pb);
        avformat_free_context(ofmt_ctx);
    }
    return ret;
}

}  // namespace avsvc