import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, toErrorPayload } from '../../api/client';
import type { ApplyResponse, ChatEdit, ChatMessage, LLMChoice } from '../../api/types';
import { formatUsd } from '../../lib/llmChoice';
import { InlineCode } from '../../components/InlineCode';
import { Button, Callout, Spinner } from '../../components/ui';
import { lineDiff } from './lineDiff';

/** One chat turn as the UI keeps it (assistant turns may carry proposed edits). */
export interface ChatEntry {
  role: ChatMessage['role'];
  content: string;
  edits?: ChatEdit[];
  applied?: string[];
  error?: boolean;
  /** Estimated API cost of this answer (USD). */
  cost?: number | null;
}

interface ChatPanelProps {
  /** The analyzed path of the tab (folder or file). */
  path: string;
  /** File the conversation is about, relative like Finding.file. */
  file: string;
  entries: ChatEntry[];
  onEntries: (entries: ChatEntry[]) => void;
  onBusy: (busy: boolean) => void;
  onApplied: (response: ApplyResponse, explanation: string) => void;
  llm?: LLMChoice;
  onCost?: (cost: number | null | undefined) => void;
}

const EXAMPLES = [
  'Bu dosya ne yapıyor?',
  'Hatalı kısımları düzelt',
  'Fonksiyonlara açıklama satırı ekle',
];

export function ChatPanel({ path, file, entries, onEntries, onBusy, onApplied, llm, onCost }: ChatPanelProps) {
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [applying, setApplying] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [entries, sending]);

  const send = async (message: string) => {
    const content = message.trim();
    if (!content || sending) return;
    const next: ChatEntry[] = [...entries, { role: 'user', content }];
    onEntries(next);
    setText('');
    setSending(true);
    onBusy(true);
    try {
      const history = next.filter((e) => !e.error).map(({ role, content: c }) => ({ role, content: c }));
      const answer = await api.chat(path, file, history.slice(-20), llm);
      onCost?.(answer.estimated_cost_usd);
      onEntries([
        ...next,
        {
          role: 'assistant',
          content: answer.reply,
          edits: answer.edits,
          applied: [],
          cost: answer.estimated_cost_usd ?? null,
        },
      ]);
    } catch (err) {
      onEntries([...next, { role: 'assistant', content: toErrorPayload(err).message, error: true }]);
    } finally {
      setSending(false);
      onBusy(false);
    }
  };

  const apply = async (index: number, edit: ChatEdit) => {
    setApplying(edit.id);
    try {
      const response = await api.applyChatEdit(path, edit);
      onEntries(
        entries.map((e, i) => (i === index ? { ...e, applied: [...(e.applied ?? []), edit.id] } : e)),
      );
      onApplied(response, edit.explanation);
    } catch (err) {
      onEntries([...entries, { role: 'assistant', content: toErrorPayload(err).message, error: true }]);
    } finally {
      setApplying(null);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void send(text);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-auto p-4">
        {entries.length === 0 && (
          <div className="py-6 text-center">
            <p className="text-[15px] font-medium text-strong">
              <span className="font-mono">{file}</span> hakkında Claude ile konuşun
            </p>
            <p className="mt-1 text-[13px] text-subtle">
              Soru sorun ya da değişiklik isteyin; önerilen kod değişikliğini görüp tek tıkla uygularsınız.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => void send(example)}
                  className="rounded-full border border-border px-3 py-1 text-[13px] text-muted hover:bg-hover hover:text-strong focus-visible:outline-2 focus-visible:outline-accent"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}
        {entries.map((entry, index) =>
          entry.role === 'user' ? (
            <div key={index} className="flex justify-end">
              <p className="max-w-[85%] rounded-[var(--radius-sheet)] rounded-br-[4px] bg-accent px-3.5 py-2 text-sm whitespace-pre-wrap text-on-accent">
                {entry.content}
              </p>
            </div>
          ) : (
            <div key={index} className="max-w-[95%] space-y-2">
              <p
                className={`rounded-[var(--radius-sheet)] rounded-bl-[4px] px-3.5 py-2 text-sm leading-relaxed whitespace-pre-wrap ${entry.error ? 'bg-err-wash text-err-ink' : 'bg-sunken text-text'}`}
              >
                <InlineCode text={entry.content} />
              </p>
              {entry.cost != null && (
                <p className="pl-1 text-[11.5px] text-hint">Bu yanıtın tahmini ücreti {formatUsd(entry.cost)}</p>
              )}
              {entry.edits?.map((edit) => (
                <EditCard
                  key={edit.id}
                  edit={edit}
                  applied={entry.applied?.includes(edit.id) ?? false}
                  applying={applying === edit.id}
                  onApply={() => void apply(index, edit)}
                />
              ))}
            </div>
          ),
        )}
        {sending && (
          <p className="flex items-center gap-2 text-[13px] text-subtle">
            <Spinner className="size-3.5" /> Claude düşünüyor…
          </p>
        )}
        <div ref={end} />
      </div>
      <form onSubmit={submit} className="flex shrink-0 items-end gap-2 border-t border-border p-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void send(text);
            }
          }}
          rows={2}
          placeholder="Örn. hesapla fonksiyonuna sıfıra bölme kontrolü ekle"
          aria-label="Claude'a mesaj"
          className="min-h-10 flex-1 resize-none rounded-[var(--radius-control)] border border-border bg-panel px-3 py-2 text-sm text-strong outline-none placeholder:text-hint focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/25"
        />
        <Button type="submit" variant="primary" disabled={sending || text.trim() === ''}>
          Gönder
        </Button>
      </form>
    </div>
  );
}

function EditCard({
  edit,
  applied,
  applying,
  onApply,
}: {
  edit: ChatEdit;
  applied: boolean;
  applying: boolean;
  onApply: () => void;
}) {
  const diff = lineDiff(edit.original, edit.replacement);
  return (
    <div className="overflow-hidden rounded-[var(--radius-control)] border border-border bg-panel">
      <div className="flex items-center gap-3 px-3 py-2">
        <p className="min-w-0 flex-1 text-[13px] text-muted">
          <span className="font-mono text-[12px] text-strong">{edit.file}</span>
          {edit.explanation && <> — <InlineCode text={edit.explanation} /></>}
        </p>
        {applied ? (
          <span className="text-[13px] font-medium text-ok-ink">✓ Uygulandı</span>
        ) : (
          <Button size="sm" variant="primary" disabled={!edit.applicable || applying} onClick={onApply}>
            {applying && <Spinner className="size-3" />}
            Uygula
          </Button>
        )}
      </div>
      <pre className="max-h-64 overflow-auto border-t border-border bg-panel-2 py-1.5 font-mono text-[12px] leading-[1.7]">
        {diff.map((line, i) => (
          <div
            key={i}
            className={
              line.kind === 'del'
                ? 'bg-err-wash px-3 text-err-ink'
                : line.kind === 'add'
                  ? 'bg-ok-wash px-3 text-ok-ink'
                  : 'px-3 text-subtle'
            }
          >
            <span aria-hidden className="mr-3 inline-block w-2 select-none">
              {line.kind === 'del' ? '-' : line.kind === 'add' ? '+' : ' '}
            </span>
            {line.text || ' '}
          </div>
        ))}
      </pre>
      {edit.problem && (
        <Callout tone="warn" className="!rounded-none !py-2 text-[13px]">
          Uygulanamaz: {edit.problem}
        </Callout>
      )}
    </div>
  );
}
