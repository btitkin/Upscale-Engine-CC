export interface UpscaleResult {
  filename: string;
  originalUrl: string;
  upscaledUrl: string;
  width: number;
  height: number;
  processingTime: number;
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
  enableSkin: boolean;      // "Skin Texture Details"
  enableHiresFix: boolean;  // "Hires Fix" logic

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
}