import { Fragment } from 'react';

/** Renders `backtick` spans of a message as inline code, the rest as plain text. */
export function InlineCode({ text }: { text: string }) {
  const parts = text.split('`');
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 && i < parts.length - 1 ? (
          <code key={i} className="rounded-[3px] bg-sunken px-1 py-px font-mono text-[0.92em] text-strong">
            {part}
          </code>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}
