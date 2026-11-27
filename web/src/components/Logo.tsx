import { motion } from 'framer-motion';

/** Verifix mark: an opening bracket and a check, cream on near-black. */
export function LogoMark({ size = 40, animate = false }: { size?: number; animate?: boolean }) {
  const draw = animate
    ? { initial: { pathLength: 0, opacity: 0 }, animate: { pathLength: 1, opacity: 1 } }
    : {};
  return (
    <svg width={size} height={size} viewBox="0 0 512 512" fill="none" aria-hidden>
      <rect width="512" height="512" rx="96" fill="#1c1b18" />
      <motion.path
        d="M174 132H130V380H174"
        stroke="#f3f0e6"
        strokeWidth="44"
        strokeLinecap="square"
        {...draw}
        transition={{ duration: 0.45, ease: 'easeOut' }}
      />
      <motion.path
        d="M204 290L244 330L370 128"
        stroke="#f3f0e6"
        strokeWidth="44"
        strokeLinecap="square"
        {...draw}
        transition={{ duration: 0.45, delay: animate ? 0.4 : 0, ease: 'easeOut' }}
      />
    </svg>
  );
}
