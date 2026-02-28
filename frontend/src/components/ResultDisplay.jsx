import React, { useState } from 'react';
import { Download, Clock, Eye, ThumbsUp, Calendar, Copy, Check, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
    return twMerge(clsx(inputs));
}

export const formatSize = (bytes) => {
    if (!bytes) return '—';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(2) + ' GB';
};

const formatDuration = (sec) => {
    if (!sec) return '';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return h > 0
        ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
        : `${m}:${String(s).padStart(2, '0')}`;
};

const formatCount = (n) => {
    if (n == null) return '';
    if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return String(n);
};

const formatDate = (dateStr) => {
    if (!dateStr || dateStr.length !== 8) return '';
    return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
};

const FormatTable = ({ formats }) => {
    const [copiedUrl, setCopiedUrl] = useState(null);

    const copyToClipboard = async (url) => {
        try {
            await navigator.clipboard.writeText(url);
            setCopiedUrl(url);
            setTimeout(() => setCopiedUrl(null), 2000);
        } catch (err) {
            window.open(url, '_blank');
        }
    };

    if (!formats || formats.length === 0) {
        return (
            <div className="py-8 text-center text-zinc-500 bg-zinc-900/30 rounded-xl border border-dashed border-zinc-800">
                No formats available for this video.
            </div>
        );
    }

    return (
        <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/30 backdrop-blur-md">
            <table className="w-full text-sm text-left">
                <thead className="text-xs uppercase bg-zinc-900/80 text-zinc-500 border-b border-zinc-800">
                    <tr>
                        <th className="px-5 py-4 font-semibold tracking-wider">Quality</th>
                        <th className="px-5 py-4 font-semibold tracking-wider">Type</th>
                        <th className="px-5 py-4 font-semibold tracking-wider">Ext</th>
                        <th className="px-5 py-4 font-semibold tracking-wider">Codec / FPS</th>
                        <th className="px-5 py-4 font-semibold tracking-wider">Size</th>
                        <th className="px-5 py-4 font-semibold tracking-wider text-right">Link</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/80">
                    {formats.map((f, i) => {
                        const isVA = f.type === 'video+audio';
                        const isV = f.type === 'video';
                        const codecDisplay = f.type === 'audio'
                            ? (f.acodec !== 'none' ? f.acodec : '')
                            : (f.vcodec !== 'none' ? `${f.vcodec}${f.fps ? ` (${f.fps}fps)` : ''}` : '');

                        return (
                            <tr key={i} className="hover:bg-zinc-800/30 transition-colors group">
                                <td className="px-5 py-3.5 font-medium text-zinc-200">{f.quality || f.format_id}</td>
                                <td className="px-5 py-3.5">
                                    <span className={cn(
                                        "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase border",
                                        isVA ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                                            isV ? "bg-blue-500/10 text-blue-400 border-blue-500/20" :
                                                "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                    )}>
                                        {f.type}
                                    </span>
                                </td>
                                <td className="px-5 py-3.5 text-zinc-500">{f.ext}</td>
                                <td className="px-5 py-3.5 text-zinc-500 text-xs">{codecDisplay}</td>
                                <td className="px-5 py-3.5 text-zinc-500 whitespace-nowrap">{formatSize(f.filesize)}</td>
                                <td className="px-5 py-3.5 text-right">
                                    <motion.button
                                        whileTap={{ scale: 0.9 }}
                                        onClick={() => copyToClipboard(f.url)}
                                        className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors"
                                        title="Copy Direct Link"
                                    >
                                        {copiedUrl === f.url ? <Check size={16} className="text-emerald-400" /> : <Copy size={16} />}
                                    </motion.button>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};

const VideoCard = ({ video, index }) => {
    const [descOpen, setDescOpen] = useState(false);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index ? index * 0.1 : 0.1, duration: 0.4 }}
            className="p-[1px] rounded-2xl bg-gradient-to-b from-zinc-800 to-zinc-900 shadow-xl overflow-hidden"
        >
            <div className="bg-zinc-950/80 backdrop-blur-2xl rounded-2xl p-6 sm:p-8 flex flex-col gap-8">
                {/* Meta Header */}
                <div className="flex flex-col md:flex-row gap-8">
                    <div className="w-full md:w-80 aspect-video rounded-xl bg-zinc-900 overflow-hidden flex-shrink-0 relative border border-zinc-800 shadow-md group">
                        {video.thumbnail ? (
                            <img src={video.thumbnail} alt={video.title} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-zinc-600 font-medium">No Thumbnail</div>
                        )}
                        {video.duration && (
                            <div className="absolute bottom-3 right-3 px-2 py-1 bg-black/80 backdrop-blur-md text-white text-xs font-bold rounded-lg shadow-sm">
                                {formatDuration(video.duration)}
                            </div>
                        )}
                    </div>

                    <div className="flex flex-col flex-1 min-w-0">
                        <h2 className="text-xl sm:text-2xl font-bold text-zinc-100 leading-snug mb-3 line-clamp-2" title={video.title}>
                            {video.title || 'Untitled Video'}
                        </h2>

                        <a href={video.author_url} target="_blank" rel="noreferrer" className="text-[#FF512F] hover:text-[#DD2476] transition-colors hover:underline font-semibold text-sm mb-5 inline-block w-fit">
                            {video.author || 'Unknown Channel'}
                        </a>

                        <div className="flex flex-wrap gap-2.5 mb-5">
                            {video.view_count && (
                                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-400">
                                    <Eye size={14} /> {formatCount(video.view_count)} views
                                </span>
                            )}
                            {video.like_count && (
                                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-400">
                                    <ThumbsUp size={14} /> {formatCount(video.like_count)}
                                </span>
                            )}
                            {video.upload_date && (
                                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-400">
                                    <Calendar size={14} /> {formatDate(video.upload_date)}
                                </span>
                            )}
                        </div>

                        {/* Description Toggle */}
                        <div className="mt-auto">
                            <button
                                onClick={() => setDescOpen(!descOpen)}
                                className="flex items-center gap-2 text-sm font-semibold text-zinc-500 hover:text-zinc-300 transition-colors"
                            >
                                <ChevronRight size={16} className={cn("transition-transform duration-300", descOpen ? "rotate-90" : "")} />
                                Video Description
                            </button>
                            <AnimatePresence>
                                {descOpen && (
                                    <motion.div
                                        initial={{ opacity: 0, height: 0 }}
                                        animate={{ opacity: 1, height: 'auto' }}
                                        exit={{ opacity: 0, height: 0 }}
                                        className="overflow-hidden"
                                    >
                                        <div className="mt-4 p-4 bg-zinc-900/50 rounded-xl text-xs text-zinc-400 whitespace-pre-wrap max-h-48 overflow-y-auto border border-zinc-800/50 leading-relaxed font-medium scrollbar-thin">
                                            {video.description || 'No description provided.'}
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    </div>
                </div>

                {/* Formats */}
                <div>
                    <h3 className="text-sm font-bold text-zinc-300 mb-4 flex items-center gap-2 uppercase tracking-wide">
                        <Download size={16} className="text-[#FF512F]" />
                        Direct Media Formats
                    </h3>
                    <FormatTable formats={video.formats} />
                </div>
            </div>
        </motion.div>
    );
};

const ResultDisplay = ({ singleResult, streamResults = [] }) => {
    // If we have stream results (playlist), show them all
    if (streamResults.length > 0) {
        return (
            <div className="flex flex-col gap-8 w-full pb-10">
                <AnimatePresence>
                    {streamResults.map((video, idx) => (
                        <VideoCard key={video.format_id || idx} video={video} index={idx} />
                    ))}
                </AnimatePresence>
            </div>
        );
    }

    // Otherwise, just a single result
    if (singleResult) {
        return (
            <div className="w-full pb-10">
                <VideoCard video={singleResult} index={0} />
            </div>
        );
    }

    return null;
};

export default ResultDisplay;
