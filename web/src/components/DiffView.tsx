// Loaded lazily: pulls in Monaco (bundled locally, never from a CDN).
import '../lib/monaco';
import { DiffEditor, type Monaco } from '@monaco-editor/react';
import { Spinner } from './ui';

const THEME = 'mytool-paper';

function defineTheme(monaco: Monaco): void {
  monaco.editor.defineTheme(THEME, {
    base: 'vs',
    inherit: true,
    rules: [],
    colors: {
      'editor.background': '#ffffff',
      'editorGutter.background': '#fbfbfd',
      'editor.lineHighlightBackground': '#00000000',
      'diffEditor.insertedTextBackground': '#248a3d2e',
      'diffEditor.removedTextBackground': '#d700152e',
      'diffEditor.insertedLineBackground': '#eaf8ec',
      'diffEditor.removedLineBackground': '#ffecec',
      'diffEditor.diagonalFill': '#e5e5ea80',
      'editorLineNumber.foreground': '#8e8e93',
      'editorLineNumber.activeForeground': '#1c1c1e',
    },
  });
}

interface DiffViewProps {
  /** Stable per-suggestion key: Monaco models are cached under it and reused. */
  modelKey: string;
  original: string;
  modified: string;
  language: string;
}

export default function DiffView({ modelKey, original, modified, language }: DiffViewProps) {
  return (
    <DiffEditor
      original={original}
      modified={modified}
      language={language}
      originalModelPath={`inmemory://original/${modelKey}`}
      modifiedModelPath={`inmemory://modified/${modelKey}`}
      keepCurrentOriginalModel
      keepCurrentModifiedModel
      theme={THEME}
      beforeMount={defineTheme}
      loading={<Spinner className="size-5 text-muted" />}
      options={{
        readOnly: true,
        originalEditable: false,
        renderSideBySide: true,
        useInlineViewWhenSpaceIsLimited: true,
        renderSideBySideInlineBreakpoint: 520,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 13,
        lineHeight: 20,
        fontFamily: 'SF Mono, JetBrains Mono, ui-monospace, Menlo, Consolas, monospace',
        lineNumbersMinChars: 3,
        renderOverviewRuler: false,
        automaticLayout: true,
        padding: { top: 8, bottom: 8 },
        scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
      }}
    />
  );
}
