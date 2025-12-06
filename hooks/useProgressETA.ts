import { useState, useEffect, useCallback, useRef } from 'react';

interface ETAResult {
    /** Estimated seconds remaining */
    secondsRemaining: number | null;
    /** Formatted string like "2m 30s" */
    formatted: string;
    /** Processing speed: items per second */
    itemsPerSecond: number;
    /** Is actively calculating */
    isCalculating: boolean;
}

/**
 * Hook for calculating estimated time remaining during processing
 * Uses rolling average of recent progress updates
 */
export function useProgressETA(
    progress: number,
    isProcessing: boolean,
    currentItem: number = 1,
    totalItems: number = 1
): ETAResult {
    const [eta, setEta] = useState<ETAResult>({
        secondsRemaining: null,
        formatted: '',
        itemsPerSecond: 0,
        isCalculating: false
    });

    // Track progress history for rolling average
    const historyRef = useRef<{ time: number; progress: number }[]>([]);
    const startTimeRef = useRef<number | null>(null);

    // Reset on processing start
    useEffect(() => {
        if (isProcessing && progress === 0) {
            historyRef.current = [];
            startTimeRef.current = Date.now();
        }
    }, [isProcessing, progress]);

    // Calculate ETA on progress change
    useEffect(() => {
        if (!isProcessing || progress <= 0) {
            setEta({
                secondsRemaining: null,
                formatted: '',
                itemsPerSecond: 0,
                isCalculating: false
            });
            return;
        }

        const now = Date.now();

        // Add to history
        historyRef.current.push({ time: now, progress });

        // Keep only last 10 samples
        if (historyRef.current.length > 10) {
            historyRef.current.shift();
        }

        // Need at least 2 samples
        if (historyRef.current.length < 2) {
            setEta(prev => ({ ...prev, isCalculating: true, formatted: 'Calculating...' }));
            return;
        }

        // Calculate rate from history
        const history = historyRef.current;
        const oldest = history[0];
        const newest = history[history.length - 1];

        const timeDiff = (newest.time - oldest.time) / 1000; // seconds
        const progressDiff = newest.progress - oldest.progress;

        if (timeDiff <= 0 || progressDiff <= 0) {
            return;
        }

        // Progress per second (for current item)
        const progressPerSecond = progressDiff / timeDiff;

        // Remaining progress for current item
        const remainingProgress = 100 - progress;
        const currentItemSecondsRemaining = remainingProgress / progressPerSecond;

        // Add time for remaining items
        const totalElapsed = startTimeRef.current ? (now - startTimeRef.current) / 1000 : 0;
        const timePerItem = progress > 0 ? (totalElapsed / (currentItem - 1 + progress / 100)) : 0;
        const remainingItems = totalItems - currentItem;
        const remainingItemsSeconds = remainingItems * timePerItem;

        const totalSecondsRemaining = Math.max(0, currentItemSecondsRemaining + remainingItemsSeconds);

        // Format time
        const formatted = formatTime(totalSecondsRemaining);

        // Items per second (for batch processing)
        const itemsPerSecond = timePerItem > 0 ? 1 / timePerItem : 0;

        setEta({
            secondsRemaining: totalSecondsRemaining,
            formatted,
            itemsPerSecond,
            isCalculating: false
        });

    }, [progress, isProcessing, currentItem, totalItems]);

    return eta;
}

function formatTime(seconds: number): string {
    if (seconds <= 0 || !isFinite(seconds)) return '';

    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);

    if (mins === 0) {
        return `${secs}s remaining`;
    } else if (mins < 60) {
        return `${mins}m ${secs}s remaining`;
    } else {
        const hours = Math.floor(mins / 60);
        const remainingMins = mins % 60;
        return `${hours}h ${remainingMins}m remaining`;
    }
}
