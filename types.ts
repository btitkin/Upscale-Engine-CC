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
  enableFaceEnhance: boolean; // GFPGAN face restoration

  // Advanced
  upscaleFactor: number;
  denoisingStrength: number;
  cfgScale: number;
  prompt: string;
}

export interface ServerStatus {
  online: boolean;
  models: string[];
  upscalers: string[];
  missingModels?: string[];
}