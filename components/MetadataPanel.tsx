import React, { useState, useEffect } from 'react';
import { Copy, Check, FileText, ChevronRight, ChevronLeft } from 'lucide-react';
import './MetadataPanel.css';

interface PNGMetadata {
    positivePrompt?: string;
    negativePrompt?: string;
    model?: string;
    loras?: string[];
    sampler?: string;
    steps?: number;
    cfgScale?: number;
    seed?: number;
    [key: string]: any;
}

interface MetadataPanelProps {
    imageUrl: string;
    filename: string;
    collapsed: boolean;
    onToggle: () => void;
}

export default function MetadataPanel({ imageUrl, filename, collapsed, onToggle }: MetadataPanelProps) {
    const [metadata, setMetadata] = useState<PNGMetadata | null>(null);
    const [loading, setLoading] = useState(true);
    const [copiedField, setCopiedField] = useState<string | null>(null);

    useEffect(() => {
        extractMetadata();
    }, [imageUrl]);

    const extractMetadata = async () => {
        try {
            const response = await fetch(imageUrl);
            const blob = await response.blob();
            const arrayBuffer = await blob.arrayBuffer();
            const uint8 = new Uint8Array(arrayBuffer);

            const textChunks = parsePNGTextChunks(uint8);
            const meta: PNGMetadata = {};

            if (textChunks.parameters) {
                parseParameters(textChunks.parameters, meta);
            }

            meta.positivePrompt = textChunks.prompt || textChunks.positive || meta.positivePrompt;
            meta.negativePrompt = textChunks.negative_prompt || textChunks.negative || meta.negativePrompt;
            meta.model = textChunks.model || textChunks.sd_model || meta.model;
            meta.sampler = textChunks.sampler || textChunks.sampler_name || meta.sampler;
            meta.steps = textChunks.steps ? parseInt(textChunks.steps) : meta.steps;
            meta.cfgScale = textChunks.cfg_scale ? parseFloat(textChunks.cfg_scale) : meta.cfgScale;
            meta.seed = textChunks.seed ? parseInt(textChunks.seed) : meta.seed;

            if (textChunks.loras) {
                meta.loras = parseLoras(textChunks.loras);
            }

            setMetadata(meta);
        } catch (error) {
            console.error('Metadata extraction failed:', error);
            setMetadata(null);
        } finally {
            setLoading(false);
        }
    };

    const parsePNGTextChunks = (data: Uint8Array): Record<string, string> => {
        const chunks: Record<string, string> = {};
        let i = 8;

        while (i < data.length) {
            const length = (data[i] << 24) | (data[i + 1] << 16) | (data[i + 2] << 8) | data[i + 3];
            const type = String.fromCharCode(data[i + 4], data[i + 5], data[i + 6], data[i + 7]);

            if (type === 'tEXt' || type === 'zTXt' || type === 'iTXt') {
                const chunkData = data.slice(i + 8, i + 8 + length);
                let key = '';
                let value = '';
                let nullIndex = chunkData.indexOf(0);

                if (nullIndex !== -1) {
                    key = String.fromCharCode(...chunkData.slice(0, nullIndex));
                    value = String.fromCharCode(...chunkData.slice(nullIndex + 1));
                    chunks[key] = value;
                }
            }

            i += 12 + length;
        }

        return chunks;
    };

    const parseParameters = (params: string, meta: PNGMetadata) => {
        const lines = params.split('\n');

        if (lines[0] && !lines[0].includes(':')) {
            meta.positivePrompt = lines[0];
        }

        lines.forEach(line => {
            if (line.startsWith('Negative prompt:')) {
                meta.negativePrompt = line.replace('Negative prompt:', '').trim();
            } else if (line.includes('Steps:')) {
                const match = line.match(/Steps: (\d+)/);
                if (match) meta.steps = parseInt(match[1]);
            } else if (line.includes('Sampler:')) {
                const match = line.match(/Sampler: ([^,]+)/);
                if (match) meta.sampler = match[1].trim();
            } else if (line.includes('CFG scale:')) {
                const match = line.match(/CFG scale: ([\d.]+)/);
                if (match) meta.cfgScale = parseFloat(match[1]);
            } else if (line.includes('Model:')) {
                const match = line.match(/Model: ([^,]+)/);
                if (match) meta.model = match[1].trim();
            }
        });
    };

    const parseLoras = (lorasString: string): string[] => {
        const regex = /<lora:([^:>]+):[^>]+>|lora:([^:]+):/g;
        const matches = [...lorasString.matchAll(regex)];
        return matches.map(m => m[1] || m[2]);
    };

    const handleCopy = (field: string, text: string) => {
        navigator.clipboard.writeText(text);
        setCopiedField(field);
        setTimeout(() => setCopiedField(null), 2000);
    };

    if (loading) {
        return (
            <div className="metadata-panel loading">
                <div className="spinner"></div>
                <p>Extracting metadata...</p>
            </div>
        );
    }

    const isEmpty = !metadata || Object.keys(metadata).filter(k => metadata[k]).length === 0;

    return (
        <div className={`metadata-panel ${collapsed ? 'collapsed' : ''}`}>
            <div className="panel-header">
                <div className="header-title">
                    <FileText size={16} />
                    <span>Image Metadata</span>
                </div>
                <button className="toggle-btn" onClick={onToggle} title={collapsed ? "Expand" : "Collapse"}>
                    {collapsed ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
                </button>
            </div>

            {!collapsed && (
                <div className="panel-content">
                    {isEmpty ? (
                        <div className="empty-state">
                            <FileText size={32} />
                            <p>No metadata found</p>
                            <span>This image doesn't contain generation info</span>
                        </div>
                    ) : (
                        <>
                            {metadata?.positivePrompt && (
                                <MetadataField
                                    label="Positive Prompt"
                                    value={metadata.positivePrompt}
                                    onCopy={() => handleCopy('positive', metadata.positivePrompt!)}
                                    copied={copiedField === 'positive'}
                                />
                            )}

                            {metadata?.negativePrompt && (
                                <MetadataField
                                    label="Negative Prompt"
                                    value={metadata.negativePrompt}
                                    onCopy={() => handleCopy('negative', metadata.negativePrompt!)}
                                    copied={copiedField === 'negative'}
                                />
                            )}

                            {metadata?.model && (
                                <MetadataField
                                    label="Model"
                                    value={metadata.model}
                                    onCopy={() => handleCopy('model', metadata.model!)}
                                    copied={copiedField === 'model'}
                                    compact
                                />
                            )}

                            {metadata?.loras && metadata.loras.length > 0 && (
                                <MetadataField
                                    label="LoRAs"
                                    value={metadata.loras.join(', ')}
                                    onCopy={() => handleCopy('loras', metadata.loras!.join(', '))}
                                    copied={copiedField === 'loras'}
                                    compact
                                />
                            )}

                            {(metadata?.sampler || metadata?.steps || metadata?.cfgScale || metadata?.seed) && (
                                <div className="metadata-group">
                                    <div className="group-label">Generation Settings</div>
                                    {metadata.sampler && <div className="setting-row"><span>Sampler:</span> {metadata.sampler}</div>}
                                    {metadata.steps && <div className="setting-row"><span>Steps:</span> {metadata.steps}</div>}
                                    {metadata.cfgScale && <div className="setting-row"><span>CFG Scale:</span> {metadata.cfgScale}</div>}
                                    {metadata.seed && <div className="setting-row"><span>Seed:</span> {metadata.seed}</div>}
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

interface MetadataFieldProps {
    label: string;
    value: string;
    onCopy: () => void;
    copied: boolean;
    compact?: boolean;
}

function MetadataField({ label, value, onCopy, copied, compact }: MetadataFieldProps) {
    return (
        <div className={`metadata-field ${compact ? 'compact' : ''}`}>
            <div className="field-header">
                <span className="field-label">{label}</span>
                <button className="copy-btn" onClick={onCopy} title="Copy">
                    {copied ? <Check size={14} /> : <Copy size={14} />}
                </button>
            </div>
            <div className="field-value">{value}</div>
        </div>
    );
}
