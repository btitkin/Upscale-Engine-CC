import React, { useEffect, useState, useRef } from 'react';
import { Loader2, Cpu, CheckCircle2, AlertCircle, Zap } from 'lucide-react';

interface LoadingScreenProps {
    onReady: () => void;
    backendUrl: string;
}

interface LoadingStep {
    id: string;
    label: string;
    status: 'pending' | 'loading' | 'done' | 'error';
    detail?: string;
    progress?: number;
}

const LoadingScreen: React.FC<LoadingScreenProps> = ({ onReady, backendUrl }) => {
    const [steps, setSteps] = useState<LoadingStep[]>([
        { id: 'backend', label: 'Łączenie z backendem', status: 'pending' },
        { id: 'comfyui', label: 'Uruchamianie ComfyUI', status: 'pending', progress: 0 },
    ]);

    const [error, setError] = useState<string | null>(null);
    const [retryCount, setRetryCount] = useState(0);
    const [overallProgress, setOverallProgress] = useState(0);
    const [elapsedTime, setElapsedTime] = useState(0);
    const cancelledRef = useRef(false);

    const updateStep = (id: string, update: Partial<LoadingStep>) => {
        setSteps(prev => prev.map(s => s.id === id ? { ...s, ...update } : s));
    };

    // Calculate overall progress
    useEffect(() => {
        const doneCount = steps.filter(s => s.status === 'done').length;
        const loadingStep = steps.find(s => s.status === 'loading');
        const stepProgress = loadingStep?.progress || 0;

        const baseProgress = (doneCount / steps.length) * 100;
        const partialProgress = (stepProgress / 100) * (100 / steps.length);
        setOverallProgress(Math.round(baseProgress + partialProgress));
    }, [steps]);

    // Timer for elapsed time
    useEffect(() => {
        const timer = setInterval(() => {
            setElapsedTime(prev => prev + 1);
        }, 1000);
        return () => clearInterval(timer);
    }, [retryCount]);

    useEffect(() => {
        cancelledRef.current = false;

        const initializeApp = async () => {
            try {
                // Step 1: Check backend connection
                updateStep('backend', { status: 'loading', detail: 'Sprawdzanie połączenia...' });

                let backendReady = false;
                for (let i = 0; i < 30; i++) {
                    if (cancelledRef.current) return;

                    updateStep('backend', {
                        detail: `Próba ${i + 1}/30...`,
                        progress: Math.round((i / 30) * 100)
                    });

                    try {
                        const res = await fetch(`${backendUrl}/status`, {
                            method: 'GET',
                            signal: AbortSignal.timeout(2000)
                        });
                        if (res.ok) {
                            backendReady = true;
                            break;
                        }
                    } catch {
                        // Wait before retry
                        await new Promise(r => setTimeout(r, 1000));
                    }
                }

                if (!backendReady) {
                    throw new Error('Nie można połączyć z backendem. Uruchom: START_UPSCALE_ENGINE.bat');
                }

                updateStep('backend', { status: 'done', detail: 'Połączono', progress: 100 });

                // Step 2: Start ComfyUI (single request, no polling)
                updateStep('comfyui', { status: 'loading', detail: 'Startowanie serwera...', progress: 10 });

                // Single request to start ComfyUI - don't poll aggressively
                try {
                    const startRes = await fetch(`${backendUrl}/comfyui/start`, {
                        method: 'POST',
                        signal: AbortSignal.timeout(180000) // 3 min timeout
                    });

                    if (cancelledRef.current) return;

                    if (!startRes.ok) {
                        const errData = await startRes.json().catch(() => ({}));
                        throw new Error(errData.error || 'Błąd startowania ComfyUI');
                    }

                    const startData = await startRes.json();

                    if (startData.status === 'already_running') {
                        updateStep('comfyui', { status: 'done', detail: 'Już aktywny', progress: 100 });
                    } else {
                        updateStep('comfyui', { status: 'done', detail: 'Uruchomiony', progress: 100 });
                    }

                } catch (err: any) {
                    if (err.name === 'TimeoutError') {
                        throw new Error('Timeout startowania ComfyUI (3 min). Sprawdź logi.');
                    }
                    throw err;
                }

                // All done!
                if (!cancelledRef.current) {
                    await new Promise(r => setTimeout(r, 500));
                    onReady();
                }

            } catch (err: any) {
                if (cancelledRef.current) return;

                console.error('Init error:', err);
                setError(err.message || 'Błąd inicjalizacji');

                setSteps(prev => prev.map(s =>
                    s.status === 'loading' ? { ...s, status: 'error' } : s
                ));
            }
        };

        initializeApp();

        return () => {
            cancelledRef.current = true;
        };
    }, [backendUrl, retryCount, onReady]);

    const handleRetry = () => {
        setError(null);
        setElapsedTime(0);
        setSteps(prev => prev.map(s => ({ ...s, status: 'pending', detail: undefined, progress: 0 })));
        setRetryCount(r => r + 1);
    };

    const handleSkip = () => {
        cancelledRef.current = true;
        onReady();
    };

    return (
        <div className="fixed inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center z-50">
            <div className="max-w-md w-full mx-4">
                {/* Logo / Title */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-cyan-500 mb-4">
                        <Zap className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-white mb-2">Upscale Engine CC</h1>
                    <p className="text-white/50 text-sm">Inicjalizacja systemu AI...</p>
                </div>

                {/* Overall Progress */}
                <div className="text-center mb-4">
                    <span className="text-4xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                        {overallProgress}%
                    </span>
                    <span className="text-white/30 text-sm ml-2">({elapsedTime}s)</span>
                </div>

                {/* Loading Steps */}
                <div className="bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-6 space-y-4">
                    {steps.map((step) => (
                        <div key={step.id} className="space-y-2">
                            <div className="flex items-center gap-4">
                                <div className="w-8 h-8 flex items-center justify-center">
                                    {step.status === 'pending' && (
                                        <div className="w-3 h-3 rounded-full bg-white/20" />
                                    )}
                                    {step.status === 'loading' && (
                                        <Loader2 className="w-5 h-5 text-emerald-400 animate-spin" />
                                    )}
                                    {step.status === 'done' && (
                                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                                    )}
                                    {step.status === 'error' && (
                                        <AlertCircle className="w-5 h-5 text-red-400" />
                                    )}
                                </div>

                                <div className="flex-1">
                                    <div className={`text-sm font-medium ${step.status === 'done' ? 'text-white' :
                                            step.status === 'loading' ? 'text-emerald-400' :
                                                step.status === 'error' ? 'text-red-400' :
                                                    'text-white/40'
                                        }`}>
                                        {step.label}
                                    </div>
                                    {step.detail && (
                                        <div className="text-xs text-white/40">{step.detail}</div>
                                    )}
                                </div>

                                {step.status === 'loading' && step.progress !== undefined && (
                                    <span className="text-xs text-emerald-400 font-mono">
                                        {step.progress}%
                                    </span>
                                )}
                            </div>

                            {step.status === 'loading' && step.progress !== undefined && (
                                <div className="ml-12 h-1 bg-white/10 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-emerald-500 transition-all duration-300"
                                        style={{ width: `${step.progress}%` }}
                                    />
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                {/* Error Message */}
                {error && (
                    <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
                        <p className="text-red-400 text-sm mb-3">{error}</p>
                        <div className="flex gap-2">
                            <button
                                onClick={handleRetry}
                                className="flex-1 py-2 px-4 bg-white/10 hover:bg-white/20 text-white text-sm font-medium rounded-lg transition-colors"
                            >
                                Spróbuj ponownie
                            </button>
                            <button
                                onClick={handleSkip}
                                className="py-2 px-4 bg-white/5 hover:bg-white/10 text-white/60 text-sm rounded-lg transition-colors"
                            >
                                Pomiń
                            </button>
                        </div>
                    </div>
                )}

                {/* Progress bar */}
                <div className="mt-6 h-2 bg-white/10 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-500"
                        style={{ width: `${overallProgress}%` }}
                    />
                </div>

                {!error && (
                    <p className="text-center text-white/30 text-xs mt-4">
                        Pierwsze uruchomienie może trwać dłużej
                    </p>
                )}
            </div>
        </div>
    );
};

export default LoadingScreen;
