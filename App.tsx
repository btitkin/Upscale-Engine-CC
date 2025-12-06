import React, { useState, useEffect, useRef, useCallback } from 'react';
import TitleBar from './components/TitleBar';
import Sidebar from './components/Sidebar';
import ImageUploader from './components/ImageUploader';
import ComparisonView from './components/ComparisonView';
import BatchQueue from './components/BatchQueue';
import MetadataPanel from './components/MetadataPanel';
import LoadingScreen from './components/LoadingScreen';
import { processImageLocally, pollProgress, ProgressUpdate } from './services/upscaleService';
import { loadSettings, saveSettings } from './services/settingsService';
import { AppState, UpscaleResult, ProcessorSettings } from './types';
import { Layers } from 'lucide-react';
import { useLivePreview } from './hooks/useLivePreview';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useProgressETA } from './hooks/useProgressETA';

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
  const [metadataCollapsed, setMetadataCollapsed] = useState(false);
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

  // Poll Stats
  React.useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${settings.backendUrl}/system/stats`);
        if (res.ok) setSystemStats(await res.json());
      } catch (e) { }
    }, 2000);
    return () => clearInterval(interval);
  }, [settings.backendUrl]);

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
    if (queue.length === 0) return;

    setState(AppState.PROCESSING);
    setProgress({ current: 0, total: queue.length });

    // Create abort controller
    const controller = new AbortController();
    setAbortController(controller);

    const newResults: UpscaleResult[] = [];

    try {
      // Sequential Processing
      for (let i = 0; i < queue.length; i++) {
        // Check if aborted
        if (controller.signal.aborted) {
          console.log('Processing cancelled by user');
          break;
        }

        setProgress({ current: i + 1, total: queue.length });

        try {
          // Reset progress for new image
          setProcessingStep('');
          setProcessingProgress(0);
          setCurrentRequestId(null);  // Reset requestId
          resetPreview();  // Reset preview

          // Process with progress callback and requestId callback
          const data = await processImageLocally(
            queue[i],
            settings,
            (update) => {
              setProcessingStep(update.step);
              setProcessingProgress(update.progress);
            },
            (requestId) => {
              // Set requestId for SSE preview connection
              setCurrentRequestId(requestId);
            }
          );

          newResults.push(data);
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

  const cancelProcessing = () => {
    if (abortController) {
      abortController.abort();
      setState(AppState.IDLE);
    }
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
      if (queueImages.filter(q => q.selected).length > 0 && state !== AppState.PROCESSING) {
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
    isProcessing: state === AppState.PROCESSING,
    hasQueue: queueImages.length > 0,
    hasResults: results.length > 0
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
        />

        {/* Main Content Area */}
        <div className="flex-1 relative bg-[#09090b] flex flex-col items-center justify-center overflow-hidden">
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
            />
          ) : queueImages.length > 0 ? (
            <div className="w-full h-full flex flex-col items-center justify-center gap-4 p-8">
              <img
                src={queueImages[selectedQueueIndex]?.preview || queueImages[0]?.preview}
                alt="Preview"
                className="max-w-[80%] max-h-[70%] object-contain rounded shadow-2xl"
              />
              <div className="flex items-center gap-4">
                <div className="px-4 py-2 bg-emerald-900/20 border border-emerald-500/30 rounded text-emerald-400 font-mono text-sm">
                  {queueImages.length} image{queueImages.length > 1 ? 's' : ''} ready
                </div>
                <button
                  onClick={handleAddMore}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 border border-emerald-500/50 text-white rounded flex items-center gap-2 transition-colors"
                >
                  <span className="text-xl">+</span> Add Images
                </button>
              </div>
            </div>
          ) : (
            <ImageUploader onUpload={handleUpload} isLoading={false} />
          )}
        </div>

        {/* Metadata Panel - Show for queue images when not in results */}
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