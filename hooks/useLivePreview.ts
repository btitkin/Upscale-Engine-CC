import { useState, useEffect, useCallback } from 'react';

/**
 * Hook for receiving live preview images via SSE during processing
 */
export function useLivePreview(
    backendUrl: string,
    requestId: string | null,
    enabled: boolean = true
) {
    const [previewImage, setPreviewImage] = useState<string | null>(null);
    const [previewStep, setPreviewStep] = useState<number>(0);
    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
        if (!enabled || !requestId) {
            setPreviewImage(null);
            setPreviewStep(0);
            setIsConnected(false);
            return;
        }

        const eventSource = new EventSource(`${backendUrl}/preview/${requestId}`);

        eventSource.onopen = () => {
            console.log('[LivePreview] Connected');
            setIsConnected(true);
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.done) {
                    console.log('[LivePreview] Processing complete');
                    eventSource.close();
                    setIsConnected(false);
                    return;
                }

                if (data.image) {
                    // Add data URI prefix for JPEG
                    const imageUrl = `data:image/jpeg;base64,${data.image}`;
                    setPreviewImage(imageUrl);
                    setPreviewStep(data.step || 0);
                    console.log(`[LivePreview] Step ${data.step}`);
                }
            } catch (e) {
                console.error('[LivePreview] Parse error:', e);
            }
        };

        eventSource.onerror = (error) => {
            console.error('[LivePreview] SSE error:', error);
            setIsConnected(false);
            eventSource.close();
        };

        return () => {
            eventSource.close();
            setIsConnected(false);
        };
    }, [backendUrl, requestId, enabled]);

    const reset = useCallback(() => {
        setPreviewImage(null);
        setPreviewStep(0);
    }, []);

    return {
        previewImage,
        previewStep,
        isConnected,
        reset
    };
}
