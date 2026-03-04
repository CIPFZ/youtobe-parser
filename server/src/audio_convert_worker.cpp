#include "audio_convert_worker.h"
#include <filesystem>
#include <iostream>

#ifdef HAVE_FFMPEG
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libswresample/swresample.h>
#include <libavutil/opt.h>
}
#endif

namespace avsvc {

// 辅助清理函数 (保持逻辑一致)
#ifdef HAVE_FFMPEG
static void fast_cleanup(AVFormatContext* ifmt, AVFormatContext* ofmt, AVCodecContext* dec, AVCodecContext* enc, SwrContext* swr) {
    if (swr) swr_free(&swr);
    if (dec) avcodec_free_context(&dec);
    if (enc) avcodec_free_context(&enc);
    if (ifmt) avformat_close_input(&ifmt);
    if (ofmt) {
        if (!(ofmt->oformat->flags & AVFMT_NOFILE)) avio_closep(&ofmt->pb);
        avformat_free_context(ofmt);
    }
}
#endif

int AudioConvertWorker::run_m4a_to_wav(const std::string& input_path,
                                       const std::string& output_path,
                                       AudioConvertProgressCallback on_progress) const {
#ifdef HAVE_FFMPEG
    AVFormatContext *ifmt = nullptr, *ofmt = nullptr;
    AVCodecContext *dec_ctx = nullptr, *enc_ctx = nullptr;
    SwrContext *swr = nullptr;
    int audio_stream_idx = -1;

    // 1. 快速打开输入
    if (avformat_open_input(&ifmt, input_path.c_str(), nullptr, nullptr) < 0) return -1;
    avformat_find_stream_info(ifmt, nullptr);
    audio_stream_idx = av_find_best_stream(ifmt, AVMEDIA_TYPE_AUDIO, -1, -1, nullptr, 0);
    if (audio_stream_idx < 0) { fast_cleanup(ifmt, ofmt, dec_ctx, enc_ctx, swr); return -2; }

    // 2. 解码器初始化
    AVStream *in_stream = ifmt->streams[audio_stream_idx];
    const AVCodec *decoder = avcodec_find_decoder(in_stream->codecpar->codec_id);
    dec_ctx = avcodec_alloc_context3(decoder);
    avcodec_parameters_to_context(dec_ctx, in_stream->codecpar);
    avcodec_open2(dec_ctx, decoder, nullptr);

    // 3. 编码器初始化 (PCM S16LE)
    avformat_alloc_output_context2(&ofmt, nullptr, "wav", output_path.c_str());
    const AVCodec *encoder = avcodec_find_encoder(AV_CODEC_ID_PCM_S16LE);
    AVStream *out_stream = avformat_new_stream(ofmt, nullptr);
    enc_ctx = avcodec_alloc_context3(encoder);
    
    // 设置 Whisper 专用参数：16k, Mono, S16
    enc_ctx->sample_fmt = AV_SAMPLE_FMT_S16;
    enc_ctx->sample_rate = 16000;
    enc_ctx->channel_layout = AV_CH_LAYOUT_MONO;
    enc_ctx->channels = 1;
    enc_ctx->time_base = {1, 16000};
    avcodec_open2(enc_ctx, encoder, nullptr);
    avcodec_parameters_from_context(out_stream->codecpar, enc_ctx);

    // 4. 重采样初始化
    swr = swr_alloc_set_opts(nullptr, 
                             AV_CH_LAYOUT_MONO, AV_SAMPLE_FMT_S16, 16000,
                             dec_ctx->channel_layout ? dec_ctx->channel_layout : av_get_default_channel_layout(dec_ctx->channels),
                             dec_ctx->sample_fmt, dec_ctx->sample_rate, 0, nullptr);
    swr_init(swr);

    if (!(ofmt->oformat->flags & AVFMT_NOFILE)) avio_open(&ofmt->pb, output_path.c_str(), AVIO_FLAG_WRITE);
    avformat_write_header(ofmt, nullptr);

    // 5. 【核心加速】预分配一次性缓冲区
    AVFrame *frame = av_frame_alloc();
    AVFrame *resampled_frame = av_frame_alloc();
    AVPacket *pkt = av_packet_alloc();
    
    // 预设重采样帧参数，避免在循环内分配
    resampled_frame->sample_rate = enc_ctx->sample_rate;
    resampled_frame->channel_layout = enc_ctx->channel_layout;
    resampled_frame->format = enc_ctx->sample_fmt;

    int64_t pts = 0;
    
    // 6. 转换循环
    while (av_read_frame(ifmt, pkt) >= 0) {
        if (pkt->stream_index == audio_stream_idx) {
            if (avcodec_send_packet(dec_ctx, pkt) == 0) {
                while (avcodec_receive_frame(dec_ctx, frame) == 0) {
                    // 计算目标样本数
                    int dst_nb_samples = av_rescale_rnd(swr_get_delay(swr, dec_ctx->sample_rate) + frame->nb_samples, 
                                                        16000, dec_ctx->sample_rate, AV_ROUND_UP);
                    
                    // 仅当缓冲区不够大时才重新分配 (复用内存)
                    if (resampled_frame->nb_samples < dst_nb_samples) {
                        resampled_frame->nb_samples = dst_nb_samples;
                        av_frame_get_buffer(resampled_frame, 0);
                    }

                    int converted = swr_convert(swr, resampled_frame->data, dst_nb_samples, 
                                                (const uint8_t**)frame->extended_data, frame->nb_samples);
                    
                    if (converted > 0) {
                        resampled_frame->nb_samples = converted;
                        resampled_frame->pts = pts;
                        pts += converted;

                        if (avcodec_send_frame(enc_ctx, resampled_frame) == 0) {
                            AVPacket *out_pkt = av_packet_alloc();
                            while (avcodec_receive_packet(enc_ctx, out_pkt) == 0) {
                                out_pkt->stream_index = out_stream->index;
                                av_interleaved_write_frame(ofmt, out_pkt);
                                av_packet_unref(out_pkt);
                            }
                            av_packet_free(&out_pkt);
                        }
                    }
                }
            }
        }
        av_packet_unref(pkt);
    }

    // 7. 收尾
    av_write_trailer(ofmt);
    av_frame_free(&frame);
    av_frame_free(&resampled_frame);
    av_packet_free(&pkt);
    fast_cleanup(ifmt, ofmt, dec_ctx, enc_ctx, swr);

    if (on_progress) on_progress(100, "done");
    return 0;
#else
    return -100;
#endif
}

} // namespace avsvc