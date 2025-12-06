import React, { useState, useEffect } from 'react';
import { ProcessorSettings, ServerStatus } from '../types';
import { Sliders, Zap, Activity, Server, RefreshCw, AlertCircle, ToggleLeft, ToggleRight, Check, Download } from 'lucide-react';
import { checkServerStatus, setServerModel, downloadModels } from '../services/upscaleService';
import { loadPresets, PromptPreset } from '../services/settingsService';

interface SidebarProps {
  settings: ProcessorSettings;
  setSettings: (s: ProcessorSettings) => void;
  disabled: boolean;
  onProcess: () => void;
  queueCount: number;
  // Progress props
  progress?: number;
  step?: string;
  eta?: string;
}

const Sidebar: React.FC<SidebarProps> = ({ settings, setSettings, disabled, onProcess, queueCount, progress, step, eta }) => {
  const [serverStatus, setServerStatus] = useState<ServerStatus>({ online: false, models: [], upscalers: [] });
  const [isChecking, setIsChecking] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<{
    percent: number;
    model: string;
    speed_mbps: number;
  } | null>(null);
  const [presets] = useState<PromptPreset[]>(loadPresets);

  // Poll download progress
  useEffect(() => {
    if (!isDownloading) return;

    const pollProgress = async () => {
      try {
        const res = await fetch(`${settings.backendUrl}/models/download/progress`);
        const data = await res.json();
        if (data.active) {
          setDownloadProgress({
            percent: data.percent,
            model: data.model,
            speed_mbps: data.speed_mbps
          });
        } else {
          setDownloadProgress(null);
          setIsDownloading(false);
          await checkConnection(); // Refresh status
        }
      } catch (e) {
        console.error("Progress poll failed:", e);
      }
    };

    const interval = setInterval(pollProgress, 500);
    return () => clearInterval(interval);
  }, [isDownloading, settings.backendUrl]);

  const handleDownload = async () => {
    setIsDownloading(true);
    setDownloadProgress({ percent: 0, model: "Starting...", speed_mbps: 0 });
    try {
      // Fire and forget - we poll for progress
      fetch(`${settings.backendUrl}/models/download`, { method: 'POST' });
    } catch (e) {
      console.error(e);
      alert("Download failed. Check backend console.");
      setIsDownloading(false);
      setDownloadProgress(null);
    }
  };

  const checkConnection = async () => {
    setIsChecking(true);
    const status = await checkServerStatus(settings.backendUrl);
    setServerStatus(status);
    setIsChecking(false);
  };

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 10000);
    return () => clearInterval(interval);
  }, [settings.backendUrl]);

  const update = (key: keyof ProcessorSettings, value: any) => {
    setSettings({ ...settings, [key]: value });
  };

  const handleModelChange = (model: string) => {
    update('checkpoint', model);
    if (serverStatus.online) {
      setServerModel(settings.backendUrl, model);
    }
  };

  // Helper Toggle Component
  const ToggleItem = ({ label, active, onClick, description }: { label: string, active: boolean, onClick: () => void, description?: string }) => (
    <div className="flex flex-col gap-1">
      <button
        onClick={onClick}
        className={`w-full flex items-center justify-between p-3 rounded border transition-all ${active ? 'bg-white/10 border-emerald-500/50' : 'bg-black/20 border-white/5 hover:border-white/10'}`}
      >
        <span className={`text-xs font-bold ${active ? 'text-white' : 'text-white/60'}`}>{label}</span>
        <div className={`transition-colors ${active ? 'text-emerald-400' : 'text-white/20'}`}>
          {active ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
        </div>
      </button>
      {description && active && <p className="text-[10px] text-emerald-500/80 px-1">{description}</p>}
    </div>
  );

  return (
    <div className="w-80 h-full bg-app-panel border-r border-app-border flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-app-border">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Sliders size={18} className="text-emerald-500" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Engine Settings</h2>
          </div>
          <button
            onClick={checkConnection}
            className="p-1.5 hover:bg-white/5 rounded transition-colors"
            disabled={isChecking}
          >
            <RefreshCw size={14} className={`text-white/40 ${isChecking ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Backend Status Indicator */}
        {/* Backend Status Indicator */}
        <div className="flex flex-col gap-2">
          <div className={`flex items-center gap-2 px-2 py-1 rounded text-[10px] font-bold ${serverStatus.online ? 'bg-emerald-900/30 text-emerald-400' : 'bg-red-900/30 text-red-400'}`}>
            <Server size={12} />
            {serverStatus.online ? 'LOCAL BACKEND' : 'BACKEND OFFLINE'}
          </div>

          {serverStatus.online && serverStatus.missingModels && serverStatus.missingModels.length > 0 && (
            isDownloading && downloadProgress ? (
              <div className="w-full p-2 bg-blue-900/30 border border-blue-500/30 rounded">
                <div className="flex justify-between text-[10px] text-blue-300 mb-1">
                  <span className="truncate max-w-[60%]">{downloadProgress.model}</span>
                  <span className="font-mono">{downloadProgress.speed_mbps} MB/s</span>
                </div>
                <div className="w-full h-2 bg-black/50 rounded overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-300"
                    style={{ width: `${downloadProgress.percent}%` }}
                  />
                </div>
                <div className="text-center text-[11px] font-bold text-blue-400 mt-1">
                  {downloadProgress.percent}%
                </div>
              </div>
            ) : (
              <button
                onClick={handleDownload}
                disabled={isDownloading}
                className="w-full flex items-center justify-center gap-2 px-2 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-[10px] font-bold transition-colors shadow-lg shadow-blue-900/20"
              >
                <Download size={12} />
                DOWNLOAD MISSING MODELS
              </button>
            )
          )}
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="p-4 space-y-4">

          {/* TOGGLES SECTION */}
          <div>
            <label className="text-[10px] uppercase tracking-widest text-app-muted font-bold mb-2 block">Processing Modules</label>

            {/* 1. REALISM */}
            <ToggleItem
              label="MAKE IT REAL"
              active={settings.enableRealism}
              onClick={() => update('enableRealism', !settings.enableRealism)}
              description="Uses Qwen VL to remaster details with photorealistic accuracy."
            />

            {/* Custom Prompt Option (visible when Make it Real is enabled) */}
            {settings.enableRealism && (
              <div className="pl-2 border-l-2 border-emerald-500/30 space-y-2 mt-2 mb-2 transition-all">
                {/* Prompt Presets */}
                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-wider text-white/40 font-bold">Prompt Preset</label>
                  <select
                    value={settings.useCustomRealism ? 'custom' : (settings.realismCustomPrompt || presets[0]?.prompt || '')}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === 'custom') {
                        update('useCustomRealism', true);
                      } else {
                        update('useCustomRealism', false);
                        update('realismCustomPrompt', val);
                      }
                    }}
                    className="w-full px-3 py-2 text-xs bg-[#1a1a1a] border border-white/10 rounded-lg text-white/90 focus:border-emerald-500/50 focus:outline-none cursor-pointer"
                  >
                    {presets.map((preset) => (
                      <option key={preset.id} value={preset.prompt} className="bg-[#1a1a1a] text-white">
                        {preset.name}
                      </option>
                    ))}
                    <option value="custom" className="bg-[#1a1a1a] text-white">✏️ Custom Prompt...</option>
                  </select>
                </div>

                {/* Custom Prompt Textarea (visible when Custom selected) */}
                {settings.useCustomRealism && (
                  <textarea
                    value={settings.realismCustomPrompt}
                    onChange={(e) => update('realismCustomPrompt', e.target.value)}
                    placeholder="Enter your custom prompt... (e.g., 'make it photorealistic with dramatic lighting')"
                    className="w-full h-20 px-3 py-2 text-xs bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:border-emerald-500/50 focus:outline-none resize-none"
                  />
                )}
              </div>
            )}

            {/* 2. SKIN TEXTURE */}
            <ToggleItem
              label="SKIN TEXTURE DETAILS"
              active={settings.enableSkin}
              onClick={() => update('enableSkin', !settings.enableSkin)}
              description="Injects pore-level details and micro-contrast."
            />

            {/* 3. HIRES FIX */}
            <ToggleItem
              label="HIRES FIX"
              active={settings.enableHiresFix}
              onClick={() => update('enableHiresFix', !settings.enableHiresFix)}
              description="Reduces hallucinations during enhancement."
            />

            {/* 4. FACE ENHANCE */}
            <ToggleItem
              label="FACE ENHANCE 👤"
              active={settings.enableFaceEnhance}
              onClick={() => update('enableFaceEnhance', !settings.enableFaceEnhance)}
              description="GFPGAN face restoration and enhancement."
            />

            {/* 5. UPSCALE */}
            <ToggleItem
              label="UPSCALE IMAGE"
              active={settings.enableUpscale}
              onClick={() => update('enableUpscale', !settings.enableUpscale)}
            />
          </div>

          {/* CONDITIONAL UPSCALE OPTIONS */}
          {
            settings.enableUpscale && (
              <div className="pl-2 border-l-2 border-white/10 space-y-3 transition-all fade-in">

                {/* Tiling Toggle */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="tiling-toggle"
                    checked={settings.enableTiling}
                    onChange={(e) => update('enableTiling', e.target.checked)}
                    className="w-4 h-4 rounded accent-emerald-500"
                  />
                  <label htmlFor="tiling-toggle" className="text-xs text-white/80 cursor-pointer">
                    Enable Tiling (512px - Faster)
                  </label>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-app-muted">Scale Factor</label>
                  <div className="flex bg-black/40 rounded p-1 border border-white/5">
                    {[2, 4].map((val) => (
                      <button
                        key={val}
                        onClick={() => update('upscaleFactor', val)}
                        className={`flex-1 py-1 text-xs font-bold rounded transition-all ${settings.upscaleFactor === val ? 'bg-emerald-600 text-white' : 'text-gray-500 hover:text-gray-300'}`}
                      >
                        {val}x
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-app-muted">Upscaler Algorithm</label>
                  <select
                    value={settings.upscaler}
                    onChange={(e) => update('upscaler', e.target.value)}
                    disabled={!serverStatus.online}
                    className="w-full bg-[#1a1a1a] border border-white/10 rounded px-2 py-1 text-xs text-white appearance-none outline-none"
                  >
                    {serverStatus.upscalers.length > 0 ? (
                      serverStatus.upscalers.map(u => <option key={u} value={u} className="bg-[#1a1a1a] text-white">{u}</option>)
                    ) : (
                      <option value="RealESRGAN x4plus" className="bg-[#1a1a1a] text-white">RealESRGAN x4plus</option>
                    )}
                  </select>
                </div>
              </div>
            )
          }

          {/* MANUAL OVERRIDES (Collapsed/Small) */}
          <div className="pt-4 border-t border-white/5 space-y-4 opacity-80 hover:opacity-100 transition-opacity">
            <label className="text-[10px] uppercase tracking-widest text-app-muted font-bold">Manual Overrides</label>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Denoising (Influence)</span>
                <span className="font-mono text-emerald-400 font-bold">{settings.denoisingStrength.toFixed(2)}</span>
              </div>
              <input
                type="range" min="0" max="100"
                value={settings.denoisingStrength * 100}
                onChange={(e) => update('denoisingStrength', parseInt(e.target.value) / 100)}
                className="w-full accent-emerald-500"
              />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">CFG Scale</span>
                <span className="font-mono text-white/60">{settings.cfgScale}</span>
              </div>
              <input
                type="range" min="1" max="15" step="0.5"
                value={settings.cfgScale}
                onChange={(e) => update('cfgScale', parseFloat(e.target.value))}
                className="w-full"
              />
            </div>
          </div>

        </div>
      </div>

      <div className="p-4 border-t border-app-border bg-black/20">
        {disabled ? (
          <div className="space-y-3">
            {/* Progress Info */}
            <div className="flex justify-between items-end">
              <div className="flex flex-col">
                <span className="text-xs font-bold text-white tracking-wide">
                  Processing... {Math.round(progress || 0)}%
                </span>
                {eta && (
                  <span className="text-[10px] text-emerald-400/80 font-mono mt-0.5">
                    ETA: {eta}
                  </span>
                )}
              </div>
              <Activity size={14} className="text-emerald-500 animate-pulse mb-1" />
            </div>

            {/* Progress Bar */}
            <div className="h-2 bg-black/50 rounded-full overflow-hidden border border-white/5">
              <div
                className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all duration-300 ease-out"
                style={{ width: `${progress || 0}%` }}
              />
            </div>

            {/* Cancel Button (Small) */}
            <button
              onClick={onProcess} // This will trigger cancel if we change the handler in App.tsx or add a specific onCancel prop
              className="w-full py-1.5 text-[10px] text-white/40 hover:text-red-400 transition-colors uppercase tracking-wider"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={onProcess}
            disabled={!serverStatus.online}
            className={`w-full py-3 rounded text-sm font-bold tracking-wide flex items-center justify-center gap-2 transition-all
              ${!serverStatus.online ? 'bg-white/5 text-white/20 cursor-not-allowed' : 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-lg shadow-emerald-900/20'}
            `}
          >
            {!serverStatus.online ? (
              'OFFLINE'
            ) : (
              <>
                <Zap size={16} fill="currentColor" /> RENDER
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};

export default Sidebar;