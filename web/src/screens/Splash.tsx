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
      <div className="pointer-events-none absolute size-[420px] rounded-full bg-accent/10 blur-[100px]" />
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      >
        <LogoMark size={88} animate />
      </motion.div>
      <div className="flex font-sans text-3xl font-bold tracking-tight text-strong" aria-label={APP_NAME}>
        {APP_NAME.split('').map((char, i) => (
          <motion.span
            key={i}
            initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{ delay: 0.55 + i * 0.05, duration: 0.3 }}
          >
            {char}
          </motion.span>
        ))}
      </div>
      <motion.p
        className="absolute bottom-10 text-xs text-muted"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9 }}
      >
        Geçmek için herhangi bir tuşa basın
      </motion.p>
    </motion.div>
  );
}
