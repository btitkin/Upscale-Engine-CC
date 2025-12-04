import { UpscaleResult, ProcessorSettings, ServerStatus } from '../types';

/**
 * LumaScale Local Backend Bridge v3.0
 * Connects to Python Flask backend for local AI inference
 * No external dependencies - fully standalone
 */

const BACKEND_URL = 'http://localhost:5555';

const DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
};

export const checkServerStatus = async (url: string = BACKEND_URL): Promise<ServerStatus> => {
    try {
        const response = await fetch(`${url}/status`, { method: 'GET' });
        if (!response.ok) throw new Error("Backend offline");

        const data = await response.json();

        // Map backend response to existing ServerStatus interface
        const upscalers = [];
        if (data.models.esrgan) upscalers.push('RealESRGAN x4plus');
        if (data.models.swinir) upscalers.push('SwinIR-L 4x');
        if (data.models.supresdiffgan) upscalers.push('SupResDiffGAN 4x');

        return {
            online: data.status === 'online',
            models: data.models_ready ? ['LumaScale Models'] : [],
            upscalers: upscalers.length > 0 ? upscalers : ['RealESRGAN x4plus'],
            missingModels: data.missing_models || []
        };
    } catch (e) {
        return { online: false, models: [], upscalers: [] };
    }
};

// Model selection no longer needed - backend uses fixed models
export const setServerModel = async (url: string, modelTitle: string): Promise<void> => {
    // No-op: Backend automatically uses correct models
    return Promise.resolve();
};

export const downloadModels = async (url: string = BACKEND_URL): Promise<void> => {
    const response = await fetch(`${url}/models/download`, { method: 'POST' });
    if (!response.ok) throw new Error("Download failed");
    const data = await response.json();
    if (data.status === 'error') throw new Error(data.message);
};

const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve((reader.result as string).split(',')[1]);
        reader.readAsDataURL(file);
    });
};

const getImageDimensions = (file: File): Promise<{ width: number, height: number }> => {
    return new Promise((r) => {
        const i = new Image();
        i.onload = () => r({ width: i.width, height: i.height });
        i.src = URL.createObjectURL(file);
    });
};

export interface ProgressUpdate {
    status: string;
    step: string;
    progress: number;
}

export const pollProgress = async (
    requestId: string,
    onProgress: (update: ProgressUpdate) => void
): Promise<void> => {
    return new Promise((resolve) => {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`${BACKEND_URL}/progress/${requestId}`);
                if (!response.ok) {
                    clearInterval(interval);
                    resolve();
                    return;
                }

                const data: ProgressUpdate = await response.json();
                onProgress(data);

                if (data.status === 'complete' || data.progress >= 100) {
                    clearInterval(interval);
                    resolve();
                }
            } catch (e) {
                console.error('Progress poll error:', e);
                clearInterval(interval);
                resolve();
            }
        }, 500); // Poll every 500ms
    });
};

export const processImageLocally = async (
    file: File,
    settings: ProcessorSettings,
    onProgress?: (update: ProgressUpdate) => void
): Promise<UpscaleResult> => {
    const startTime = performance.now();

    // 1. Prepare Data
    const base64 = await fileToBase64(file);
    const dims = await getImageDimensions(file);

    // Generate Request ID for progress tracking
    const requestId = crypto.randomUUID();

    // 2. Determine which endpoint to use based on active modules
    let endpoint = '';
    let payload: any = {
        image: base64,
        request_id: requestId,
        use_tiling: settings.enableTiling // Universal tiling support
    };

    // Route to appropriate backend endpoint based on modules
    if (settings.enableRealism) {
        // Phase 3: Qwen "Make it Real"
        endpoint = '/make-real';
        payload.prompt = settings.prompt || 'convert to photorealistic, raw photo, dslr quality';

        if (settings.enableUpscale) {
            payload.scale_factor = settings.upscaleFactor;
        }

    } else if (settings.enableSkin || settings.enableHiresFix) {
        // Phase 2: SDXL img2img enhancement
        endpoint = '/enhance';
        payload.modules = {
            skin_texture: settings.enableSkin,
            hires_fix: settings.enableHiresFix,
            upscale: settings.enableUpscale
        };
        payload.scale_factor = settings.upscaleFactor;
        payload.denoising_strength = settings.denoisingStrength;
        payload.cfg_scale = settings.cfgScale;
        payload.prompt = settings.prompt || '';

    } else if (settings.enableUpscale) {
        // Phase 1: ESRGAN upscale only
        endpoint = '/upscale';
        payload.upscaler = settings.upscaler;
        payload.scale_factor = settings.upscaleFactor;
    } else {
        throw new Error('No processing modules enabled');
    }

    // Start polling concurrently if callback provided
    if (onProgress) {
        // Start polling immediately (non-blocking)
        pollProgress(requestId, onProgress).catch(err => {
            console.error('Progress polling error:', err);
        });
    }

    // 3. Make API request to backend (Blocking)
    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
        method: 'POST',
        headers: DEFAULT_HEADERS,
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));

        // Check if feature not yet implemented
        if (response.status === 501) {
            throw new Error(`${errorData.error || 'Feature not yet implemented'}. Using simple upscale instead.`);
        }

        throw new Error(errorData.error || `Backend error: ${response.statusText}`);
    }

    const data = await response.json();

    // 4. Extract result
    if (!data.image) {
        throw new Error("Backend returned no image data");
    }

    const duration = (performance.now() - startTime) / 1000;
    const upscaledUrl = `data:image/png;base64,${data.image}`;

    // Use backend-provided dimensions or calculate
    const width = data.width || (dims.width * settings.upscaleFactor);
    const height = data.height || (dims.height * settings.upscaleFactor);

    return {
        filename: file.name,
        originalUrl: URL.createObjectURL(file),
        upscaledUrl: upscaledUrl,
        width: width,
        height: height,
        processingTime: data.processing_time || duration
    };
};