import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, type ReactNode } from 'react';

interface ModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}

export function Modal({ open, title, onClose, children, footer, width = 'max-w-lg' }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) onClose();
          }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className={`flex max-h-[85vh] w-full ${width} flex-col overflow-hidden rounded-xl border border-border bg-panel shadow-2xl shadow-black/60`}
            initial={{ opacity: 0, scale: 0.97, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 4 }}
            transition={{ duration: 0.16, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <h2 className="text-sm font-semibold">{title}</h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Kapat"
                className="rounded p-1 text-muted hover:bg-panel-2 hover:text-text"
              >
                ✕
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-auto">{children}</div>
            {footer && (
              <div className="flex items-center justify-end gap-2 border-t border-border bg-panel-2/40 px-5 py-3">
                {footer}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
