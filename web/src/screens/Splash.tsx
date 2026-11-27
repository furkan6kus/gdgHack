import { motion } from 'framer-motion';
import { useEffect } from 'react';
import { LogoMark } from '../components/Logo';
import { APP_NAME, SPLASH_MS } from '../config';

export function Splash({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onDone, SPLASH_MS);
    const skip = () => onDone();
    window.addEventListener('keydown', skip);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('keydown', skip);
    };
  }, [onDone]);

  return (
    <motion.div
      className="flex h-full cursor-pointer flex-col items-center justify-center gap-6"
      onClick={onDone}
      exit={{ opacity: 0, scale: 1.02 }}
      transition={{ duration: 0.25 }}
    >
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      >
        <LogoMark size={88} animate />
      </motion.div>
      <motion.div
        className="text-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6, duration: 0.3 }}
      >
        <p className="text-3xl font-semibold text-strong">{APP_NAME}</p>
        <p className="mt-1 text-sm text-muted">Kodundaki sorunu bulur, Türkçe anlatır, düzeltir.</p>
      </motion.div>
      <motion.p
        className="absolute bottom-10 text-[13px] text-subtle"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9 }}
      >
        Geçmek için herhangi bir tuşa basın
      </motion.p>
    </motion.div>
  );
}
