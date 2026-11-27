import type { FileSummary } from '../../api/types';
import { SEVERITY_LABELS, SEVERITY_ORDER, SEVERITY_TEXT } from '../../lib/labels';
import { basename } from './model';

interface FileListProps {
  files: FileSummary[];
  selected: string | null;
  onSelect: (path: string | null) => void;
}

export function FileList({ files, selected, onSelect }: FileListProps) {
  return (
    <nav className="flex h-full flex-col">
      <PanelTitle>
        Dosyalar <span className="text-muted/60">{files.length}</span>
      </PanelTitle>
      <ul className="min-h-0 flex-1 overflow-auto px-1.5 pb-2">
        <li>
          <FileButton active={selected === null} onClick={() => onSelect(null)}>
            <span className="text-sm">Tüm dosyalar</span>
          </FileButton>
        </li>
        {files.map((file) => (
          <li key={file.path}>
            <FileButton
              active={selected === file.path}
              onClick={() => onSelect(selected === file.path ? null : file.path)}
              title={file.path}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-[12.5px]">{basename(file.path)}</span>
                <span className="block truncate text-[10.5px] text-muted/70">
                  {file.path} · {file.line_count} satır
                </span>
              </span>
              <SeverityCounts counts={file.counts} />
            </FileButton>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function SeverityCounts({ counts }: { counts: FileSummary['counts'] }) {
  const visible = SEVERITY_ORDER.filter((s) => counts[s] > 0);
  if (visible.length === 0) return <span className="text-[11px] text-ok">✓</span>;
  return (
    <span className="flex shrink-0 gap-1.5 font-mono text-[11px]">
      {visible.map((s) => (
        <span key={s} className={SEVERITY_TEXT[s]} title={SEVERITY_LABELS[s]}>
          {counts[s]}
        </span>
      ))}
    </span>
  );
}

function FileButton({
  active,
  children,
  ...rest
}: {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      type="button"
      className={`flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left transition-colors ${active ? 'bg-accent-soft text-text' : 'text-muted hover:bg-panel-2 hover:text-text'}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function PanelTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="flex h-10 shrink-0 items-center gap-1.5 px-4 text-[11px] font-semibold tracking-wide text-muted uppercase">
      {children}
    </h2>
  );
}
