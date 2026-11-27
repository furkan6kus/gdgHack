import type { ErrorPayload, Suggestion } from '../../api/types';
import { Modal } from '../../components/Modal';
import { Button, Kbd, Spinner } from '../../components/ui';

interface ApplyBarProps {
  checkedCount: number;
  applicableCount: number;
  onApplySelected: () => void;
  onApplyAll: () => void;
  onSelectNone: () => void;
}

export function ApplyBar({
  checkedCount,
  applicableCount,
  onApplySelected,
  onApplyAll,
  onSelectNone,
}: ApplyBarProps) {
  return (
    <footer className="flex h-14 shrink-0 items-center gap-3 border-t border-border bg-panel px-4">
      <span className="text-sm text-muted">
        {checkedCount > 0 ? (
          <>
            <span className="font-semibold text-text">{checkedCount}</span> öneri seçili
          </>
        ) : (
          'Uygulamak istediğiniz önerileri işaretleyin'
        )}
      </span>
      {checkedCount > 0 && (
        <Button size="sm" variant="ghost" onClick={onSelectNone}>
          Hiçbiri
        </Button>
      )}
      <span className="hidden items-center gap-1.5 text-[11px] text-muted/70 xl:flex">
        <Kbd>j</Kbd>
        <Kbd>k</Kbd> gezin · <Kbd>space</Kbd> seç
      </span>
      <div className="ml-auto flex gap-2">
        <Button onClick={onApplyAll} disabled={applicableCount === 0}>
          Tümünü uygula ({applicableCount})
        </Button>
        <Button variant="primary" onClick={onApplySelected} disabled={checkedCount === 0}>
          Seçilileri uygula
        </Button>
      </div>
    </footer>
  );
}

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
      <div className="space-y-4 px-5 py-4 text-sm">
        <p className="text-muted">
          Aşağıdaki <strong className="text-text">{byFile.size}</strong> dosya değiştirilecek.
          Yalnızca doğrulaması geçen öneriler uygulanır.
        </p>
        <ul className="divide-y divide-border rounded-lg border border-border">
          {[...byFile].map(([file, items]) => (
            <li key={file} className="flex items-center justify-between gap-3 px-3 py-2">
              <span className="truncate font-mono text-[12.5px]">{file}</span>
              <span className="shrink-0 text-xs text-muted">{items.length} öneri</span>
            </li>
          ))}
        </ul>
        <div className="flex gap-2.5 rounded-lg border border-accent/25 bg-accent-soft px-3 py-2.5 text-xs">
          <span aria-hidden>⛁</span>
          <p className="text-muted">
            Değişiklikten önce yedek alınır:{' '}
            <code className="font-mono text-text">{root}/.mytool/backup/</code>
          </p>
        </div>
        {error && <p className="text-xs text-err">{error.message}</p>}
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
