import React, { useState, useRef } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const ParserForm = ({ onStart, onSuccess, onStreamItem, onStreamComplete, onError, isLoading }) => {
    const [url, setUrl] = useState('');

    // Ref to hold the active EventSource
    const eventSourceRef = useRef(null);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!url.trim() || isLoading) return;

        onStart();

        // Determine if it looks like a playlist
        const isPlaylist = url.includes('list=');

        if (isPlaylist) {
            startStreamParse(url);
        } else {
            startSingleParse(url);
        }
    };

    const startSingleParse = async (videoUrl) => {
        try {
            const res = await fetch('/api/v1/parse', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_url: videoUrl })
            });
            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || 'Failed to parse video');
            }

            onSuccess(data);
        } catch (err) {
            onError(err.message);
        }
    };

    const startStreamParse = (videoUrl) => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        const sseUrl = `/api/v1/parse-stream?video_url=${encodeURIComponent(videoUrl)}`;
        const es = new EventSource(sseUrl);
        eventSourceRef.current = es;

        es.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.error) {
                    onError(data.error);
                    es.close();
                    onStreamComplete();
                } else if (data === "done") {
                    es.close();
                    onStreamComplete();
                } else {
                    onStreamItem(data);
                }
            } catch (e) {
                console.error("Error parsing stream event: ", e);
            }
        };

        es.onerror = (err) => {
            // EventSource doesn't provide much detail on failure. Try to gracefully terminate.
            console.error("EventSource failed:", err);
            // Wait to see if it autoreconnects, or close it if stream actually ended
            if (es.readyState === EventSource.CLOSED) {
                onStreamComplete();
            }
        };
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="p-[1px] rounded-2xl bg-gradient-to-b from-zinc-800 to-zinc-900 shadow-2xl overflow-hidden"
        >
            <div className="bg-zinc-950/80 backdrop-blur-2xl rounded-2xl p-6 sm:p-8">
                <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-4">
                    <div className="relative flex-1 group">
                        <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none">
                            <Search size={22} className="text-zinc-500 group-focus-within:text-[#FF512F] transition-colors" />
                        </div>
                        <input
                            type="url"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="Paste YouTube or Playlist URL..."
                            required
                            className="w-full pl-14 pr-4 py-4 bg-zinc-900/50 border border-zinc-800 rounded-xl text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-[#FF512F]/50 focus:ring-1 focus:ring-[#FF512F]/50 transition-all font-medium sm:text-lg"
                            autoComplete="off"
                            disabled={isLoading}
                        />
                    </div>
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        type="submit"
                        disabled={isLoading || !url.trim()}
                        className="group relative flex items-center justify-center gap-3 px-8 py-4 bg-zinc-100 hover:bg-white text-zinc-950 font-bold rounded-xl transition-all disabled:opacity-70 disabled:hover:scale-100 disabled:cursor-not-allowed overflow-hidden shadow-[0_0_20px_rgba(255,255,255,0.05)]"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 size={20} className="animate-spin text-zinc-600" />
                                <span>Processing...</span>
                            </>
                        ) : (
                            <span>Extract Data</span>
                        )}
                    </motion.button>
                </form>

                <AnimatePresence>
                    {isLoading && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="overflow-hidden"
                        >
                            <div className="mt-6 flex items-center gap-3 text-sm text-zinc-400">
                                <div className="w-2 h-2 rounded-full bg-[#FF512F] animate-pulse" />
                                <span>Connecting to network and extracting available media formats...</span>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    );
};

export default ParserForm;
