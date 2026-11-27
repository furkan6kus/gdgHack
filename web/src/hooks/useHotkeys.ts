import { useEffect, useRef } from 'react';

type HotkeyMap = Record<string, (e: KeyboardEvent) => void>;

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
}

/**
 * Global single-key shortcuts (keys as in KeyboardEvent.key, e.g. "j", " ").
 * Ignored while typing, with modifiers, inside Monaco, or when `enabled` is false.
 */
export function useHotkeys(map: HotkeyMap, enabled = true): void {
  const latest = useRef(map);
  useEffect(() => {
    latest.current = map;
  });

  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return;
      if (e.target instanceof HTMLElement && e.target.closest('.monaco-editor')) return;
      const handler = latest.current[e.key];
      if (!handler) return;
      e.preventDefault();
      handler(e);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [enabled]);
}
