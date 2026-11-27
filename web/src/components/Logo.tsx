import { motion } from 'framer-motion';

/** Brackets around a scanning line that settles into a check mark. */
export function LogoMark({ size = 40, animate = false }: { size?: number; animate?: boolean }) {
  const draw = animate
    ? { initial: { pathLength: 0, opacity: 0 }, animate: { pathLength: 1, opacity: 1 } }
    : {};
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden>
      <rect x="1" y="1" width="46" height="46" rx="12" fill="url(#logo-bg)" stroke="#ffffff14" />
      <motion.path
        d="M17 14h-4v20h4M31 14h4v20h-4"
        stroke="#e2e8f0"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        {...draw}
        transition={{ duration: 0.55, ease: 'easeOut' }}
      />
      <motion.path
        d="M18.5 24.5l4 4 7.5-9"
        stroke="var(--color-accent)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        {...draw}
        transition={{ duration: 0.45, delay: animate ? 0.5 : 0, ease: 'easeOut' }}
      />
      <defs>
        <linearGradient id="logo-bg" x1="0" y1="0" x2="48" y2="48">
          <stop stopColor="#1a2130" />
          <stop offset="1" stopColor="#131822" />
        </linearGradient>
      </defs>
    </svg>
  );
}
