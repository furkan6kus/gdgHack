// Bundle Monaco locally (never from a CDN) and keep it lean: the core editor API,
// the base editor worker, and syntax highlighting for the languages we diff.
// No TS/CSS/HTML/JSON language-service workers are pulled in.
import * as monaco from 'monaco-editor/editor/editor.api';
import EditorWorker from 'monaco-editor/editor/editor.worker?worker';
import 'monaco-editor/features/codicon/register'; // icon font for diff gutter/actions
import 'monaco-editor/languages/definitions/python/register';
import 'monaco-editor/languages/definitions/javascript/register';
import 'monaco-editor/languages/definitions/typescript/register';
import 'monaco-editor/languages/definitions/markdown/register';
import { loader } from '@monaco-editor/react';

self.MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

loader.config({ monaco });
