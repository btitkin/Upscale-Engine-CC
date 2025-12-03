import React, { useState, useEffect } from 'react';
import { Cpu, Activity, Zap, HardDrive, Monitor, Thermometer } from 'lucide-react';

interface SystemMetrics {
  cpu: { load: number };
  memory: { used: string; total: string };
  gpu: { name: string; vramUsed: string; vramTotal: number; load: number; temp: number };
}

declare global {
  interface Window {
    electron?: {
      getSystemInfo: () => Promise<SystemMetrics>;
    };
  }
}

const TitleBar: React.FC = () => {
  const [gpuInfo, setGpuInfo] = useState<string>('Detecting GPU...');
  const [stats, setStats] = useState<SystemMetrics>({
    cpu: { load: 0 },
    memory: { used: '0', total: '64' },
    gpu: { name: 'Unknown GPU', vramUsed: '0', vramTotal: 12, load: 0, temp: 0 }
  });

  useEffect(() => {
    // Detect GPU from WebGL (for display name)
    const detectGPU = () => {
      try {
        const canvas = document.createElement('canvas');
        const gl = (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')) as WebGLRenderingContext;

        if (gl) {
          const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
          if (debugInfo) {
            const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);

            if (renderer.includes('ANGLE (')) {
              const parts = renderer.replace(/^ANGLE \((.+)\)$/, '$1').split(',');
              if (parts.length > 1) {
                return parts[1].trim();
              }
            }
            return renderer;
          }
        }
        return 'Standard Graphics Adapter';
      } catch (e) {
        return 'Integrated Graphics';
      }
    };

    setGpuInfo(detectGPU());

    // Get real system metrics from Electron
    const updateMetrics = async () => {
      try {
        if (window.electron?.getSystemInfo) {
          const sysInfo = await window.electron.getSystemInfo();
          setStats(sysInfo);
        }
      } catch (error) {
        console.error('Failed to get system metrics:', error);
      }
    };

    // Update immediately and then every 2 seconds
    updateMetrics();
    const interval = setInterval(updateMetrics, 2000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-10 bg-black flex items-center justify-between px-4 border-b border-white/10 select-none drag-region overflow-hidden">
      <div className="flex items-center gap-4 shrink-0">
        {/* Window Controls */}
        <div className="flex items-center gap-2 group">
          <div className="w-3 h-3 rounded-full bg-red-500/80 group-hover:bg-red-500 transition-colors"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-500/80 group-hover:bg-yellow-500 transition-colors"></div>
          <div className="w-3 h-3 rounded-full bg-green-500/80 group-hover:bg-green-500 transition-colors"></div>
        </div>

        <div className="h-4 w-px bg-white/10 mx-2"></div>

        <span className="text-xs font-medium text-white/60 font-mono flex items-center gap-2 hidden sm:flex">
          Upscale Engine CC <span className="text-white/20">Local Host</span>
        </span>
      </div>

      {/* Hardware Monitor - Real Data */}
      <div className="flex items-center gap-4 md:gap-6 text-[10px] font-medium text-white/40 uppercase tracking-widest shrink-0 font-mono">

        {/* GPU NAME */}
        <div className="flex items-center gap-2 text-white/60 whitespace-nowrap shrink-0 font-sans">
          <Monitor size={12} className="text-indigo-400" />
          <span className="hidden md:inline">{gpuInfo}</span>
          <span className="md:hidden">GPU</span>
        </div>

        <div className="h-3 w-px bg-white/10 hidden md:block"></div>

        {/* GPU LOAD */}
        <div className="flex items-center gap-1.5 w-[60px] md:w-auto whitespace-nowrap">
          <Zap size={12} className={stats.gpu.load > 80 ? 'text-red-500' : 'text-yellow-500'} />
          <span>GPU: <span className="text-white">{stats.gpu.load || 'N/A'}%</span></span>
        </div>

        {/* VRAM */}
        <div className="flex items-center gap-1.5 w-auto whitespace-nowrap">
          <Activity size={12} className="text-blue-500" />
          <span>VRAM: <span className="text-white">{stats.gpu.vramUsed}</span> <span className="text-white/30">/</span> {stats.gpu.vramTotal} GB</span>
        </div>

        {/* CPU - Real */}
        <div className="flex items-center gap-1.5 hidden lg:flex whitespace-nowrap">
          <Cpu size={12} className="text-emerald-500" />
          <span>CPU: <span className="text-white">{stats.cpu.load}%</span></span>
        </div>

        {/* RAM - Real */}
        <div className="flex items-center gap-1.5 hidden lg:flex whitespace-nowrap">
          <HardDrive size={12} className="text-orange-500" />
          <span>RAM: <span className="text-white">{stats.memory.used}</span> <span className="text-white/30">/</span> {stats.memory.total} GB</span>
        </div>

        {/* TEMP */}
        {stats.gpu.temp > 0 && (
          <div className="flex items-center gap-1.5 hidden xl:flex whitespace-nowrap">
            <Thermometer size={12} className={stats.gpu.temp > 75 ? 'text-red-400' : 'text-gray-400'} />
            <span className={stats.gpu.temp > 75 ? 'text-red-400' : 'text-white'}>{stats.gpu.temp}°C</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default TitleBar;