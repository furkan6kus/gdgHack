import type { ErrorPayload, Suggestion } from '../../api/types';
import { Modal } from '../../components/Modal';
import { Button, Callout, INSET, Spinner } from '../../components/ui';

interface ConfirmApplyModalProps {
  suggestions: Suggestion[];
  root: string;
  applying: boolean;
  error: ErrorPayload | null;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmApplyModal({
  suggestions,
  root,
  applying,
  error,
  onConfirm,
  onClose,
}: ConfirmApplyModalProps) {
  const byFile = groupByFile(suggestions);
  const untested = suggestions.filter((s) => s.verification.tested === false).length;
  const footer = (
    <>
      <Button onClick={onClose} disabled={applying}>
        Vazgeç
      </Button>
      <Button variant="primary" onClick={onConfirm} disabled={applying || suggestions.length === 0}>
        {applying && <Spinner className="size-3.5" />}
        {suggestions.length} öneriyi uygula
      </Button>
    </>
  );
  return (
    <Modal
      open={suggestions.length > 0}
      title="Değişiklikleri uygula"
      onClose={applying ? () => undefined : onClose}
      footer={footer}
    >
      <div className="space-y-4 p-6 text-sm">
        <p className="leading-relaxed text-muted">
          Aşağıdaki <strong className="text-strong">{byFile.size}</strong> dosya değiştirilecek.
          Yalnızca doğrulaması geçen öneriler uygulanır.
        </p>
        <ul className={`${INSET} divide-y divide-border`}>
          {[...byFile].map(([file, items]) => (
            <li key={file} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className="min-w-0 truncate font-mono text-[12.5px] text-text">{file}</span>
              <span className="shrink-0 text-xs text-subtle">{items.length} öneri</span>
            </li>
          ))}
        </ul>
        {untested > 0 && (
          <Callout tone="warn" className="!p-3 text-xs">
            {untested} öneri testle doğrulanmadı: yalnız kodun derlendiği ve ruff'ın yeni hata
            bulmadığı denetlendi. Uygulamadan önce farkı gözden geçirin.
          </Callout>
        )}
        <Callout tone="info" className="flex gap-2.5 !p-3 text-xs">
          <span aria-hidden>⛁</span>
          <p className="min-w-0 break-words text-muted">
            Değişiklikten önce yedek alınır:{' '}
            <code className="font-mono text-text">{root}/.mytool/backup/</code>
          </p>
        </Callout>
        {error && (
          <Callout tone="err" className="!p-3 text-xs">
            {error.message}
          </Callout>
        )}
      </div>
    </Modal>
  );
}

function groupByFile(suggestions: Suggestion[]): Map<string, Suggestion[]> {
  const map = new Map<string, Suggestion[]>();
  for (const s of suggestions) {
    map.set(s.patch.file, [...(map.get(s.patch.file) ?? []), s]);
  }
  return map;
}
