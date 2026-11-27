// Loaded lazily: pulls in Monaco (bundled locally, never from a CDN).
import '../lib/monaco';
import Editor, { type Monaco, type OnMount } from '@monaco-editor/react';
import { useEffect, useRef } from 'react';
import { Spinner } from './ui';

const THEME = 'mytool-light';

export interface LineMark {
  line: number;
  /** "suggestion": a fix is ready here; "warn": a finding without a fix. */
  kind: 'suggestion' | 'warn';
  label: string;
}

interface CodeViewProps {
  path: string;
  source: string;
  language: string;
  marks: LineMark[];
  /** Line to scroll to and highlight (the selected finding). */
  focusLine: number | null;
}

type EditorInstance = Parameters<OnMount>[0];

function defineTheme(monaco: Monaco): void {
  monaco.editor.defineTheme(THEME, {
    base: 'vs',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '8e8e93', fontStyle: 'italic' },
      { token: 'string', foreground: 'c41a16' },
      { token: 'keyword', foreground: 'ad3da4' },
      { token: 'number', foreground: '1c00cf' },
    ],
    colors: {
      'editor.background': '#ffffff',
      'editorGutter.background': '#ffffff',
      'editor.lineHighlightBackground': '#00000000',
      'editor.lineHighlightBorder': '#00000000',
      'editorLineNumber.foreground': '#c7c7cc',
      'editorLineNumber.activeForeground': '#8e8e93',
    },
  });
}

/** Read-only view of the analyzed file with the lines that have findings marked. */
export default function CodeView({ path, source, language, marks, focusLine }: CodeViewProps) {
  const editorRef = useRef<EditorInstance | null>(null);
  const decorations = useRef<ReturnType<EditorInstance['createDecorationsCollection']> | null>(null);

  const paint = () => {
    const editor = editorRef.current;
    if (!editor) return;
    const model = editor.getModel();
    if (!model) return;
    const lines = model.getLineCount();
    // One badge per line: several findings on a line share the first label.
    const seen = new Set<number>();
    const items = marks
      .filter((mark) => mark.line >= 1 && mark.line <= lines && !seen.has(mark.line) && seen.add(mark.line))
      .map((mark) => ({
      // The range must end at the line end so the badge is injected after the code.
      range: {
        startLineNumber: mark.line,
        startColumn: 1,
        endLineNumber: mark.line,
        endColumn: model.getLineMaxColumn(mark.line),
      },
      options: {
        isWholeLine: true,
        className:
          mark.line === focusLine
            ? 'mt-line-selected'
            : mark.kind === 'suggestion'
              ? 'mt-line-suggestion'
              : 'mt-line-warn',
        after: {
          content: mark.label,
          inlineClassName: mark.kind === 'suggestion' ? 'mt-line-badge' : 'mt-line-badge-warn',
        },
      },
    }));
    if (decorations.current) decorations.current.set(items);
    else decorations.current = editor.createDecorationsCollection(items);
    if (focusLine) editor.revealLineInCenterIfOutsideViewport(focusLine);
  };

  // Repaint whenever the marks, the focus or the file change.
  useEffect(paint);

  return (
    <Editor
      path={`inmemory://source/${path}`}
      value={source}
      language={language}
      theme={THEME}
      beforeMount={defineTheme}
      onMount={(editor) => {
        editorRef.current = editor;
        decorations.current = null;
        paint();
      }}
      loading={<Spinner className="size-5 text-subtle" />}
      options={{
        readOnly: true,
        domReadOnly: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 13,
        lineHeight: 22,
        fontFamily: 'SF Mono, JetBrains Mono, ui-monospace, Menlo, Consolas, monospace',
        lineNumbersMinChars: 3,
        renderLineHighlight: 'none',
        overviewRulerLanes: 0,
        hideCursorInOverviewRuler: true,
        folding: false,
        glyphMargin: false,
        automaticLayout: true,
        padding: { top: 12, bottom: 12 },
        scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
        contextmenu: false,
      }}
    />
  );
}
