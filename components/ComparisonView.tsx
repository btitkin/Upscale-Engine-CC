import React, { useState, useRef, useEffect } from 'react';
import { UpscaleResult } from '../types';
import { Download, Check, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Move, FileText, Archive, Paintbrush, Eye, Image as ImageIcon, Columns } from 'lucide-react';
import MetadataPanel from './MetadataPanel';
import InpaintingModal from './InpaintingModal';
import HistoryToolbar from './HistoryToolbar';
import { exportAsZip } from '../services/exportService';
import { inpaintImage } from '../services/upscaleService';

interface ComparisonViewProps {
  result: UpscaleResult;
  allResults?: UpscaleResult[];  // For batch export
  onClose: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  hasNext: boolean;
  hasPrev: boolean;
  currentCount: number;
  totalCount: number;
  // History props
  canUndo?: boolean;
  canRedo?: boolean;
  onUndo?: () => void;
  onRedo?: () => void;
  showOriginal?: boolean;
  onToggleOriginal?: () => void;
  historyStepInfo?: string;
}

// View modes
type ViewMode = 'original' | 'processed' | 'comparison';

const ComparisonView: React.FC<ComparisonViewProps> = ({
  result, allResults, onClose, onNext, onPrev, hasNext, hasPrev, currentCount, totalCount,
  canUndo, canRedo, onUndo, onRedo, showOriginal, onToggleOriginal, historyStepInfo
}) => {
  const [sliderPos, setSliderPos] = useState(50);
  const containerRef = useRef<HTMLDivElement>(null); // The transformed element
  const viewportRef = useRef<HTMLDivElement>(null);  // The fixed window

  // Interaction States
  const [isSliderDragging, setIsSliderDragging] = useState(false);
  const [isPanning, setIsPanning] = useState(false);

  // View Mode State
  const [viewMode, setViewMode] = useState<ViewMode>('comparison');

  // Transform State
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const startPanRef = useRef({ x: 0, y: 0 });

  const [exportFormat, setExportFormat] = useState<'png' | 'jpg'>('png');
  const [metadataCollapsed, setMetadataCollapsed] = useState(true); // Start collapsed

  // Inpainting state
  const [showInpainting, setShowInpainting] = useState(false);
  const [isInpainting, setIsInpainting] = useState(false);
  const [inpaintedUrl, setInpaintedUrl] = useState<string | null>(null);

  // Reset transform when result changes
  useEffect(() => {
    setScale(1);
    setPan({ x: 0, y: 0 });
    setSliderPos(50);
    setInpaintedUrl(null); // Reset inpainted result
  }, [result]);

  // --- Zoom Logic ---
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!viewportRef.current || !containerRef.current) return;

    const zoomIntensity = 0.1;
    const direction = e.deltaY > 0 ? -1 : 1;
    const factor = direction * zoomIntensity;

    // Calculate new scale
    let newScale = scale + (scale * factor);
    newScale = Math.max(0.25, Math.min(newScale, 8)); // Clamp 0.25x to 8x

    // Get viewport rect
    const viewportRect = viewportRef.current.getBoundingClientRect();

    // Calculate mouse position relative to the viewport center
    const viewportCenterX = viewportRect.width / 2;
    const viewportCenterY = viewportRect.height / 2;
    const mouseX = e.clientX - viewportRect.left;
    const mouseY = e.clientY - viewportRect.top;

    if (newScale <= 1) {
      setPan({ x: 0, y: 0 }); // Reset to center/fit when at or below 100%
    } else {
      // Calculate the offset from center to mouse position
      const offsetX = mouseX - viewportCenterX;
      const offsetY = mouseY - viewportCenterY;

      // The point under the mouse (in pre-zoom coordinates)
      const pointX = (offsetX - pan.x) / scale;
      const pointY = (offsetY - pan.y) / scale;

      // After zoom, this same point should still be at the mouse position
      // newPan + pointInNewScale = offsetFromCenter
      // newPan = offsetFromCenter - point * newScale
      setPan({
        x: offsetX - pointX * newScale,
        y: offsetY - pointY * newScale
      });
    }

    setScale(newScale);
  };

  // Handle zoom slider
  const handleZoomSlider = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newScale = parseFloat(e.target.value);
    setScale(newScale);
    if (newScale <= 1) {
      setPan({ x: 0, y: 0 });
    }
  };

  // --- Interaction Logic ---

  const handleMouseDown = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    const isHandle = target.closest('.slider-handle') !== null;

    if (isHandle || (scale === 1 && !e.button)) {
      setIsSliderDragging(true);
      if (!isHandle && containerRef.current) {
        updateSlider(e.clientX);
      }
    } else if (scale > 1) {
      setIsPanning(true);
      startPanRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };

  const updateSlider = (clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    setSliderPos((x / rect.width) * 100);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isSliderDragging) {
      updateSlider(e.clientX);
    } else if (isPanning) {
      e.preventDefault();
      setPan({
        x: e.clientX - startPanRef.current.x,
        y: e.clientY - startPanRef.current.y
      });
    }
  };

  const handleGlobalUp = () => {
    setIsSliderDragging(false);
    setIsPanning(false);
  };

  useEffect(() => {
    window.addEventListener('mouseup', handleGlobalUp);
    window.addEventListener('mouseleave', handleGlobalUp);
    return () => {
      window.removeEventListener('mouseup', handleGlobalUp);
      window.removeEventListener('mouseleave', handleGlobalUp);
    };
  }, []);

  // --- Download ---
  const handleDownload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = result.width;
    canvas.height = result.height;
    const ctx = canvas.getContext('2d');

    const img = new Image();
    img.src = result.upscaledUrl;

    img.onload = () => {
      if (!ctx) return;

      if (exportFormat === 'jpg') {
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }

      ctx.drawImage(img, 0, 0);

      const mimeType = exportFormat === 'png' ? 'image/png' : 'image/jpeg';
      const quality = exportFormat === 'jpg' ? 0.92 : 1.0;
      const extension = exportFormat;

      const dataUrl = canvas.toDataURL(mimeType, quality);

      const link = document.createElement('a');
      link.href = dataUrl;
      const stem = result.filename.substring(0, result.filename.lastIndexOf('.')) || 'render';
      link.download = `${stem}_${result.width}x${result.height}_lumascale.${extension}`;
      link.click();
    };
  };

  // Track original image dimensions
  const [originalDimensions, setOriginalDimensions] = useState<{ width: number, height: number } | null>(null);

  // Load original image dimensions
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setOriginalDimensions({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.src = result.originalUrl;
  }, [result.originalUrl]);

  return (
    <div className="flex-1 h-full flex flex-col bg-[#050505]">
      {/* Minimal Top Bar - Just Back and Navigation */}
      <div className="h-10 border-b border-white/10 flex items-center justify-between px-4 bg-app-panel z-20 relative">
        <div className="flex items-center gap-4 text-xs">
          <button onClick={onClose} className="px-3 py-1 bg-white/5 hover:bg-white/10 rounded text-white/60 hover:text-white font-bold transition-colors">
            BACK
          </button>

          {totalCount > 1 && (
            <div className="flex items-center bg-black/40 rounded border border-white/5">
              <button
                onClick={onPrev}
                disabled={!hasPrev}
                className={`p-1.5 ${!hasPrev ? 'text-white/10' : 'text-white hover:bg-white/10'} border-r border-white/5`}
              >
                <ChevronLeft size={14} />
              </button>
              <span className="px-3 font-mono text-white/80">
                {currentCount} / {totalCount}
              </span>
              <button
                onClick={onNext}
                disabled={!hasNext}
                className={`p-1.5 ${!hasNext ? 'text-white/10' : 'text-white hover:bg-white/10'} border-l border-white/5`}
              >
                <ChevronRight size={14} />
              </button>
            </div>
          )}

          <span className="text-white/40 border-l border-white/10 pl-4">File:</span>
          <span className="font-mono text-white max-w-[150px] truncate" title={result.filename}>{result.filename}</span>
        </div>

        {/* Zoom Indicator */}
        <div className="flex items-center gap-2 text-app-muted">
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${scale > 1 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/5'}`}>
            {Math.round(scale * 100)}%
          </span>
          {scale > 1 && <span className="text-[10px] opacity-50 flex items-center gap-1"><Move size={10} /> DRAG TO PAN</span>}
        </div>
      </div>

      {/* Viewport - Captures events */}
      <div
        ref={viewportRef}
        className="flex-1 relative overflow-hidden flex items-center justify-center bg-[#09090b] select-none cursor-default"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
      >
        {/* Content Container - Transformed */}
        <div
          ref={containerRef}
          className="relative shadow-2xl bg-[#111] group origin-center will-change-transform"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
            cursor: isPanning ? 'grabbing' : (scale > 1 ? 'grab' : 'default'),
            transition: isPanning ? 'none' : 'transform 0.1s ease-out'
          }}
        >
          {/* View Mode: Original Only */}
          {viewMode === 'original' && (
            <img
              src={result.originalUrl}
              alt="Original"
              className="block max-w-[calc(100vw-64px)] max-h-[calc(100vh-160px)] w-auto h-auto object-contain pointer-events-none"
              draggable={false}
            />
          )}

          {/* View Mode: Processed Only */}
          {viewMode === 'processed' && (
            <img
              src={inpaintedUrl || result.upscaledUrl}
              alt="Processed"
              className="block max-w-[calc(100vw-64px)] max-h-[calc(100vh-160px)] w-auto h-auto object-contain pointer-events-none"
              draggable={false}
            />
          )}

          {/* View Mode: Comparison with Slider */}
          {viewMode === 'comparison' && (
            <>
              {/* Driver Image (Processed) */}
              <img
                src={inpaintedUrl || result.upscaledUrl}
                alt="Luma Render"
                className="block max-w-[calc(100vw-64px)] max-h-[calc(100vh-160px)] w-auto h-auto object-contain pointer-events-none"
                draggable={false}
              />

              {/* Overlay Image (Original) */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{ clipPath: `inset(0 ${100 - sliderPos}% 0 0)` }}
              >
                <img
                  src={result.originalUrl}
                  alt="Original"
                  className="w-full h-full object-contain"
                />
              </div>

              {/* Slider Handle */}
              <div
                className="slider-handle absolute top-0 bottom-0 w-1 bg-white cursor-ew-resize z-20 flex items-center justify-center group-hover:shadow-[0_0_15px_rgba(255,255,255,0.5)] transition-shadow"
                style={{ left: `${sliderPos}%`, transform: 'translateX(-50%)' }}
              >
                <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center shadow-lg transform transition-transform hover:scale-110 pointer-events-none">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="black" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6" /></svg>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="black" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="rotate-180 absolute"><path d="m9 18 6-6-6-6" /></svg>
                </div>
              </div>

              {/* Labels with Resolution */}
              {scale < 2 && (
                <>
                  <div className="absolute bottom-4 left-4 bg-black/50 backdrop-blur px-2 py-1 rounded text-[10px] font-bold text-white/80 pointer-events-none z-10 border border-white/10">
                    ORIGINAL {originalDimensions && <span className="text-white/50 ml-1">{originalDimensions.width}×{originalDimensions.height}</span>}
                  </div>
                  <div className="absolute bottom-4 right-4 bg-emerald-900/50 backdrop-blur px-2 py-1 rounded text-[10px] font-bold text-emerald-400 pointer-events-none z-10 border border-emerald-500/20">
                    PROCESSED <span className="text-emerald-300/70 ml-1">{result.width}×{result.height}</span>
                  </div>
                </>
              )}
            </>
          )}

          {/* Mode Label for single views with Resolution */}
          {viewMode !== 'comparison' && scale < 2 && (
            <div className={`absolute bottom-4 left-4 backdrop-blur px-2 py-1 rounded text-[10px] font-bold pointer-events-none z-10 border ${viewMode === 'original'
              ? 'bg-blue-900/50 text-blue-400 border-blue-500/20'
              : 'bg-emerald-900/50 text-emerald-400 border-emerald-500/20'
              }`}>
              {viewMode === 'original' ? (
                <>ORIGINAL {originalDimensions && <span className="opacity-70 ml-1">{originalDimensions.width}×{originalDimensions.height}</span>}</>
              ) : (
                <>PROCESSED <span className="opacity-70 ml-1">{result.width}×{result.height}</span></>
              )}
            </div>
          )}
        </div>

        {/* History Toolbar - floating at bottom of viewport */}
        {onUndo && onRedo && onToggleOriginal && (
          <HistoryToolbar
            canUndo={canUndo ?? false}
            canRedo={canRedo ?? false}
            onUndo={onUndo}
            onRedo={onRedo}
            showOriginal={showOriginal ?? false}
            onToggleOriginal={onToggleOriginal}
            historyStepInfo={historyStepInfo}
          />
        )}
      </div>

      {/* Bottom Toolbar - View Mode, Zoom, Export */}
      <div className="h-12 border-t border-white/10 flex items-center justify-between px-4 bg-app-panel z-20 relative shrink-0">
        <div className="flex items-center gap-3">
          {/* View Mode Selector */}
          <div className="flex items-center bg-black/40 rounded-lg p-0.5 border border-white/10">
            <button
              onClick={() => setViewMode('original')}
              className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all flex items-center gap-1.5 ${viewMode === 'original' ? 'bg-blue-500/30 text-blue-400 shadow-sm' : 'text-white/40 hover:text-white/60'}`}
              title="Show original image"
            >
              <Eye size={12} /> Original
            </button>
            <div className="w-px h-3 bg-white/10 mx-0.5"></div>
            <button
              onClick={() => setViewMode('processed')}
              className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all flex items-center gap-1.5 ${viewMode === 'processed' ? 'bg-emerald-500/30 text-emerald-400 shadow-sm' : 'text-white/40 hover:text-white/60'}`}
              title="Show processed image"
            >
              <ImageIcon size={12} /> Processed
            </button>
            <div className="w-px h-3 bg-white/10 mx-0.5"></div>
            <button
              onClick={() => setViewMode('comparison')}
              className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all flex items-center gap-1.5 ${viewMode === 'comparison' ? 'bg-purple-500/30 text-purple-400 shadow-sm' : 'text-white/40 hover:text-white/60'}`}
              title="Split comparison view"
            >
              <Columns size={12} /> Compare
            </button>
          </div>

          {/* Zoom Slider */}
          <div className="flex items-center gap-2 bg-black/40 rounded-lg px-2 py-1 border border-white/10">
            <ZoomOut size={12} className="text-white/40" />
            <input
              type="range"
              min="0.25"
              max="8"
              step="0.1"
              value={scale}
              onChange={handleZoomSlider}
              className="w-20 h-1 accent-emerald-500 cursor-pointer"
              title={`Zoom: ${Math.round(scale * 100)}%`}
            />
            <ZoomIn size={12} className="text-white/40" />
            <span className="text-[10px] font-mono text-white/60 w-8">{Math.round(scale * 100)}%</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Format Selector */}
          <div className="flex items-center bg-black/40 rounded-lg p-0.5 border border-white/10">
            <button
              onClick={() => setExportFormat('png')}
              className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all flex items-center gap-1.5 ${exportFormat === 'png' ? 'bg-white/20 text-white shadow-sm' : 'text-white/40 hover:text-white/60'}`}
            >
              PNG {exportFormat === 'png' && <Check size={10} />}
            </button>
            <div className="w-px h-3 bg-white/10 mx-0.5"></div>
            <button
              onClick={() => setExportFormat('jpg')}
              className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all flex items-center gap-1.5 ${exportFormat === 'jpg' ? 'bg-white/20 text-white shadow-sm' : 'text-white/40 hover:text-white/60'}`}
            >
              JPG {exportFormat === 'jpg' && <Check size={10} />}
            </button>
          </div>

          {/* Edit Regions (Inpainting) */}
          <button
            onClick={() => setShowInpainting(true)}
            className="px-3 py-1.5 text-xs font-bold rounded flex items-center gap-2 bg-gradient-to-r from-purple-500/20 to-pink-500/20 text-purple-400 hover:from-purple-500/30 hover:to-pink-500/30 border border-purple-500/30 transition-all"
            title="Edit specific regions with AI"
          >
            <Paintbrush size={12} />
            EDIT REGIONS
          </button>

          <button
            onClick={() => setMetadataCollapsed(!metadataCollapsed)}
            className={`px-3 py-1.5 text-xs font-bold rounded flex items-center gap-2 transition-colors ${!metadataCollapsed
              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
              : 'bg-white/5 text-white/60 hover:bg-white/10 hover:text-white border border-white/10'
              }`}
          >
            <FileText size={12} /> INFO
          </button>

          <button onClick={handleDownload} className="px-4 py-1.5 bg-white text-black text-xs font-bold rounded hover:bg-gray-200 flex items-center gap-2 transition-colors">
            <Download size={12} /> EXPORT
          </button>

          {/* Export All ZIP - only show if multiple results */}
          {allResults && allResults.length > 1 && (
            <button
              onClick={() => exportAsZip(allResults, { format: exportFormat === 'jpg' ? 'jpeg' : 'png' })}
              className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded flex items-center gap-2 transition-colors"
              title={`Export all ${allResults.length} images as ZIP`}
            >
              <Archive size={12} /> ZIP ({allResults.length})
            </button>
          )}
        </div>
      </div>

      {/* Metadata Panel - Always show with collapse toggle */}
      <MetadataPanel
        imageUrl={inpaintedUrl || result.upscaledUrl}
        filename={result.filename}
        collapsed={metadataCollapsed}
        onToggle={() => setMetadataCollapsed(!metadataCollapsed)}
      />

      {/* Inpainting Modal */}
      {showInpainting && (
        <InpaintingModal
          imageUrl={inpaintedUrl || result.upscaledUrl}
          imageWidth={result.width}
          imageHeight={result.height}
          onClose={() => setShowInpainting(false)}
          isProcessing={isInpainting}
          onApply={async (maskDataUrl, prompt, strength) => {
            setIsInpainting(true);
            try {
              // Extract base64 from data URL
              const imageB64 = (inpaintedUrl || result.upscaledUrl).split(',')[1];

              const res = await inpaintImage(
                'http://127.0.0.1:5555', // TODO: Get from settings
                imageB64,
                maskDataUrl,
                prompt,
                strength
              );

              // Update with inpainted result
              setInpaintedUrl(`data:image/png;base64,${res.image}`);
              setShowInpainting(false);
            } catch (err) {
              console.error('Inpainting failed:', err);
              alert(`Inpainting failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
            } finally {
              setIsInpainting(false);
            }
          }}
        />
      )}
    </div>
  );
};

export default ComparisonView;
