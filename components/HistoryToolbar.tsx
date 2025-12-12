import React from 'react';
import { Undo2, Redo2, Eye, EyeOff } from 'lucide-react';

interface HistoryToolbarProps {
    canUndo: boolean;
    canRedo: boolean;
    onUndo: () => void;
    onRedo: () => void;
    showOriginal: boolean;
    onToggleOriginal: () => void;
    historyStepInfo?: string;
    disabled?: boolean;
}

/**
 * Floating bottom-center toolbar for history controls (Undo/Redo, Original/Enhanced toggle).
 */
const HistoryToolbar: React.FC<HistoryToolbarProps> = ({
    canUndo,
    canRedo,
    onUndo,
    onRedo,
    showOriginal,
    onToggleOriginal,
    historyStepInfo,
    disabled = false,
}) => {
    return (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 px-3 py-2 bg-black/70 backdrop-blur-lg border border-white/10 rounded-full shadow-2xl animate-in fade-in slide-in-from-bottom-4">
            {/* Undo */}
            <button
                onClick={onUndo}
                disabled={!canUndo || disabled}
                className={`p-2 rounded-full transition-all ${canUndo && !disabled
                    ? 'bg-white/10 text-white hover:bg-white/20'
                    : 'text-white/20 cursor-not-allowed'
                    }`}
                title="Undo (Ctrl+Z)"
            >
                <Undo2 size={16} />
            </button>

            {/* Redo */}
            <button
                onClick={onRedo}
                disabled={!canRedo || disabled}
                className={`p-2 rounded-full transition-all ${canRedo && !disabled
                    ? 'bg-white/10 text-white hover:bg-white/20'
                    : 'text-white/20 cursor-not-allowed'
                    }`}
                title="Redo (Ctrl+Y)"
            >
                <Redo2 size={16} />
            </button>

            {/* Divider */}
            <div className="w-px h-5 bg-white/20 mx-1" />

            {/* Original / Enhanced Toggle */}
            <button
                onClick={onToggleOriginal}
                disabled={disabled}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold transition-all ${showOriginal
                    ? 'bg-blue-500/30 text-blue-300'
                    : 'bg-emerald-500/30 text-emerald-300'
                    }`}
                title="Toggle Original/Enhanced (O)"
            >
                {showOriginal ? <Eye size={14} /> : <EyeOff size={14} />}
                {showOriginal ? 'Original' : 'Enhanced'}
            </button>

            {/* Step Info */}
            {historyStepInfo && (
                <>
                    <div className="w-px h-5 bg-white/20 mx-1" />
                    <span className="text-[10px] font-mono text-white/50">{historyStepInfo}</span>
                </>
            )}
        </div>
    );
};

export default HistoryToolbar;
