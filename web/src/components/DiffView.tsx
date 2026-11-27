// Loaded lazily: pulls in Monaco (bundled locally, never from a CDN).
import '../lib/monaco';
import { DiffEditor, type Monaco } from '@monaco-editor/react';
import { Spinner } from './ui';

const THEME = 'mytool-dark';

function defineTheme(monaco: Monaco): void {
  monaco.editor.defineTheme(THEME, {
    base: 'vs-dark',
    inherit: true,
    rules: [],
    colors: {
      'editor.background': '#0b0b10',
      'editorGutter.background': '#0b0b10',
      'editor.lineHighlightBackground': '#ffffff00',
      'diffEditor.insertedTextBackground': '#3ecf8e22',
      'diffEditor.removedTextBackground': '#f0554d22',
      'diffEditor.insertedLineBackground': '#3ecf8e12',
      'diffEditor.removedLineBackground': '#f0554d12',
      'editorLineNumber.foreground': '#4a4a58',
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
        fontSize: 12.5,
        fontFamily: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
        lineNumbersMinChars: 3,
        renderOverviewRuler: false,
        automaticLayout: true,
        padding: { top: 8, bottom: 8 },
        scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
      }}
    />
  );
}
