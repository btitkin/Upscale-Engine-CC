import React, { useState, useEffect, useRef, useCallback } from 'react';
import TitleBar from './components/TitleBar';
import Sidebar from './components/Sidebar';
import ImageUploader from './components/ImageUploader';
import ComparisonView from './components/ComparisonView';
import BatchQueue from './components/BatchQueue';
import MetadataPanel from './components/MetadataPanel';
import LoadingScreen from './components/LoadingScreen';
import HistoryToolbar from './components/HistoryToolbar';
import { processImageLocally, processImageFromBase64, cancelProcessing as cancelBackend, ProgressUpdate } from './services/upscaleService';
import { loadSettings, saveSettings } from './services/settingsService';
import { AppState, UpscaleResult, ProcessorSettings } from './types';
import { Layers, ZoomIn, ZoomOut } from 'lucide-react';
import { useLivePreview } from './hooks/useLivePreview';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useProgressETA } from './hooks/useProgressETA';
import { useImageHistory } from './hooks/useImageHistory';

interface QueueImage {
  id: string;
  file: File;
  preview: string;
  selected: boolean;
  processed: boolean;
  processing: boolean;
}

const App: React.FC = () => {
  const [state, setState] = useState<AppState>(AppState.IDLE);
  const [queue, setQueue] = useState<File[]>([]);
  const [queueImages, setQueueImages] = useState<QueueImage[]>([]);
  const [results, setResults] = useState<UpscaleResult[]>([]);
  const [currentResultIndex, setCurrentResultIndex] = useState(0);
  const [batchMode, setBatchMode] = useState(true);
  const [selectedQueueIndex, setSelectedQueueIndex] = useState(0);
  const [metadataCollapsed, setMetadataCollapsed] = useState(true);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // App initialization state (loading screen)
  const [isInitialized, setIsInitialized] = useState(false);

  // Settings - Load from localStorage on init (MUST be before useLivePreview)
  const [settings, setSettings] = useState<ProcessorSettings>(loadSettings);

  // Progress tracking
  const [processingStep, setProcessingStep] = useState<string>('');
  const [processingProgress, setProcessingProgress] = useState<number>(0);
  const [currentRequestId, setCurrentRequestId] = useState<string | null>(null);

  // File input ref for keyboard shortcut
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Image History Hook for pipeline processing
  const imageHistory = useImageHistory();

  // Show original vs enhanced toggle
  const [showOriginal, setShowOriginal] = useState(false);

  // Queue view zoom
  const [queueZoom, setQueueZoom] = useState(100);

  // Live Preview Hook
  const { previewImage, previewStep, reset: resetPreview } = useLivePreview(
    settings.backendUrl,
    currentRequestId,
    state === AppState.PROCESSING
  );

  // Progress State
  const [progress, setProgress] = useState({ current: 0, total: 0 });

  // Progress ETA Hook
  const { formatted: etaFormatted } = useProgressETA(
    processingProgress,
    state === AppState.PROCESSING,
    progress.current,
    progress.total
  );

  // System Stats
  const [systemStats, setSystemStats] = useState<any>(null);

  // Save settings whenever they change
  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  // Poll Stats - only when app is initialized
  React.useEffect(() => {
    if (!isInitialized) return; // Don't poll during loading

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${settings.backendUrl}/system/stats`);
        if (res.ok) setSystemStats(await res.json());
      } catch (e) { }
    }, 2000);
    return () => clearInterval(interval);
  }, [settings.backendUrl, isInitialized]);

  // File dialog helper
  const openFileDialog = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleUpload = (files: File[]) => {
    setQueue(files);

    // Create queue images with previews
    const newQueueImages: QueueImage[] = files.map((file, index) => ({
      id: `img-${Date.now()}-${index}`,
      file,
      preview: URL.createObjectURL(file),
      selected: true, // Select all by default
      processed: false,
      processing: false
    }));

    setQueueImages(newQueueImages);
    setResults([]);
    setCurrentResultIndex(0);
    setState(AppState.IDLE);
  };

  const processBatch = async () => {
    // Determine operation name for history
    const getOperationName = () => {
      if (settings.enableRealism) return 'Make It Real';
      if (settings.enableSDXLUpscale) return 'SDXL Realistic Upscale';
      if (settings.enableSkin) return 'Skin Texture';
      if (settings.enableHiresFix) return 'HiresFix';
      if (settings.enableFaceEnhance) return 'Face Enhance';
      if (settings.enableUpscale) return `Upscale ${settings.upscaleFactor}x`;
      return 'Process';
    };

    // DEBUG: Log state to diagnose pipeline issues
    console.log('[Pipeline] processBatch called:', {
      historyLength: imageHistory.historyLength,
      hasCurrentImage: !!imageHistory.currentImage,
      queueLength: queue.length,
      state: state
    });

    // PIPELINE MODE: If we have history, process from current image in history
    if (imageHistory.currentImage && imageHistory.historyLength > 0) {
      console.log('[Pipeline] Using PIPELINE MODE - processing from history');
      setState(AppState.PROCESSING);
      setProgress({ current: 1, total: 1 });

      const controller = new AbortController();
      setAbortController(controller);

      try {
        setProcessingStep('');
        setProcessingProgress(0);
        setCurrentRequestId(null);
        resetPreview();

        const data = await processImageFromBase64(
          imageHistory.currentImage,
          imageHistory.history[0]?.operation.replace('Original: ', '') || 'image.png',
          settings,
          (update) => {
            setProcessingStep(update.step);
            setProcessingProgress(update.progress);
          },
          (requestId) => {
            setCurrentRequestId(requestId);
          }
        );

        // Add result to history
        imageHistory.pushImage(data.upscaledUrl, getOperationName(), settings);

        // Update results for display
        setResults([data]);
        setState(AppState.RESULTS);
        setCurrentResultIndex(0);

      } catch (error: any) {
        console.error('Pipeline processing failed:', error);
        alert(`Processing failed: ${error.message}`);
        setState(AppState.IDLE);
      } finally {
        setAbortController(null);
        setCurrentRequestId(null);
        resetPreview();
      }
      return;
    }

    // NORMAL MODE: Process from queue files
    if (queue.length === 0) return;

    setState(AppState.PROCESSING);
    setProgress({ current: 0, total: queue.length });

    const controller = new AbortController();
    setAbortController(controller);

    const newResults: UpscaleResult[] = [];

    try {
      for (let i = 0; i < queue.length; i++) {
        if (controller.signal.aborted) {
          console.log('Processing cancelled by user');
          break;
        }

        setProgress({ current: i + 1, total: queue.length });

        try {
          setProcessingStep('');
          setProcessingProgress(0);
          setCurrentRequestId(null);
          resetPreview();

          const data = await processImageLocally(
            queue[i],
            settings,
            (update) => {
              setProcessingStep(update.step);
              setProcessingProgress(update.progress);
            },
            (requestId) => {
              setCurrentRequestId(requestId);
            }
          );

          newResults.push(data);

          // For single image, initialize history with original and add result
          if (queue.length === 1) {
            // Create data URL from original file for history
            const originalDataUrl = await new Promise<string>((resolve) => {
              const reader = new FileReader();
              reader.onload = () => resolve(reader.result as string);
              reader.readAsDataURL(queue[i]);
            });

            imageHistory.setOriginal(originalDataUrl, queue[i].name);
            imageHistory.pushImage(data.upscaledUrl, getOperationName(), settings);
          }

        } catch (error: any) {
          console.error(`Processing failed for ${queue[i].name}`, error);
        }
      }
    } finally {
      setAbortController(null);
      setCurrentRequestId(null);
      resetPreview();
    }

    if (newResults.length > 0) {
      setResults(newResults);
      setState(AppState.RESULTS);
      setCurrentResultIndex(0);
    } else {
      setState(AppState.IDLE);
      if (!controller.signal.aborted) {
        alert("Processing failed. Please check your local server console.");
      }
    }
  };


  const cancelProcessing = async () => {
    // Cancel backend (ComfyUI interrupt)
    await cancelBackend(settings.backendUrl);

    // Cancel frontend batch loop
    if (abortController) {
      abortController.abort();
    }

    // Reset state
    setState(AppState.IDLE);
    setProcessingProgress(0);
    setProcessingStep('');
    resetPreview();
  };

  const handleClose = () => {
    setResults([]);
    setQueue([]);
    setState(AppState.IDLE);
    setProgress({ current: 0, total: 0 });
  };

  const handleNext = () => {
    if (currentResultIndex < results.length - 1) {
      setCurrentResultIndex(prev => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentResultIndex > 0) {
      setCurrentResultIndex(prev => prev - 1);
    }
  };

  // Batch Queue Control Functions
  const handleSelectToggle = (id: string) => {
    setQueueImages(prev => prev.map(img =>
      img.id === id ? { ...img, selected: !img.selected } : img
    ));
  };

  const handleSelectAll = () => {
    setQueueImages(prev => prev.map(img => ({ ...img, selected: true })));
  };

  const handleSelectNone = () => {
    setQueueImages(prev => prev.map(img => ({ ...img, selected: false })));
  };

  const handleDelete = (ids: string[]) => {
    // Remove from queue images
    const remainingImages = queueImages.filter(img => !ids.includes(img.id));
    setQueueImages(remainingImages);

    // Update main queue
    const keepFiles = remainingImages.map(img => img.file);
    setQueue(keepFiles);

    // Cleanup preview URLs
    queueImages
      .filter(img => ids.includes(img.id))
      .forEach(img => URL.revokeObjectURL(img.preview));
  };

  const handleBatchModeToggle = () => {
    setBatchMode(!batchMode);
  };

  const handleAddMore = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      handleUpload(files);
    }
  };

  // Keyboard Shortcuts (after all handlers are defined)
  useKeyboardShortcuts({
    onProcess: () => {
      // Process from history or queue
      if ((imageHistory.historyLength > 0 || queueImages.filter(q => q.selected).length > 0) && state !== AppState.PROCESSING) {
        processBatch();
      }
    },
    onCancel: cancelProcessing,
    onOpenFiles: openFileDialog,
    onNextResult: handleNext,
    onPrevResult: handlePrev,
    onClose: handleClose,
    onSelectAll: handleSelectAll,
    onDeselectAll: handleSelectNone,
    onUndo: imageHistory.undo,
    onRedo: imageHistory.redo,
    onToggleOriginal: () => setShowOriginal(!showOriginal),
    isProcessing: state === AppState.PROCESSING,
    hasQueue: queueImages.length > 0,
    hasResults: results.length > 0,
    hasHistory: imageHistory.historyLength > 0
  });


  return (
    <div className="h-screen w-screen flex flex-col bg-app-bg text-app-text overflow-hidden">
      {/* Loading Screen - shown during initialization */}
      {!isInitialized && (
        <LoadingScreen
          onReady={() => setIsInitialized(true)}
          backendUrl={settings.backendUrl}
        />
      )}

      <TitleBar />

      {/* Hidden file input for adding more images */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="image/*"
        onChange={handleFileInputChange}
        style={{ display: 'none' }}
      />

      <div className="flex-1 flex overflow-hidden" style={{ paddingBottom: queueImages.length >= 2 ? '200px' : '0' }}>
        {/* Left Sidebar */}
        <Sidebar
          settings={settings}
          setSettings={setSettings}
          disabled={state === AppState.PROCESSING}
          onProcess={processBatch}
          queueCount={queueImages.filter(img => img.selected).length}
          // Progress Props
          progress={processingProgress}
          step={processingStep}
          eta={etaFormatted}
          // History Props
          canUndo={imageHistory.canUndo}
          canRedo={imageHistory.canRedo}
          onUndo={imageHistory.undo}
          onRedo={imageHistory.redo}
          historyStepInfo={imageHistory.stepInfo}
          showOriginal={showOriginal}
          onToggleOriginal={() => setShowOriginal(!showOriginal)}
          hasHistory={imageHistory.historyLength > 0}
        />



        {/* Main Content Area */}
        <div
          className="flex-1 relative bg-[#09090b] flex flex-col items-center justify-center overflow-hidden"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px'
          }}
        >
          {state === AppState.RESULTS && results.length > 0 ? (
            <ComparisonView
              result={results[currentResultIndex]}
              allResults={results}
              onClose={() => setState(AppState.IDLE)}
              onNext={() => setCurrentResultIndex((prev) => prev + 1)}
              onPrev={() => setCurrentResultIndex((prev) => prev - 1)}
              hasNext={currentResultIndex < results.length - 1}
              hasPrev={currentResultIndex > 0}
              currentCount={currentResultIndex + 1}
              totalCount={results.length}
              // History props
              canUndo={imageHistory.canUndo}
              canRedo={imageHistory.canRedo}
              onUndo={imageHistory.undo}
              onRedo={imageHistory.redo}
              showOriginal={showOriginal}
              onToggleOriginal={() => setShowOriginal(!showOriginal)}
              historyStepInfo={imageHistory.stepInfo}
            />
          ) : imageHistory.historyLength > 0 && imageHistory.currentImage ? (
            /* PIPELINE VIEW: Show current image from history for further editing */
            <div className="w-full h-full relative flex flex-col items-center justify-center gap-4 p-8">
              <img
                src={showOriginal ? imageHistory.originalImage! : imageHistory.currentImage}
                alt="Current"
                className="max-w-[80%] max-h-[70%] object-contain rounded shadow-2xl"
              />

              {/* History Toolbar */}
              <HistoryToolbar
                canUndo={imageHistory.canUndo}
                canRedo={imageHistory.canRedo}
                onUndo={imageHistory.undo}
                onRedo={imageHistory.redo}
                showOriginal={showOriginal}
                onToggleOriginal={() => setShowOriginal(!showOriginal)}
                historyStepInfo={imageHistory.stepInfo}
                disabled={state === AppState.PROCESSING}
              />
              <div className="flex items-center gap-4">
                <div className="px-4 py-2 bg-purple-900/20 border border-purple-500/30 rounded text-purple-400 font-mono text-sm">
                  {imageHistory.stepInfo} • {imageHistory.currentOperation}
                </div>
              </div>
            </div>
          ) : queueImages.length > 0 ? (
            /* QUEUE VIEW: Show selected image from queue with toolbar */
            <div className="w-full h-full flex flex-col">
              {/* Image area with zoom */}
              <div className="flex-1 flex items-center justify-center p-4 overflow-auto">
                <img
                  src={queueImages[selectedQueueIndex]?.preview || queueImages[0]?.preview}
                  alt="Preview"
                  className="object-contain rounded shadow-2xl transition-transform"
                  style={{
                    transform: `scale(${queueZoom / 100})`,
                    maxWidth: queueZoom > 100 ? 'none' : '100%',
                    maxHeight: queueZoom > 100 ? 'none' : '100%'
                  }}
                />
              </div>

              {/* Bottom Toolbar - Similar to ComparisonView */}
              <div className="h-14 border-t border-white/10 flex items-center justify-between px-4 bg-app-panel shrink-0">
                {/* Left: Status indicators */}
                <div className="flex items-center gap-3">
                  <div className="px-3 py-1.5 bg-emerald-900/30 border border-emerald-500/30 rounded text-emerald-400 font-mono text-sm">
                    {queueImages.length} image{queueImages.length > 1 ? 's' : ''} ready
                  </div>
                  <span className="text-white/40 text-xs truncate max-w-[200px]">
                    {queueImages[selectedQueueIndex]?.file?.name || queueImages[0]?.file?.name}
                  </span>
                </div>

                {/* Center: Zoom controls */}
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setQueueZoom(prev => Math.max(25, prev - 25))}
                    className="p-1.5 rounded border border-white/10 text-white/60 hover:text-white hover:border-white/30 transition-colors"
                  >
                    <ZoomOut size={14} />
                  </button>
                  <input
                    type="range"
                    min="25"
                    max="800"
                    step="25"
                    value={queueZoom}
                    onChange={(e) => setQueueZoom(Number(e.target.value))}
                    className="w-24 accent-emerald-500"
                  />
                  <span className="text-white/60 text-xs font-mono w-10">{queueZoom}%</span>
                  <button
                    onClick={() => setQueueZoom(prev => Math.min(800, prev + 25))}
                    className="p-1.5 rounded border border-white/10 text-white/60 hover:text-white hover:border-white/30 transition-colors"
                  >
                    <ZoomIn size={14} />
                  </button>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setQueue([])}
                    className="px-3 py-1.5 text-xs font-bold rounded border border-white/10 text-white/40 hover:text-white hover:border-white/30 transition-colors"
                  >
                    Clear All
                  </button>
                  <button
                    onClick={handleAddMore}
                    className="px-4 py-1.5 bg-white/10 hover:bg-white/20 border border-white/10 text-white text-xs font-bold rounded flex items-center gap-2 transition-colors"
                  >
                    + Add More
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <ImageUploader onUpload={handleUpload} isLoading={false} />
          )}

          {/* GLOBAL LIVE PREVIEW OVERLAY - visible during all processing modes */}
          {state === AppState.PROCESSING && previewImage && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/90 z-50 p-8">
              <img
                src={previewImage}
                alt="Live Preview"
                className="max-w-full max-h-[calc(100%-120px)] object-contain rounded shadow-2xl border-2 border-emerald-500/50"
              />
              <div className="flex items-center gap-4 mt-4 shrink-0">
                <div className="px-4 py-2 bg-emerald-900/30 border border-emerald-500/30 rounded text-emerald-400 font-mono text-sm">
                  Live Preview • Step {previewStep}
                </div>
                <div className="px-3 py-1.5 bg-black/40 rounded border border-white/10 text-white/60 text-xs">
                  {Math.round(processingProgress)}%
                </div>
                <button
                  onClick={cancelProcessing}
                  className="px-4 py-2 bg-red-600/80 hover:bg-red-500 text-white text-sm font-bold rounded border border-red-500/50 transition-colors"
                >
                  ✕ CANCEL
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Metadata Panel - Show for queue images when not in results (starts collapsed) */}
        {state !== AppState.RESULTS && queueImages.length > 0 && (
          <MetadataPanel
            imageUrl={queueImages[selectedQueueIndex]?.preview || queueImages[0]?.preview}
            filename={queueImages[selectedQueueIndex]?.file.name || queueImages[0]?.file.name}
            collapsed={metadataCollapsed}
            onToggle={() => setMetadataCollapsed(!metadataCollapsed)}
          />
        )}
      </div>

      {/* Status Bar */}
      <div className="h-6 bg-app-panel border-t border-app-border flex items-center justify-between px-4 text-[10px] text-app-muted select-none relative overflow-hidden">
        {/* Visual Progress Bar */}
        {state === AppState.PROCESSING && (
          <div
            className="absolute inset-y-0 left-0 bg-white/10 transition-all duration-300 ease-out z-0"
            style={{ width: `${(progress.current / progress.total) * 100}%` }}
          />
        )}

        <div className="flex gap-4 relative z-10">
          <span className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${state === AppState.PROCESSING ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'}`}></div>
            {state === AppState.PROCESSING ? `PROCESSING: ${progress.current} / ${progress.total}` : 'SYSTEM IDLE'}
          </span>
          <span className="uppercase">BACKEND: {settings.backendUrl}</span>
          {systemStats?.vram_usage && (
            <span className="text-emerald-400 font-mono">
              VRAM: {systemStats.vram_usage.allocated_gb}GB
            </span>
          )}
        </div>
        <div className="relative z-10 flex gap-4">
          <span>Upscale Engine CC v1.0</span>
        </div>
      </div>

      {/* Batch Queue - Bottom Panel - Only show when 2+ images */}
      {queueImages.length >= 2 && (
        <BatchQueue
          images={queueImages}
          onSelectToggle={handleSelectToggle}
          onSelectAll={handleSelectAll}
          onSelectNone={handleSelectNone}
          onDelete={handleDelete}
          batchMode={batchMode}
          onBatchModeToggle={handleBatchModeToggle}
        />
      )}
    </div>
  );
};

export default App;