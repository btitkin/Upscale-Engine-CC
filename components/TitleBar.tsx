import React from 'react';

const TitleBar: React.FC = () => {
  return (
    <div className="h-10 bg-black flex items-center justify-between px-4 border-b border-white/10 select-none drag-region overflow-hidden">
      <div className="flex items-center gap-4 shrink-0">
        <div className="flex items-center gap-2 group">
          <div className="w-3 h-3 rounded-full bg-red-500/80 group-hover:bg-red-500 transition-colors"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-500/80 group-hover:bg-yellow-500 transition-colors"></div>
          <div className="w-3 h-3 rounded-full bg-green-500/80 group-hover:bg-green-500 transition-colors"></div>
        </div>

        <div className="h-4 w-px bg-white/10 mx-2"></div>

        <span className="text-xs font-medium text-white/60 font-mono flex items-center gap-2">
          Upscale Engine CC <span className="text-white/20">Local Host</span>
        </span>
      </div>

      <div className="text-[10px] text-white/30 font-mono">
        v1.0
      </div>
    </div>
  );
};

export default TitleBar;