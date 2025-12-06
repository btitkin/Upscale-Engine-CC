import { useEffect, useCallback } from 'react';

interface KeyboardShortcuts {
    onProcess?: () => void;
    onCancel?: () => void;
    onOpenFiles?: () => void;
    onNextResult?: () => void;
    onPrevResult?: () => void;
    onClose?: () => void;
    onSelectAll?: () => void;
    onDeselectAll?: () => void;
    isProcessing?: boolean;
    hasQueue?: boolean;
    hasResults?: boolean;
}

/**
 * Hook for global keyboard shortcuts
 * 
 * Shortcuts:
 * - Ctrl+O: Open file dialog
 * - Space/Enter: Start processing  
 * - Escape: Cancel/Close
 * - Arrow Left/Right: Navigate results
 * - Ctrl+A: Select all in queue
 * - Ctrl+D: Deselect all
 */
export function useKeyboardShortcuts({
    onProcess,
    onCancel,
    onOpenFiles,
    onNextResult,
    onPrevResult,
    onClose,
    onSelectAll,
    onDeselectAll,
    isProcessing = false,
    hasQueue = false,
    hasResults = false
}: KeyboardShortcuts) {

    const handleKeyDown = useCallback((e: KeyboardEvent) => {
        // Ignore if typing in input/textarea
        const target = e.target as HTMLElement;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
            return;
        }

        const isCtrl = e.ctrlKey || e.metaKey;

        // Ctrl+O: Open files
        if (isCtrl && e.key === 'o') {
            e.preventDefault();
            onOpenFiles?.();
            return;
        }

        // Ctrl+A: Select all
        if (isCtrl && e.key === 'a') {
            e.preventDefault();
            onSelectAll?.();
            return;
        }

        // Ctrl+D: Deselect all
        if (isCtrl && e.key === 'd') {
            e.preventDefault();
            onDeselectAll?.();
            return;
        }

        // Space or Enter: Process
        if ((e.key === ' ' || e.key === 'Enter') && hasQueue && !isProcessing) {
            e.preventDefault();
            onProcess?.();
            return;
        }

        // Escape: Cancel or Close
        if (e.key === 'Escape') {
            e.preventDefault();
            if (isProcessing) {
                onCancel?.();
            } else if (hasResults) {
                onClose?.();
            }
            return;
        }

        // Arrow keys: Navigate results
        if (hasResults && !isProcessing) {
            if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                e.preventDefault();
                onNextResult?.();
                return;
            }
            if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                e.preventDefault();
                onPrevResult?.();
                return;
            }
        }
    }, [
        onProcess, onCancel, onOpenFiles, onNextResult, onPrevResult,
        onClose, onSelectAll, onDeselectAll, isProcessing, hasQueue, hasResults
    ]);

    useEffect(() => {
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [handleKeyDown]);
}
