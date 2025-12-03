import React, { useState } from 'react';
import { Trash2, CheckSquare, Square } from 'lucide-react';
import './BatchQueue.css';

interface QueueImage {
    id: string;
    file: File;
    preview: string;
    selected: boolean;
    processed: boolean;
    processing: boolean;
}

interface BatchQueueProps {
    images: QueueImage[];
    onSelectToggle: (id: string) => void;
    onSelectAll: () => void;
    onSelectNone: () => void;
    onDelete: (ids: string[]) => void;
    batchMode: boolean;
    onBatchModeToggle: () => void;
}

export default function BatchQueue({
    images,
    onSelectToggle,
    onSelectAll,
    onSelectNone,
    onDelete,
    batchMode,
    onBatchModeToggle
}: BatchQueueProps) {
    const selectedCount = images.filter(img => img.selected).length;
    const selectedIds = images.filter(img => img.selected).map(img => img.id);

    return (
        <div className="batch-queue">
            {/* Header Controls */}
            <div className="queue-header">
                <div className="queue-info">
                    <span className="queue-count">{images.length} Files</span>
                    {selectedCount > 0 && (
                        <span className="selected-count">• {selectedCount} Selected</span>
                    )}
                </div>

                <div className="queue-controls">
                    {/* Batch/Single Toggle */}
                    <button
                        className={`mode-toggle ${batchMode ? 'batch' : 'single'}`}
                        onClick={onBatchModeToggle}
                        title={batchMode ? 'Batch Mode' : 'Single Mode'}
                    >
                        {batchMode ? 'Batch' : 'Single'}
                    </button>

                    {/* Select All/None */}
                    <button
                        className="control-btn"
                        onClick={selectedCount === images.length ? onSelectNone : onSelectAll}
                        disabled={images.length === 0}
                        title={selectedCount === images.length ? 'Unselect All' : 'Select All'}
                    >
                        {selectedCount === images.length ? <Square size={18} /> : <CheckSquare size={18} />}
                        {selectedCount === images.length ? 'None' : 'All'}
                    </button>

                    {/* Delete Selected */}
                    <button
                        className="control-btn delete"
                        onClick={() => onDelete(selectedIds)}
                        disabled={selectedCount === 0}
                        title="Delete Selected"
                    >
                        <Trash2 size={18} />
                        Delete ({selectedCount})
                    </button>
                </div>
            </div>

            {/* Image Thumbnails */}
            <div className="queue-thumbnails">
                {images.length === 0 ? (
                    <div className="empty-queue">
                        <p>No images in queue</p>
                        <span>Drop images or click to upload</span>
                    </div>
                ) : (
                    images.map(image => (
                        <div
                            key={image.id}
                            className={`thumbnail-item ${image.selected ? 'selected' : ''} ${image.processing ? 'processing' : ''
                                } ${image.processed ? 'processed' : ''}`}
                            onClick={() => onSelectToggle(image.id)}
                        >
                            {/* Checkbox */}
                            <div className="thumbnail-checkbox">
                                {image.selected ? <CheckSquare size={16} /> : <Square size={16} />}
                            </div>

                            {/* Image Preview */}
                            <img src={image.preview} alt={image.file.name} className="thumbnail-img" />

                            {/* Status Badge */}
                            {image.processing && <div className="status-badge processing">Processing...</div>}
                            {image.processed && <div className="status-badge done">✓ Done</div>}

                            {/* Filename */}
                            <div className="thumbnail-name" title={image.file.name}>
                                {image.file.name}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
