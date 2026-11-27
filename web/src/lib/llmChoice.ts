import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Effort, LLMChoice, ModelInfo } from '../api/types';
import { readJson, writeJson } from './storage';

const KEY = 'mytool.llm'; // storage key kept from the old name

export const EFFORT_LABELS: Record<Effort, string> = {
  low: 'Hızlı',
  medium: 'Dengeli',
  high: 'Derin',
};

/** The user's model + effort choice (remembered in the browser) and the model list with prices. */
export function useLLMChoice(): {
  choice: LLMChoice | null;
  models: ModelInfo[];
  setChoice: (next: LLMChoice) => void;
} {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [choice, setChoiceState] = useState<LLMChoice | null>(() => readJson<LLMChoice | null>(KEY, null));

  useEffect(() => {
    let alive = true;
    api
      .models()
      .then((res) => {
        if (!alive) return;
        setModels(res.models);
        setChoiceState((current) =>
          current && res.models.some((m) => m.id === current.model)
            ? current
            : { model: res.default_model, effort: res.default_effort },
        );
      })
      .catch(() => undefined); // the server default is used when the list is unavailable
    return () => {
      alive = false;
    };
  }, []);

  const setChoice = useCallback((next: LLMChoice) => {
    setChoiceState(next);
    writeJson(KEY, next);
  }, []);

  return { choice, models, setChoice };
}

export function formatUsd(value: number): string {
  if (value === 0) return '$0';
  return '$' + value.toFixed(value < 0.01 ? 4 : 2);
}
