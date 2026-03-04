#include "compose_worker.h"
#include "merge_worker.h"

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
    
    LOG_INF("Starting hardsub compose task (Two-Step Pipeline)...");

    if (!std::filesystem::exists(video_path) || !std::filesystem::exists(audio_path) || !std::filesystem::exists(subtitle_path)) {
        LOG_ERR("Input files missing.");
        if (on_progress) on_progress(0, "failed: input file(s) not found");
        return -1;
    }

    std::string temp_video_path = output_path + ".tmp.mp4";
    int ret = 0;

    // ==========================================================
    // 第一阶段：纯视频硬字幕渲染 (剥离音频，解决交织混乱与卡顿)
    // ==========================================================
    AVFormatContext *ifmt_ctx_v = nullptr, *ofmt_ctx = nullptr;
    AVCodecContext *dec_ctx = nullptr, *enc_ctx = nullptr;
    AVFilterGraph *filter_graph = nullptr;
    AVFilterContext *buffersink_ctx = nullptr, *buffersrc_ctx = nullptr;
    AVPacket *pkt = nullptr, *enc_pkt = nullptr;
    AVFrame *frame = nullptr, *filt_frame = nullptr;
    int video_stream_idx = -1;
    int out_video_idx = -1;

    if ((ret = avformat_open_input(&ifmt_ctx_v, video_path.c_str(), nullptr, nullptr)) < 0) {
        LOG_ERR("Cannot open video input."); return -1;
    }
    avformat_find_stream_info(ifmt_ctx_v, nullptr);
    video_stream_idx = av_find_best_stream(ifmt_ctx_v, AVMEDIA_TYPE_VIDEO, -1, -1, nullptr, 0);

    avformat_alloc_output_context2(&ofmt_ctx, nullptr, nullptr, temp_video_path.c_str());

    // 解码器
    AVStream *in_v_stream = ifmt_ctx_v->streams[video_stream_idx];
    const AVCodec *dec = avcodec_find_decoder(in_v_stream->codecpar->codec_id);
    dec_ctx = avcodec_alloc_context3(dec);
    avcodec_parameters_to_context(dec_ctx, in_v_stream->codecpar);
    avcodec_open2(dec_ctx, dec, nullptr);

    // 编码器
    const AVCodec *enc = avcodec_find_encoder_by_name("libx264");
    enc_ctx = avcodec_alloc_context3(enc);
    enc_ctx->height = dec_ctx->height;
    enc_ctx->width = dec_ctx->width;
    enc_ctx->sample_aspect_ratio = dec_ctx->sample_aspect_ratio;
    enc_ctx->pix_fmt = AV_PIX_FMT_YUV420P;

    AVRational frame_rate = av_guess_frame_rate(ifmt_ctx_v, in_v_stream, nullptr);
    if (frame_rate.num <= 0 || frame_rate.den <= 0) frame_rate = {30, 1};
    enc_ctx->time_base = av_inv_q(frame_rate);
    enc_ctx->framerate = frame_rate;
    
    if (ofmt_ctx->oformat->flags & AVFMT_GLOBALHEADER) enc_ctx->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
        
    // 关键优化：强制 CRF=23 和 Preset=fast，完美解决 400MB 体积暴增问题
    av_opt_set(enc_ctx->priv_data, "preset", "fast", 0);
    av_opt_set(enc_ctx->priv_data, "crf", "23", 0);
    
    avcodec_open2(enc_ctx, enc, nullptr);
    
    AVStream *out_v_stream = avformat_new_stream(ofmt_ctx, nullptr);
    out_video_idx = out_v_stream->index;
    avcodec_parameters_from_context(out_v_stream->codecpar, enc_ctx);
    out_v_stream->time_base = enc_ctx->time_base;

    // 滤镜图
    filter_graph = avfilter_graph_alloc();
    const AVFilter *buffersrc  = avfilter_get_by_name("buffer");
    const AVFilter *buffersink = avfilter_get_by_name("buffersink");
    char args[512];
    snprintf(args, sizeof(args), "video_size=%dx%d:pix_fmt=%d:time_base=%d/%d:pixel_aspect=%d/%d",
             dec_ctx->width, dec_ctx->height, dec_ctx->pix_fmt,
             in_v_stream->time_base.num, in_v_stream->time_base.den,
             dec_ctx->sample_aspect_ratio.num, dec_ctx->sample_aspect_ratio.den);
    avfilter_graph_create_filter(&buffersrc_ctx, buffersrc, "in", args, nullptr, filter_graph);
    avfilter_graph_create_filter(&buffersink_ctx, buffersink, "out", nullptr, nullptr, filter_graph);
    enum AVPixelFormat pix_fmts[] = { enc_ctx->pix_fmt, AV_PIX_FMT_NONE };
    av_opt_set_int_list(buffersink_ctx, "pix_fmts", pix_fmts, AV_PIX_FMT_NONE, AV_OPT_SEARCH_CHILDREN);

    AVFilterInOut *outputs = avfilter_inout_alloc();
    AVFilterInOut *inputs  = avfilter_inout_alloc();
    outputs->name       = av_strdup("in"); outputs->filter_ctx = buffersrc_ctx; outputs->pad_idx = 0; outputs->next = nullptr;
    inputs->name       = av_strdup("out"); inputs->filter_ctx = buffersink_ctx; inputs->pad_idx = 0; inputs->next = nullptr;
    
    std::string filter_str = "ass='" + subtitle_path + "'";
    avfilter_graph_parse_ptr(filter_graph, filter_str.c_str(), &inputs, &outputs, nullptr);
    avfilter_graph_config(filter_graph, nullptr);
    avfilter_inout_free(&inputs); avfilter_inout_free(&outputs);

    if (!(ofmt_ctx->oformat->flags & AVFMT_NOFILE)) avio_open(&ofmt_ctx->pb, temp_video_path.c_str(), AVIO_FLAG_WRITE);
    avformat_write_header(ofmt_ctx, nullptr);

    pkt = av_packet_alloc();
    enc_pkt = av_packet_alloc();
    frame = av_frame_alloc();
    filt_frame = av_frame_alloc();
    
    LOG_INF("Phase 1: Hardsubbing video stream...");
    int64_t v_pts_us = 0;
    
    while (av_read_frame(ifmt_ctx_v, pkt) >= 0) {
        if (pkt->stream_index == video_stream_idx) {
            avcodec_send_packet(dec_ctx, pkt);
            while (avcodec_receive_frame(dec_ctx, frame) >= 0) {
                av_buffersrc_add_frame_flags(buffersrc_ctx, frame, AV_BUFFERSRC_FLAG_KEEP_REF);
                while (av_buffersink_get_frame(buffersink_ctx, filt_frame) >= 0) {
                    v_pts_us = av_rescale_q(filt_frame->pts, in_v_stream->time_base, {1, AV_TIME_BASE});
                    avcodec_send_frame(enc_ctx, filt_frame);
                    while (avcodec_receive_packet(enc_ctx, enc_pkt) >= 0) {
                        av_packet_rescale_ts(enc_pkt, enc_ctx->time_base, out_v_stream->time_base);
                        enc_pkt->stream_index = out_video_idx;
                        av_interleaved_write_frame(ofmt_ctx, enc_pkt);
                        av_packet_unref(enc_pkt);
                    }
                    av_frame_unref(filt_frame);
                }
                av_frame_unref(frame);
            }
        }
        av_packet_unref(pkt);
        
        if (on_progress && ifmt_ctx_v->duration > 0) {
            int p = (v_pts_us * 90 / ifmt_ctx_v->duration);
            on_progress(std::min(90, std::max(0, p)), "Phase 1: Hardsub encoding...");
        }
    }

    av_buffersrc_add_frame_flags(buffersrc_ctx, nullptr, 0);
    while (av_buffersink_get_frame(buffersink_ctx, filt_frame) >= 0) {
        avcodec_send_frame(enc_ctx, filt_frame);
        while (avcodec_receive_packet(enc_ctx, enc_pkt) >= 0) {
            av_packet_rescale_ts(enc_pkt, enc_ctx->time_base, out_v_stream->time_base);
            enc_pkt->stream_index = out_video_idx;
            av_interleaved_write_frame(ofmt_ctx, enc_pkt);
            av_packet_unref(enc_pkt);
        }
        av_frame_unref(filt_frame);
    }
    avcodec_send_frame(enc_ctx, nullptr);
    while (avcodec_receive_packet(enc_ctx, enc_pkt) >= 0) {
        av_packet_rescale_ts(enc_pkt, enc_ctx->time_base, out_v_stream->time_base);
        enc_pkt->stream_index = out_video_idx;
        av_interleaved_write_frame(ofmt_ctx, enc_pkt);
        av_packet_unref(enc_pkt);
    }

    av_write_trailer(ofmt_ctx);
    
    if (pkt) av_packet_free(&pkt);
    if (enc_pkt) av_packet_free(&enc_pkt);
    if (frame) av_frame_free(&frame);
    if (filt_frame) av_frame_free(&filt_frame);
    if (dec_ctx) avcodec_free_context(&dec_ctx);
    if (enc_ctx) avcodec_free_context(&enc_ctx);
    if (filter_graph) avfilter_graph_free(&filter_graph);
    if (ifmt_ctx_v) avformat_close_input(&ifmt_ctx_v);
    if (ofmt_ctx) {
        if (!(ofmt_ctx->oformat->flags & AVFMT_NOFILE)) avio_closep(&ofmt_ctx->pb);
        avformat_free_context(ofmt_ctx);
    }

    // ==========================================================
    // 第二阶段：复用 MergeWorker 将处理好的视频与音频合并
    // ==========================================================
    LOG_INF("Phase 2: Muxing audio into temp video...");
    MergeWorker muxer;
    ret = muxer.run(temp_video_path, audio_path, output_path, [on_progress](int p, const std::string& msg) {
        if (on_progress) {
            // 将 MergeWorker 的进度 0-100 映射到主任务的 90-100
            on_progress(90 + (p / 10), "Phase 2: Muxing audio...");
        }
    });

    // 清理临时视频文件
    std::filesystem::remove(temp_video_path);

    if (ret == 0 && on_progress) on_progress(100, "done");
    return ret;
}

}  // namespace avsvc