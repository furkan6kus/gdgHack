import { AnimatePresence, motion } from 'framer-motion';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { api, toErrorPayload } from './api/client';
import { ERROR_CODES, type AnalyzeResult, type ErrorPayload, type HealthResponse } from './api/types';
import { ApiKeyMissingHelp, StateMessage } from './components/StateMessage';
import { Button } from './components/ui';
import { AnalyzingScreen } from './screens/AnalyzingScreen';
import { HomeScreen } from './screens/HomeScreen';
import { ResultsScreen } from './screens/results/ResultsScreen';
import { Splash } from './screens/Splash';

type Screen =
  | { name: 'splash' }
  | { name: 'home' }
  | { name: 'analyzing'; jobId: string; path: string; verify: boolean }
  | { name: 'results'; jobId: string; result: AnalyzeResult }
  | { name: 'error'; error: ErrorPayload };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'splash' });
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<ErrorPayload | null>(null);
  const [startError, setStartError] = useState<ErrorPayload | null>(null);
  const [starting, setStarting] = useState(false);

  const refreshHealth = useCallback(() => {
    api
      .health()
      .then((h) => {
        setHealth(h);
        setHealthError(null);
      })
      .catch((err: unknown) => setHealthError(toErrorPayload(err)));
  }, []);

  useEffect(refreshHealth, [refreshHealth]);

  const goHome = useCallback(() => {
    setStartError(null);
    setScreen({ name: 'home' });
    refreshHealth();
  }, [refreshHealth]);

  const start = async (path: string, verify: boolean) => {
    setStarting(true);
    setStartError(null);
    try {
      const { job_id } = await api.startAnalyze(path, verify);
      setScreen({ name: 'analyzing', jobId: job_id, path, verify });
    } catch (err) {
      setStartError(toErrorPayload(err));
    } finally {
      setStarting(false);
    }
  };

  const onAnalysisError = useCallback(
    (error: ErrorPayload) => {
      if (error.code === ERROR_CODES.cancelled) goHome();
      else setScreen({ name: 'error', error });
    },
    [goHome],
  );

  const onAnalysisResult = useCallback((result: AnalyzeResult) => {
    setScreen((s) => (s.name === 'analyzing' ? { name: 'results', jobId: s.jobId, result } : s));
  }, []);

  const onSplashDone = useCallback(() => setScreen({ name: 'home' }), []);

  return (
    <div className="h-full overflow-hidden">
      <AnimatePresence mode="wait">
        {screen.name === 'splash' && <Splash key="splash" onDone={onSplashDone} />}
        {screen.name === 'home' && (
          <Fade key="home">
            <HomeScreen
              health={health}
              healthError={healthError}
              startError={startError}
              starting={starting}
              onStart={start}
            />
          </Fade>
        )}
        {screen.name === 'analyzing' && (
          <Fade key={`analyzing-${screen.jobId}`}>
            <AnalyzingScreen
              jobId={screen.jobId}
              path={screen.path}
              verify={screen.verify}
              onResult={onAnalysisResult}
              onError={onAnalysisError}
              onCancel={() => void api.cancelAnalyze(screen.jobId)}
            />
          </Fade>
        )}
        {screen.name === 'results' && (
          <Fade key={`results-${screen.jobId}`}>
            <ResultsScreen jobId={screen.jobId} result={screen.result} onNewAnalysis={goHome} />
          </Fade>
        )}
        {screen.name === 'error' && (
          <Fade key="error">
            <ErrorScreen error={screen.error} onBack={goHome} />
          </Fade>
        )}
      </AnimatePresence>
    </div>
  );
}

function Fade({ children }: { children: ReactNode }) {
  return (
    <motion.div
      className="h-full"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
    >
      {children}
    </motion.div>
  );
}

function ErrorScreen({ error, onBack }: { error: ErrorPayload; onBack: () => void }) {
  const keyMissing = error.code === ERROR_CODES.apiKeyMissing;
  return (
    <div className="flex h-full items-center justify-center">
      <StateMessage
        icon={keyMissing ? '🔑' : '!'}
        tone={keyMissing ? 'warn' : 'err'}
        title={keyMissing ? 'API anahtarı eksik' : 'Analiz tamamlanamadı'}
        actions={
          <Button variant="primary" onClick={onBack}>
            Ana sayfaya dön
          </Button>
        }
      >
        {keyMissing ? <ApiKeyMissingHelp /> : <p>{error.message}</p>}
      </StateMessage>
    </div>
  );
}
