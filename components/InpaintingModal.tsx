import React, { useState, useRef, useEffect } from 'react';
import { X, Paintbrush, Eraser, Trash2, Undo2, Redo2, Loader2, Maximize2 } from 'lucide-react';
import MaskCanvas from './MaskCanvas';

interface InpaintingModalProps {
    imageUrl: string;
    imageWidth: number;
    imageHeight: number;
    onClose: () => void;
    onApply: (maskDataUrl: string, prompt: string, strength: number) => void;
    isProcessing?: boolean;
}

/**
 * InpaintingModal - Modal for mask drawing and inpainting configuration
 */
const InpaintingModal: React.FC<InpaintingModalProps> = ({
    imageUrl,
    imageWidth,
    imageHeight,
    onClose,
    onApply,
    isProcessing = false
}) => {
    const [brushSize, setBrushSize] = useState(30);
    const [isEraser, setIsEraser] = useState(false);
    const [prompt, setPrompt] = useState('');
    const [strength, setStrength] = useState(0.75);
    const [maskDataUrl, setMaskDataUrl] = useState<string | null>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Calculate display size (fit in viewport)
    const maxWidth = Math.min(800, window.innerWidth - 100);
    const maxHeight = Math.min(600, window.innerHeight - 300);
    const scale = Math.min(maxWidth / imageWidth, maxHeight / imageHeight, 1);
    const displayWidth = Math.round(imageWidth * scale);
    const displayHeight = Math.round(imageHeight * scale);

    const handleApply = () => {
        if (!maskDataUrl || !prompt.trim()) {
            alert('Please draw a mask and enter a prompt');
            return;
        }
        onApply(maskDataUrl, prompt.trim(), strength);
    };

    const handleClear = () => {
        const canvas = document.querySelector('canvas') as any;
        if (canvas?.clearMask) {
            canvas.clearMask();
        }
    };

    const handleUndo = () => {
        const canvas = document.querySelector('canvas') as any;
        if (canvas?.undo) {
            canvas.undo();
        }
    };

    const handleRedo = () => {
        const canvas = document.querySelector('canvas') as any;
        if (canvas?.redo) {
            canvas.redo();
        }
    };

    // Close on Escape
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && !isProcessing) {
                onClose();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onClose, isProcessing]);

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-zinc-900 rounded-2xl border border-white/10 shadow-2xl max-w-[900px] w-full mx-4 overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                            <Paintbrush className="w-4 h-4 text-white" />
                        </div>
                        <div>
                            <h2 className="text-white font-semibold">Inpainting</h2>
                            <p className="text-white/50 text-xs">Draw on areas you want to change</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        disabled={isProcessing}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors disabled:opacity-50"
                    >
                        <X className="w-5 h-5 text-white/50 hover:text-white" />
                    </button>
                </div>

                {/* Toolbar */}
                <div className="flex items-center gap-4 p-4 border-b border-white/10 bg-black/20">
                    {/* Brush/Eraser Toggle */}
                    <div className="flex gap-1 bg-white/5 rounded-lg p-1">
                        <button
                            onClick={() => setIsEraser(false)}
                            className={`p-2 rounded-md transition-all ${!isEraser ? 'bg-purple-500 text-white' : 'text-white/50 hover:text-white'}`}
                            title="Brush (draw mask)"
                        >
                            <Paintbrush className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setIsEraser(true)}
                            className={`p-2 rounded-md transition-all ${isEraser ? 'bg-purple-500 text-white' : 'text-white/50 hover:text-white'}`}
                            title="Eraser (remove mask)"
                        >
                            <Eraser className="w-4 h-4" />
                        </button>
                    </div>

                    {/* Brush Size */}
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-white/50">Size</span>
                        <input
                            type="range"
                            min="5"
                            max="100"
                            value={brushSize}
                            onChange={(e) => setBrushSize(Number(e.target.value))}
                            className="w-24 accent-purple-500"
                        />
                        <span className="text-xs text-white/70 w-8">{brushSize}px</span>
                    </div>

                    <div className="w-px h-6 bg-white/10" />

                    {/* Undo/Redo */}
                    <button
                        onClick={handleUndo}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors text-white/50 hover:text-white"
                        title="Undo (Ctrl+Z)"
                    >
                        <Undo2 className="w-4 h-4" />
                    </button>
                    <button
                        onClick={handleRedo}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors text-white/50 hover:text-white"
                        title="Redo (Ctrl+Y)"
                    >
                        <Redo2 className="w-4 h-4" />
                    </button>

                    <div className="w-px h-6 bg-white/10" />

                    {/* Clear */}
                    <button
                        onClick={handleClear}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors text-white/50 hover:text-red-400"
                        title="Clear mask"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>

                {/* Canvas Area */}
                <div className="p-4 flex justify-center bg-black/40">
                    <div
                        className="rounded-lg overflow-hidden border border-white/10"
                        style={{ width: displayWidth, height: displayHeight }}
                    >
                        <MaskCanvas
                            imageUrl={imageUrl}
                            width={displayWidth}
                            height={displayHeight}
                            brushSize={brushSize}
                            isEraser={isEraser}
                            onMaskChange={setMaskDataUrl}
                        />
                    </div>
                </div>

                {/* Settings */}
                <div className="p-4 space-y-4 border-t border-white/10">
                    {/* Prompt */}
                    <div className="space-y-2">
                        <label className="text-xs text-white/50 uppercase tracking-wider font-bold">
                            Prompt (what to generate in masked area)
                        </label>
                        <textarea
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            placeholder="e.g., 'remove text', 'add flowers', 'sunny beach background'..."
                            className="w-full h-20 px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/30 focus:border-purple-500/50 focus:outline-none resize-none"
                            disabled={isProcessing}
                        />
                    </div>

                    {/* Strength Slider */}
                    <div className="flex items-center gap-4">
                        <label className="text-xs text-white/50 uppercase tracking-wider font-bold w-24">
                            Strength
                        </label>
                        <input
                            type="range"
                            min="0.3"
                            max="1.0"
                            step="0.05"
                            value={strength}
                            onChange={(e) => setStrength(Number(e.target.value))}
                            className="flex-1 accent-purple-500"
                            disabled={isProcessing}
                        />
                        <span className="text-sm text-white/70 w-12">{Math.round(strength * 100)}%</span>
                    </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between p-4 border-t border-white/10 bg-black/20">
                    <p className="text-xs text-white/30">
                        {isProcessing ? 'Processing...' : 'White areas will be regenerated • Ctrl+Z to undo'}
                    </p>
                    <div className="flex gap-3">
                        <button
                            onClick={onClose}
                            disabled={isProcessing}
                            className="px-4 py-2 text-sm bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-white/70 transition-colors disabled:opacity-50"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleApply}
                            disabled={isProcessing || !maskDataUrl || !prompt.trim()}
                            className="px-4 py-2 text-sm bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 rounded-lg text-white font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {isProcessing ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Processing...
                                </>
                            ) : (
                                'Apply Inpainting'
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default InpaintingModal;
