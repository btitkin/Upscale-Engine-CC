import React, { useEffect, useState } from 'react';
import { Loader2, Server, Cpu, CheckCircle2, AlertCircle } from 'lucide-react';

interface LoadingScreenProps {
    onReady: () => void;
    backendUrl: string;
}

interface LoadingStep {
    id: string;
    label: string;
    status: 'pending' | 'loading' | 'done' | 'error';
    detail?: string;
}

const LoadingScreen: React.FC<LoadingScreenProps> = ({ onReady, backendUrl }) => {
    const [steps, setSteps] = useState<LoadingStep[]>([
        { id: 'backend', label: 'Łączenie z backendem', status: 'pending' },
        { id: 'comfyui', label: 'Uruchamianie ComfyUI', status: 'pending' },
    ]);

    const [error, setError] = useState<string | null>(null);
    const [retryCount, setRetryCount] = useState(0);

    const updateStep = (id: string, update: Partial<LoadingStep>) => {
        setSteps(prev => prev.map(s => s.id === id ? { ...s, ...update } : s));
    };

    useEffect(() => {
        let cancelled = false;

        const initializeApp = async () => {
            try {
                // Step 1: Check backend connection
                updateStep('backend', { status: 'loading' });

                let backendReady = false;
                for (let i = 0; i < 30; i++) {
                    if (cancelled) return;
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
                        await new Promise(r => setTimeout(r, 1000));
                    }
                }

                if (!backendReady) {
                    throw new Error('Nie można połączyć z backendem. Uruchom: python backend/server.py');
                }

                updateStep('backend', { status: 'done', detail: 'Połączono' });

                // Step 2: Start ComfyUI
                updateStep('comfyui', { status: 'loading', detail: 'Startowanie...' });

                const startRes = await fetch(`${backendUrl}/comfyui/start`, {
                    method: 'POST',
                    signal: AbortSignal.timeout(120000) // 2 min timeout
                });

                if (!startRes.ok) {
                    const errData = await startRes.json();
                    throw new Error(errData.error || 'Błąd startowania ComfyUI');
                }

                updateStep('comfyui', { status: 'done', detail: 'Aktywny' });

                // All done!
                await new Promise(r => setTimeout(r, 300));
                if (!cancelled) {
                    onReady();
                }

            } catch (err: any) {
                console.error('Init error:', err);
                setError(err.message || 'Błąd inicjalizacji');

                // Mark current loading step as error
                setSteps(prev => prev.map(s =>
                    s.status === 'loading' ? { ...s, status: 'error' } : s
                ));
            }
        };

        initializeApp();

        return () => { cancelled = true; };
    }, [backendUrl, retryCount]);

    const handleRetry = () => {
        setError(null);
        setSteps(prev => prev.map(s => ({ ...s, status: 'pending', detail: undefined })));
        setRetryCount(r => r + 1);
    };

    return (
        <div className="fixed inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center z-50">
            <div className="max-w-md w-full mx-4">
                {/* Logo / Title */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-cyan-500 mb-4">
                        <Cpu className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-white mb-2">Upscale Engine CC</h1>
                    <p className="text-white/50 text-sm">Inicjalizacja systemu AI...</p>
                </div>

                {/* Loading Steps */}
                <div className="bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-6 space-y-4">
                    {steps.map((step, idx) => (
                        <div key={step.id} className="flex items-center gap-4">
                            {/* Icon */}
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

                            {/* Label */}
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
                        </div>
                    ))}
                </div>

                {/* Error Message */}
                {error && (
                    <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
                        <p className="text-red-400 text-sm mb-3">{error}</p>
                        <button
                            onClick={handleRetry}
                            className="w-full py-2 px-4 bg-white/10 hover:bg-white/20 text-white text-sm font-medium rounded-lg transition-colors"
                        >
                            Spróbuj ponownie
                        </button>
                    </div>
                )}

                {/* Progress bar at bottom */}
                <div className="mt-6 h-1 bg-white/10 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-500"
                        style={{
                            width: `${(steps.filter(s => s.status === 'done').length / steps.length) * 100}%`
                        }}
                    />
                </div>
            </div>
        </div>
    );
};

export default LoadingScreen;
