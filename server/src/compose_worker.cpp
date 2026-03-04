#include "compose_worker.h"
#include <iostream>
#include <filesystem>

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavfilter/buffersink.h>
#include <libavfilter/buffersrc.h>
#include <libavfilter/avfilter.h>
#include <libavutil/opt.h>
}

#define LOG_INF(msg) std::cout << "[ComposeWorker][INFO] " << msg << std::endl
#define LOG_ERR(msg) std::cerr << "[ComposeWorker][ERROR] " << msg << std::endl

namespace avsvc {

int ComposeWorker::run(const std::string& video_path,
                       const std::string& audio_path,
                       const std::string& subtitle_path,
                       const std::string& output_path,
                       ComposeProgressCallback on_progress) const {
    
    int ret = 0;
    AVFormatContext *ifmt_v = nullptr, *ifmt_a = nullptr, *ofmt = nullptr;
    AVCodecContext *dec_ctx = nullptr, *enc_ctx = nullptr;
    AVFilterGraph *fg = nullptr;
    AVFilterContext *src_ctx = nullptr, *snk_ctx = nullptr;
    AVPacket *pkt = av_packet_alloc(), *out_pkt = av_packet_alloc();
    AVFrame *frame = av_frame_alloc(), *filt_frame = av_frame_alloc();

    // 1. 打开输入
    if (avformat_open_input(&ifmt_v, video_path.c_str(), nullptr, nullptr) < 0) return -1;
    avformat_find_stream_info(ifmt_v, nullptr);
    if (avformat_open_input(&ifmt_a, audio_path.c_str(), nullptr, nullptr) < 0) return -2;
    avformat_find_stream_info(ifmt_a, nullptr);

    int v_idx = av_find_best_stream(ifmt_v, AVMEDIA_TYPE_VIDEO, -1, -1, nullptr, 0);
    int a_idx = av_find_best_stream(ifmt_a, AVMEDIA_TYPE_AUDIO, -1, -1, nullptr, 0);

    // 2. 配置解码器
    const AVCodec *dec = avcodec_find_decoder(ifmt_v->streams[v_idx]->codecpar->codec_id);
    dec_ctx = avcodec_alloc_context3(dec);
    avcodec_parameters_to_context(dec_ctx, ifmt_v->streams[v_idx]->codecpar);
    avcodec_open2(dec_ctx, dec, nullptr);

    // 3. 配置编码器 (优化体积)
    avformat_alloc_output_context2(&ofmt, nullptr, "mp4", output_path.c_str());
    const AVCodec *enc = avcodec_find_encoder(AV_CODEC_ID_H264);
    enc_ctx = avcodec_alloc_context3(enc);
    enc_ctx->height = dec_ctx->height;
    enc_ctx->width = dec_ctx->width;
    enc_ctx->pix_fmt = AV_PIX_FMT_YUV420P;
    AVRational fps = av_guess_frame_rate(ifmt_v, ifmt_v->streams[v_idx], nullptr);
    enc_ctx->time_base = av_inv_q(fps);
    enc_ctx->framerate = fps;
    
    // 关键优化：控制码率和质量平衡
    av_opt_set(enc_ctx->priv_data, "preset", "medium", 0); 
    av_opt_set(enc_ctx->priv_data, "crf", "26", 0); // CRF 26 能显著减小体积
    if (ofmt->oformat->flags & AVFMT_GLOBALHEADER) enc_ctx->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
    avcodec_open2(enc_ctx, enc, nullptr);

    // 4. 设置输出流
    AVStream *out_v = avformat_new_stream(ofmt, nullptr);
    avcodec_parameters_from_context(out_v->codecpar, enc_ctx);
    AVStream *out_a = avformat_new_stream(ofmt, nullptr);
    avcodec_parameters_copy(out_a->codecpar, ifmt_a->streams[a_idx]->codecpar);
    out_a->codecpar->codec_tag = 0;

    // 5. 滤镜图处理 (硬字幕)
    fg = avfilter_graph_alloc();
    char args[512];
    snprintf(args, sizeof(args), "video_size=%dx%d:pix_fmt=%d:time_base=%d/%d:pixel_aspect=%d/%d",
             dec_ctx->width, dec_ctx->height, dec_ctx->pix_fmt, 
             enc_ctx->time_base.num, enc_ctx->time_base.den,
             dec_ctx->sample_aspect_ratio.num, dec_ctx->sample_aspect_ratio.den);
    avfilter_graph_create_filter(&src_ctx, avfilter_get_by_name("buffer"), "in", args, nullptr, fg);
    avfilter_graph_create_filter(&snk_ctx, avfilter_get_by_name("buffersink"), "out", nullptr, nullptr, fg);
    
    AVFilterInOut *outputs = avfilter_inout_alloc();
    AVFilterInOut *inputs  = avfilter_inout_alloc();
    outputs->name = av_strdup("in"); outputs->filter_ctx = src_ctx; outputs->pad_idx = 0; outputs->next = nullptr;
    inputs->name = av_strdup("out"); inputs->filter_ctx = snk_ctx; inputs->pad_idx = 0; inputs->next = nullptr;
    
    // 允许通过环境变量指定字体路径
    std::string filter_descr = "ass=filename='" + subtitle_path + "'";
    avfilter_graph_parse_ptr(fg, filter_descr.c_str(), &inputs, &outputs, nullptr);
    avfilter_graph_config(fg, nullptr);

    // 6. 写入头
    if (!(ofmt->oformat->flags & AVFMT_NOFILE)) avio_open(&ofmt->pb, output_path.c_str(), AVIO_FLAG_WRITE);
    avformat_write_header(ofmt, nullptr);

    // 7. 处理循环 (使用交织同步)
    bool video_done = false, audio_done = false;
    int64_t last_v_pts = 0;

    while (!video_done || !audio_done) {
        int stream_select = 0; // 0: video, 1: audio
        if (!video_done && !audio_done) {
            // 比较 PTS 决定读取哪个流
            if (av_compare_ts(last_v_pts, out_v->time_base, ifmt_a->streams[a_idx]->cur_dts, ifmt_a->streams[a_idx]->time_base) > 0)
                stream_select = 1;
        } else if (video_done) stream_select = 1;

        if (stream_select == 0) { // Video
            if (av_read_frame(ifmt_v, pkt) < 0) { video_done = true; av_packet_unref(pkt); continue; }
            if (pkt->stream_index == v_idx) {
                avcodec_send_packet(dec_ctx, pkt);
                while (avcodec_receive_frame(dec_ctx, frame) >= 0) {
                    av_buffersrc_add_frame_flags(src_ctx, frame, AV_BUFFERSRC_FLAG_KEEP_REF);
                    while (av_buffersink_get_frame(snk_ctx, filt_frame) >= 0) {
                        avcodec_send_frame(enc_ctx, filt_frame);
                        while (avcodec_receive_packet(enc_ctx, out_pkt) >= 0) {
                            av_packet_rescale_ts(out_pkt, enc_ctx->time_base, out_v->time_base);
                            out_pkt->stream_index = out_v->index;
                            last_v_pts = out_pkt->pts;
                            av_interleaved_write_frame(ofmt, out_pkt);
                            av_packet_unref(out_pkt);
                        }
                        av_frame_unref(filt_frame);
                    }
                    av_frame_unref(frame);
                }
            }
            av_packet_unref(pkt);
        } else { // Audio
            if (av_read_frame(ifmt_a, pkt) < 0) { audio_done = true; av_packet_unref(pkt); continue; }
            if (pkt->stream_index == a_idx) {
                av_packet_rescale_ts(pkt, ifmt_a->streams[a_idx]->time_base, out_a->time_base);
                pkt->stream_index = out_a->index;
                av_interleaved_write_frame(ofmt, pkt);
            }
            av_packet_unref(pkt);
        }
    }

    av_write_trailer(ofmt);
    // 释放资源... (代码省略)
    LOG_INF("Compose done.");
    return 0;
}
}