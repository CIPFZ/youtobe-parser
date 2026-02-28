import React, { useState } from 'react';
import { Youtube, Settings2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ProxyModal from './components/ProxyModal';
import ParserForm from './components/ParserForm';
import ResultDisplay from './components/ResultDisplay';

function App() {
  const [isProxyModalOpen, setIsProxyModalOpen] = useState(false);
  const [parseResult, setParseResult] = useState(null);
  const [playlistStream, setPlaylistStream] = useState([]);
  const [isParsing, setIsParsing] = useState(false);
  const [error, setError] = useState('');

  const handleParseStart = () => {
    setIsParsing(true);
    setError('');
    setParseResult(null);
    setPlaylistStream([]);
  };

  const handleParseSuccess = (data) => {
    setParseResult(data);
    setIsParsing(false);
  };

  const handleStreamItem = (item) => {
    setPlaylistStream(prev => [...prev, item]);
  };

  const handleStreamComplete = () => {
    setIsParsing(false);
  };

  const handleError = (msg) => {
    setError(msg);
    setIsParsing(false);
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col items-center p-4 sm:p-8 relative overflow-hidden">
      {/* Dynamic background glow */}
      <div className="absolute top-0 inset-x-0 h-[500px] bg-gradient-to-b from-[#FF512F]/10 to-transparent pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-5xl relative z-10"
      >
        {/* Header */}
        <header className="flex justify-between items-center mb-12 mt-2 sm:mt-6">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-[#FF512F] to-[#DD2476] flex items-center justify-center shadow-[0_0_30px_rgba(221,36,118,0.3)] border border-white/10">
              <Youtube className="text-white" size={30} strokeWidth={1.5} />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
                RPD Parser
              </h1>
              <p className="text-zinc-400 text-sm font-medium mt-0.5">Media & Metadata Extractor</p>
            </div>
          </div>

          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsProxyModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/80 backdrop-blur-md transition-colors text-sm font-medium shadow-sm hover:border-zinc-700 hover:text-white text-zinc-300"
          >
            <Settings2 size={18} />
            <span className="hidden sm:inline">Proxies</span>
          </motion.button>
        </header>

        {/* Main Content Area */}
        <main className="flex flex-col gap-8">
          <ParserForm
            onStart={handleParseStart}
            onSuccess={handleParseSuccess}
            onStreamItem={handleStreamItem}
            onStreamComplete={handleStreamComplete}
            onError={handleError}
            isLoading={isParsing}
          />

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="p-4 rounded-xl bg-red-950/30 border border-red-900/50 text-red-400 font-medium text-sm flex items-center gap-3 backdrop-blur-sm mt-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                  {error}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <ResultDisplay
            singleResult={parseResult}
            streamResults={playlistStream}
          />
        </main>
      </motion.div>

      <ProxyModal
        isOpen={isProxyModalOpen}
        onClose={() => setIsProxyModalOpen(false)}
      />
    </div>
  )
}

export default App;
