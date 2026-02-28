import React, { useState, useEffect } from 'react';
import { X, Globe, Plus, Trash2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const ProxyModal = ({ isOpen, onClose }) => {
    const [proxies, setProxies] = useState([]);
    const [newProxy, setNewProxy] = useState('');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState('');

    useEffect(() => {
        if (isOpen) {
            loadProxies();
            setMessage('');
            setNewProxy('');
        }
    }, [isOpen]);

    const loadProxies = async () => {
        try {
            const res = await fetch('/api/v1/proxies');
            const data = await res.json();
            setProxies(data.proxies || []);
        } catch (e) {
            console.error(e);
            setMessage({ text: 'Failed to load proxies', err: true });
        }
    };

    const showMsg = (msg, isErr = false) => {
        setMessage({ text: msg, err: isErr });
        setTimeout(() => setMessage(''), 3000);
    };

    const handleAdd = async () => {
        const url = newProxy.trim();
        if (!url) return;

        setLoading(true);
        try {
            const res = await fetch('/api/v1/proxies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ proxy_url: url })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail);

            showMsg('Proxy added successfully', false);
            setNewProxy('');
            loadProxies();
        } catch (e) {
            showMsg(e.message, true);
        } finally {
            setLoading(false);
        }
    };

    const handleRemove = async (url) => {
        try {
            const res = await fetch('/api/v1/proxies', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ proxy_url: url })
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail);
            }
            loadProxies();
        } catch (e) {
            showMsg(e.message, true);
        }
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                    />

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 10 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 10 }}
                        className="relative w-full max-w-lg p-[1px] bg-gradient-to-b from-zinc-700 to-zinc-800 rounded-2xl shadow-2xl"
                    >
                        <div className="bg-zinc-950 rounded-2xl flex flex-col max-h-[85vh] overflow-hidden">
                            {/* Header */}
                            <div className="flex items-center justify-between p-6 bg-zinc-900/50 border-b border-zinc-800/80">
                                <div className="flex items-center gap-3">
                                    <Globe className="text-zinc-400" size={22} />
                                    <h2 className="text-lg font-bold text-zinc-100">CORS Proxies</h2>
                                </div>
                                <button
                                    onClick={onClose}
                                    className="p-2 text-zinc-500 hover:text-zinc-100 hover:bg-zinc-800 rounded-lg transition-colors"
                                >
                                    <X size={20} />
                                </button>
                            </div>

                            {/* Content */}
                            <div className="p-6 flex-1 overflow-y-auto">
                                <div className="flex gap-3 mb-2">
                                    <input
                                        type="text"
                                        placeholder="http://user:pass@127.0.0.1:1080"
                                        value={newProxy}
                                        onChange={e => setNewProxy(e.target.value)}
                                        className="flex-1 px-4 py-3 rounded-xl border border-zinc-800 bg-zinc-900 text-zinc-100 placeholder-zinc-600 focus:border-[#FF512F]/50 focus:ring-1 focus:ring-[#FF512F]/50 transition-all font-medium"
                                        onKeyDown={e => e.key === 'Enter' && handleAdd()}
                                    />
                                    <motion.button
                                        whileHover={{ scale: 1.02 }}
                                        whileTap={{ scale: 0.98 }}
                                        onClick={handleAdd}
                                        disabled={loading || !newProxy.trim()}
                                        className="flex items-center justify-center gap-2 bg-zinc-100 hover:bg-white text-zinc-950 px-6 py-3 rounded-xl font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <Plus size={18} />
                                        Add
                                    </motion.button>
                                </div>

                                <AnimatePresence>
                                    {message.text && (
                                        <motion.div
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: 'auto' }}
                                            exit={{ opacity: 0, height: 0 }}
                                            className="overflow-hidden"
                                        >
                                            <div className={`mt-3 px-4 py-3 rounded-xl border text-sm font-medium ${message.err ? 'text-red-400 bg-red-950/30 border-red-900/50' : 'text-emerald-400 bg-emerald-950/30 border-emerald-900/50'}`}>
                                                {message.text}
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>

                                <div className="mt-8">
                                    <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                                        Active Proxies
                                        <span className="bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded-full text-[10px]">{proxies.length}</span>
                                    </h3>

                                    {proxies.length === 0 ? (
                                        <div className="text-center py-10 text-zinc-500 text-sm border-2 border-dashed border-zinc-800/50 rounded-xl bg-zinc-900/20 font-medium">
                                            No proxies configured.<br />Direct connection defaults will apply.
                                        </div>
                                    ) : (
                                        <ul className="flex flex-col gap-3">
                                            <AnimatePresence>
                                                {proxies.map(p => (
                                                    <motion.li
                                                        key={p}
                                                        initial={{ opacity: 0, y: -10 }}
                                                        animate={{ opacity: 1, y: 0 }}
                                                        exit={{ opacity: 0, scale: 0.95 }}
                                                        className="flex items-center justify-between bg-zinc-900 border border-zinc-800/80 p-3.5 rounded-xl group hover:border-zinc-700 transition-colors"
                                                    >
                                                        <span className="text-sm break-all text-zinc-300 font-mono tracking-tight">{p}</span>
                                                        <button
                                                            onClick={() => handleRemove(p)}
                                                            className="text-zinc-500 hover:text-red-400 p-2 rounded-lg hover:bg-red-500/10 transition-colors"
                                                            title="Delete proxy"
                                                        >
                                                            <Trash2 size={18} />
                                                        </button>
                                                    </motion.li>
                                                ))}
                                            </AnimatePresence>
                                        </ul>
                                    )}
                                </div>
                            </div>
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
};

export default ProxyModal;
