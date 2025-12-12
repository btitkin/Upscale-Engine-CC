import { useState, useCallback, useMemo } from 'react';

/**
 * Single entry in the image processing history
 */
export interface HistoryEntry {
    id: string;
    image: string;        // Base64 data URL or blob URL
    operation: string;    // e.g., "Original", "Make It Real", "HiresFix"
    timestamp: number;
    settings?: object;    // Settings used for this operation
}

/**
 * Return type for useImageHistory hook
 */
export interface ImageHistoryState {
    // History data
    history: HistoryEntry[];
    currentIndex: number;

    // Computed values
    currentImage: string | null;
    originalImage: string | null;
    currentOperation: string | null;

    // Actions
    setOriginal: (image: string, filename?: string) => void;
    pushImage: (image: string, operation: string, settings?: object) => void;
    undo: () => void;
    redo: () => void;
    reset: () => void;
    goToStep: (index: number) => void;

    // State flags
    canUndo: boolean;
    canRedo: boolean;
    historyLength: number;
    stepInfo: string;  // e.g., "Step 2/5"
}

const MAX_HISTORY_DEPTH = 10;

/**
 * Hook for managing image processing history with undo/redo support
 */
export function useImageHistory(): ImageHistoryState {
    const [history, setHistory] = useState<HistoryEntry[]>([]);
    const [currentIndex, setCurrentIndex] = useState(-1);

    // Computed values
    const currentImage = useMemo(() => {
        if (currentIndex >= 0 && currentIndex < history.length) {
            return history[currentIndex].image;
        }
        return null;
    }, [history, currentIndex]);

    const originalImage = useMemo(() => {
        if (history.length > 0) {
            return history[0].image;
        }
        return null;
    }, [history]);

    const currentOperation = useMemo(() => {
        if (currentIndex >= 0 && currentIndex < history.length) {
            return history[currentIndex].operation;
        }
        return null;
    }, [history, currentIndex]);

    const canUndo = currentIndex > 0;
    const canRedo = currentIndex < history.length - 1;
    const historyLength = history.length;

    const stepInfo = useMemo(() => {
        if (history.length === 0) return '';
        return `Step ${currentIndex + 1}/${history.length}`;
    }, [history.length, currentIndex]);

    // Set the original image (first entry in history)
    const setOriginal = useCallback((image: string, filename?: string) => {
        const entry: HistoryEntry = {
            id: `original-${Date.now()}`,
            image,
            operation: filename ? `Original: ${filename}` : 'Original',
            timestamp: Date.now(),
        };
        setHistory([entry]);
        setCurrentIndex(0);
    }, []);

    // Push a new processed image to history
    const pushImage = useCallback((image: string, operation: string, settings?: object) => {
        // Use functional update to get latest state
        setCurrentIndex(prevIndex => {
            // First update history with the correct prevIndex
            setHistory(prevHistory => {
                // If we're not at the end of history, truncate future entries
                const newHistory = prevHistory.slice(0, prevIndex + 1);

                const entry: HistoryEntry = {
                    id: `${operation}-${Date.now()}`,
                    image,
                    operation,
                    timestamp: Date.now(),
                    settings,
                };

                // Add new entry
                newHistory.push(entry);

                // Limit history depth (keep original + last N-1 operations)
                if (newHistory.length > MAX_HISTORY_DEPTH) {
                    // Keep the first entry (original) and trim from the beginning of operations
                    return [newHistory[0], ...newHistory.slice(-(MAX_HISTORY_DEPTH - 1))];
                }

                return newHistory;
            });

            // Return new index
            const newIndex = Math.min(prevIndex + 1, MAX_HISTORY_DEPTH - 1);
            return newIndex;
        });
    }, []);

    // Undo - go back one step
    const undo = useCallback(() => {
        if (canUndo) {
            setCurrentIndex(prev => prev - 1);
        }
    }, [canUndo]);

    // Redo - go forward one step
    const redo = useCallback(() => {
        if (canRedo) {
            setCurrentIndex(prev => prev + 1);
        }
    }, [canRedo]);

    // Reset - clear all history
    const reset = useCallback(() => {
        setHistory([]);
        setCurrentIndex(-1);
    }, []);

    // Go to specific step
    const goToStep = useCallback((index: number) => {
        if (index >= 0 && index < history.length) {
            setCurrentIndex(index);
        }
    }, [history.length]);

    return {
        history,
        currentIndex,
        currentImage,
        originalImage,
        currentOperation,
        setOriginal,
        pushImage,
        undo,
        redo,
        reset,
        goToStep,
        canUndo,
        canRedo,
        historyLength,
        stepInfo,
    };
}
