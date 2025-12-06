import React, { useRef, useEffect, useState, useCallback } from 'react';

interface MaskCanvasProps {
    imageUrl: string;
    width: number;
    height: number;
    brushSize: number;
    isEraser: boolean;
    onMaskChange?: (maskDataUrl: string) => void;
}

/**
 * MaskCanvas - Canvas overlay for drawing inpainting masks
 * White = areas to inpaint, Black = areas to preserve
 */
const MaskCanvas: React.FC<MaskCanvasProps> = ({
    imageUrl,
    width,
    height,
    brushSize,
    isEraser,
    onMaskChange
}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [lastPos, setLastPos] = useState<{ x: number; y: number } | null>(null);
    const [history, setHistory] = useState<ImageData[]>([]);
    const [historyIndex, setHistoryIndex] = useState(-1);

    // Initialize canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Clear to black (preserve all by default)
        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, width, height);

        // Save initial state
        const initialState = ctx.getImageData(0, 0, width, height);
        setHistory([initialState]);
        setHistoryIndex(0);
    }, [width, height]);

    // Save state to history
    const saveState = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const currentState = ctx.getImageData(0, 0, width, height);

        // Remove future states if we're not at the end
        const newHistory = history.slice(0, historyIndex + 1);
        newHistory.push(currentState);

        // Limit history to 20 states
        if (newHistory.length > 20) {
            newHistory.shift();
        }

        setHistory(newHistory);
        setHistoryIndex(newHistory.length - 1);

        // Notify parent of mask change
        if (onMaskChange) {
            onMaskChange(canvas.toDataURL('image/png'));
        }
    }, [history, historyIndex, width, height, onMaskChange]);

    // Undo (Ctrl+Z)
    const undo = useCallback(() => {
        if (historyIndex <= 0) return;

        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const newIndex = historyIndex - 1;
        ctx.putImageData(history[newIndex], 0, 0);
        setHistoryIndex(newIndex);

        if (onMaskChange) {
            onMaskChange(canvas.toDataURL('image/png'));
        }
    }, [history, historyIndex, onMaskChange]);

    // Redo (Ctrl+Y)
    const redo = useCallback(() => {
        if (historyIndex >= history.length - 1) return;

        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const newIndex = historyIndex + 1;
        ctx.putImageData(history[newIndex], 0, 0);
        setHistoryIndex(newIndex);

        if (onMaskChange) {
            onMaskChange(canvas.toDataURL('image/png'));
        }
    }, [history, historyIndex, onMaskChange]);

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
                e.preventDefault();
                undo();
            }
            if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
                e.preventDefault();
                redo();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [undo, redo]);

    // Get canvas coordinates from mouse event
    const getCanvasPos = (e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        if (!canvas) return { x: 0, y: 0 };

        const rect = canvas.getBoundingClientRect();
        const scaleX = width / rect.width;
        const scaleY = height / rect.height;

        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    };

    // Draw at position
    const draw = (x: number, y: number) => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.globalCompositeOperation = 'source-over';
        ctx.fillStyle = isEraser ? 'black' : 'white';
        ctx.beginPath();
        ctx.arc(x, y, brushSize / 2, 0, Math.PI * 2);
        ctx.fill();

        // Draw line from last position for smooth strokes
        if (lastPos) {
            ctx.strokeStyle = isEraser ? 'black' : 'white';
            ctx.lineWidth = brushSize;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(lastPos.x, lastPos.y);
            ctx.lineTo(x, y);
            ctx.stroke();
        }
    };

    const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
        setIsDrawing(true);
        const pos = getCanvasPos(e);
        setLastPos(pos);
        draw(pos.x, pos.y);
    };

    const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!isDrawing) return;

        const pos = getCanvasPos(e);
        draw(pos.x, pos.y);
        setLastPos(pos);
    };

    const handleMouseUp = () => {
        if (isDrawing) {
            setIsDrawing(false);
            setLastPos(null);
            saveState();
        }
    };

    const handleMouseLeave = () => {
        if (isDrawing) {
            setIsDrawing(false);
            setLastPos(null);
            saveState();
        }
    };

    // Clear mask
    const clear = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, width, height);
        saveState();
    }, [width, height, saveState]);

    // Fill all (inpaint everything)
    const fillAll = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, width, height);
        saveState();
    }, [width, height, saveState]);

    // Expose methods via ref (for parent component)
    useEffect(() => {
        const canvas = canvasRef.current;
        if (canvas) {
            (canvas as any).clearMask = clear;
            (canvas as any).fillAll = fillAll;
            (canvas as any).undo = undo;
            (canvas as any).redo = redo;
        }
    }, [clear, fillAll, undo, redo]);

    return (
        <div className="relative" style={{ width, height }}>
            {/* Background image */}
            <img
                src={imageUrl}
                alt="Source"
                className="absolute inset-0 w-full h-full object-contain pointer-events-none"
                style={{ width, height }}
            />

            {/* Mask canvas overlay */}
            <canvas
                ref={canvasRef}
                width={width}
                height={height}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseLeave}
                className="absolute inset-0 cursor-crosshair"
                style={{
                    width,
                    height,
                    opacity: 0.5,
                    mixBlendMode: 'screen'
                }}
            />
        </div>
    );
};

export default MaskCanvas;
