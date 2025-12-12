import { ProcessorSettings, GlobalPreset } from '../types';

const SETTINGS_KEY = 'lumascale_settings';
const PRESETS_KEY = 'lumascale_presets';
const GLOBAL_PRESETS_KEY = 'lumascale_global_presets';
const SETTINGS_VERSION_KEY = 'lumascale_settings_version';
const CURRENT_VERSION = 7;  // Version 7: Added SDXL Advanced Settings (Sat, Steps, Denoise) & Global Presets

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
    realismCustomPrompt: 'realistic face, real eyes, realistic, (real,realistic,raw,photo,source_realistic:1.8), realistic body,',  // Default prompt for SDXL Make it Real workflow
    enableSkin: true,
    enableHiresFix: true,
    hiresFixMode: 'normal',
    makeItRealDenoise: 0.6,

    // SDXL Advanced Defaults
    sdxlSaturation: 0.3, // Reverted to original workflow value
    sdxlSteps: 8,
    sdxlDenoise: 0.55, // Reverted to 0.55 as requested

    enableFaceEnhance: false,
    enableSDXLUpscale: false,
    upscaleFactor: 2,
    denoisingStrength: 0.25,
    cfgScale: 7.0,
    prompt: ''
};

const DEFAULT_PRESETS: PromptPreset[] = [
    {
        id: 'anime-to-real',
        name: '🎨 Anime to Real (Best)',
        prompt: 'realistic face, real eyes, realistic, (real,realistic,raw,photo,source_realistic:1.8), realistic body,',
        isDefault: true
    },
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

const DEFAULT_GLOBAL_PRESETS: GlobalPreset[] = [
    {
        id: 'default',
        name: '🔒 Upscale Engine CC Default',
        settings: { ...DEFAULT_SETTINGS },
        createdAt: 0
    }
];

/**
 * Load settings from localStorage
 */
export function loadSettings(): ProcessorSettings {
    try {
        // Check if settings version is outdated
        const storedVersion = localStorage.getItem(SETTINGS_VERSION_KEY);
        const version = storedVersion ? parseInt(storedVersion, 10) : 0;

        if (version < CURRENT_VERSION) {
            // Settings are outdated - clear and use defaults
            console.log(`Settings outdated (v${version} < v${CURRENT_VERSION}), resetting to defaults`);
            localStorage.removeItem(SETTINGS_KEY);
            localStorage.setItem(SETTINGS_VERSION_KEY, CURRENT_VERSION.toString());
            return { ...DEFAULT_SETTINGS };
        }

        const stored = localStorage.getItem(SETTINGS_KEY);
        if (stored) {
            const parsed = JSON.parse(stored);
            // Merge with defaults to ensure all keys exist
            return { ...DEFAULT_SETTINGS, ...parsed };
        }
    } catch (e) {
        console.warn('Failed to load settings:', e);
    }
    localStorage.setItem(SETTINGS_VERSION_KEY, CURRENT_VERSION.toString());
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
 * Load Global Presets
 */
export function loadGlobalPresets(): GlobalPreset[] {
    try {
        const stored = localStorage.getItem(GLOBAL_PRESETS_KEY);
        if (stored) {
            const customPresets = JSON.parse(stored) as GlobalPreset[];
            return [...DEFAULT_GLOBAL_PRESETS, ...customPresets];
        }
    } catch (e) {
        console.warn('Failed to load global presets:', e);
    }
    return [...DEFAULT_GLOBAL_PRESETS];
}

/**
 * Save Global Preset
 */
export function saveGlobalPreset(name: string, settings: ProcessorSettings): GlobalPreset {
    const presets = loadGlobalPresets().filter(p => p.id !== 'default');
    const newPreset: GlobalPreset = {
        id: `global_${Date.now()}`,
        name,
        settings: { ...settings },
        createdAt: Date.now()
    };
    presets.push(newPreset);

    try {
        localStorage.setItem(GLOBAL_PRESETS_KEY, JSON.stringify(presets));
    } catch (e) {
        console.warn('Failed to save global preset:', e);
    }

    return newPreset;
}

/**
 * Delete Global Preset
 */
export function deleteGlobalPreset(id: string): void {
    if (id === 'default') return; // Cannot delete default

    const presets = loadGlobalPresets().filter(p => p.id !== 'default' && p.id !== id);
    try {
        localStorage.setItem(GLOBAL_PRESETS_KEY, JSON.stringify(presets));
    } catch (e) {
        console.warn('Failed to delete global preset:', e);
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
