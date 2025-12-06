import { ProcessorSettings } from '../types';

const SETTINGS_KEY = 'lumascale_settings';
const PRESETS_KEY = 'lumascale_presets';

export interface PromptPreset {
    id: string;
    name: string;
    prompt: string;
    isDefault?: boolean;
}

const DEFAULT_SETTINGS: ProcessorSettings = {
    backendUrl: 'http://127.0.0.1:5555',
    upscaler: 'RealESRGAN x4plus',
    checkpoint: '',
    enableUpscale: true,
    enableTiling: true,
    enableRealism: false,
    useCustomRealism: false,
    realismCustomPrompt: '',
    enableSkin: true,
    enableHiresFix: true,
    enableFaceEnhance: false,
    upscaleFactor: 2,
    denoisingStrength: 0.25,
    cfgScale: 7.0,
    prompt: ''
};

const DEFAULT_PRESETS: PromptPreset[] = [
    {
        id: 'photorealistic',
        name: '📸 Photorealistic',
        prompt: 'convert to photorealistic, raw photo, dslr quality, natural lighting',
        isDefault: true
    },
    {
        id: 'cinematic',
        name: '🎬 Cinematic',
        prompt: 'cinematic shot, professional photography, dramatic lighting, film grain',
        isDefault: true
    },
    {
        id: 'anime-to-real',
        name: '🎨 Anime to Real',
        prompt: 'convert anime to photorealistic person, real human, detailed skin texture',
        isDefault: true
    },
    {
        id: 'portrait',
        name: '👤 Portrait Pro',
        prompt: 'professional portrait photography, soft lighting, shallow depth of field, studio quality',
        isDefault: true
    },
    {
        id: 'enhance-details',
        name: '🔍 Enhance Details',
        prompt: 'enhance details, sharpen, increase clarity, professional quality',
        isDefault: true
    }
];

/**
 * Load settings from localStorage
 */
export function loadSettings(): ProcessorSettings {
    try {
        const stored = localStorage.getItem(SETTINGS_KEY);
        if (stored) {
            const parsed = JSON.parse(stored);
            // Merge with defaults to ensure all keys exist
            return { ...DEFAULT_SETTINGS, ...parsed };
        }
    } catch (e) {
        console.warn('Failed to load settings:', e);
    }
    return { ...DEFAULT_SETTINGS };
}

/**
 * Save settings to localStorage
 */
export function saveSettings(settings: ProcessorSettings): void {
    try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch (e) {
        console.warn('Failed to save settings:', e);
    }
}

/**
 * Load prompt presets from localStorage
 */
export function loadPresets(): PromptPreset[] {
    try {
        const stored = localStorage.getItem(PRESETS_KEY);
        if (stored) {
            const customPresets = JSON.parse(stored) as PromptPreset[];
            // Combine defaults with custom, defaults first
            return [...DEFAULT_PRESETS, ...customPresets];
        }
    } catch (e) {
        console.warn('Failed to load presets:', e);
    }
    return [...DEFAULT_PRESETS];
}

/**
 * Save custom preset
 */
export function savePreset(preset: Omit<PromptPreset, 'id'>): PromptPreset {
    const presets = loadPresets().filter(p => !p.isDefault);
    const newPreset: PromptPreset = {
        ...preset,
        id: `custom_${Date.now()}`
    };
    presets.push(newPreset);

    try {
        localStorage.setItem(PRESETS_KEY, JSON.stringify(presets));
    } catch (e) {
        console.warn('Failed to save preset:', e);
    }

    return newPreset;
}

/**
 * Delete custom preset
 */
export function deletePreset(id: string): void {
    const presets = loadPresets().filter(p => !p.isDefault && p.id !== id);
    try {
        localStorage.setItem(PRESETS_KEY, JSON.stringify(presets));
    } catch (e) {
        console.warn('Failed to delete preset:', e);
    }
}

/**
 * Reset settings to defaults
 */
export function resetSettings(): ProcessorSettings {
    try {
        localStorage.removeItem(SETTINGS_KEY);
    } catch (e) {
        console.warn('Failed to reset settings:', e);
    }
    return { ...DEFAULT_SETTINGS };
}
