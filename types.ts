export interface UpscaleResult {
  filename: string;
  originalUrl: string;
  upscaledUrl: string;
  width: number;
  height: number;
  processingTime: number;
  // For export (optional, extracted from URLs if needed)
  originalName?: string;
  originalImage?: string;  // base64
  processedImage?: string; // base64
}

export enum AppState {
  IDLE = 'IDLE',
  CONNECTING = 'CONNECTING',
  PROCESSING = 'PROCESSING',
  RESULTS = 'RESULTS',
  ERROR = 'ERROR'
}

export interface ProcessorSettings {
  backendUrl: string;
  checkpoint: string;
  upscaler: string;

  // Toggles
  enableUpscale: boolean;   // ON/OFF Upscale
  enableTiling: boolean;    // Tiling for large images (faster)
  enableRealism: boolean;   // "Make it Real"
  useCustomRealism: boolean; // Use custom prompt for Make it Real
  realismCustomPrompt: string; // Custom prompt for Make it Real
  enableSkin: boolean;      // "Skin Texture Details"
  enableHiresFix: boolean;  // "Hires Fix" logic
  hiresFixMode: 'normal' | 'advanced'; // New HiresFix mode
  makeItRealDenoise: number; // Denoise for Make It Real KSampler (0.0-1.0)

  // Custom SDXL/HiresFix Advanced Settings
  sdxlSaturation: number; // For FastFilmGrain (Node 100)
  sdxlSteps: number;      // For KSamplers
  sdxlDenoise: number;    // For KSamplers

  enableFaceEnhance: boolean; // GFPGAN face restoration
  enableSDXLUpscale: boolean; // SDXL Realistic Advanced Tiled Upscale

  // Advanced
  upscaleFactor: number;
  denoisingStrength: number;
  cfgScale: number;
  prompt: string;
}

export interface GlobalPreset {
  id: string;
  name: string;
  settings: ProcessorSettings;
  createdAt: number;
}

export interface ServerStatus {
  online: boolean;
  models: string[];
  upscalers: string[];
  missingModels?: string[];
}