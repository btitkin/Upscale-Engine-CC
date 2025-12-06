/**
 * Export Service - Batch export processed images as ZIP
 */
import JSZip from 'jszip';
import { saveAs } from 'file-saver';
import { UpscaleResult } from '../types';

/**
 * Export all results as a ZIP file
 */
export async function exportAsZip(
    results: UpscaleResult[],
    options: {
        format?: 'png' | 'jpeg' | 'webp';
        quality?: number;
        includeOriginals?: boolean;
        filenamePrefix?: string;
    } = {}
): Promise<void> {
    const {
        format = 'png',
        quality = 0.95,
        includeOriginals = false,
        filenamePrefix = 'upscaled'
    } = options;

    const zip = new JSZip();
    const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');

    // Create folders
    const outputFolder = zip.folder('output');
    const originalsFolder = includeOriginals ? zip.folder('originals') : null;

    for (let i = 0; i < results.length; i++) {
        const result = results[i];
        const index = String(i + 1).padStart(3, '0');

        // Get original filename without extension
        const baseName = result.originalName
            ? result.originalName.replace(/\.[^/.]+$/, '')
            : `image_${index}`;

        // Add processed image
        if (result.processedImage) {
            const processedBlob = await base64ToBlob(
                result.processedImage,
                format,
                quality
            );
            outputFolder?.file(
                `${filenamePrefix}_${baseName}.${format}`,
                processedBlob
            );
        }

        // Add original if requested
        if (includeOriginals && originalsFolder && result.originalImage) {
            const originalBlob = await base64ToBlob(result.originalImage, 'png');
            originalsFolder.file(`original_${baseName}.png`, originalBlob);
        }
    }

    // Generate ZIP
    const zipBlob = await zip.generateAsync({
        type: 'blob',
        compression: 'DEFLATE',
        compressionOptions: { level: 6 }
    });

    // Download
    const filename = `${filenamePrefix}_${timestamp}_${results.length}images.zip`;
    saveAs(zipBlob, filename);
}

/**
 * Convert base64 image to Blob with optional format conversion
 */
async function base64ToBlob(
    base64: string,
    format: 'png' | 'jpeg' | 'webp' = 'png',
    quality: number = 0.95
): Promise<Blob> {
    // Remove data URL prefix if present
    const base64Data = base64.includes(',')
        ? base64.split(',')[1]
        : base64;

    // If format is PNG, just decode directly
    if (format === 'png') {
        const binary = atob(base64Data);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return new Blob([bytes], { type: 'image/png' });
    }

    // For JPEG/WebP, use canvas for conversion
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = img.width;
            canvas.height = img.height;

            const ctx = canvas.getContext('2d');
            if (!ctx) {
                reject(new Error('Could not get canvas context'));
                return;
            }

            ctx.drawImage(img, 0, 0);

            canvas.toBlob(
                (blob) => {
                    if (blob) {
                        resolve(blob);
                    } else {
                        reject(new Error('Failed to create blob'));
                    }
                },
                `image/${format}`,
                quality
            );
        };
        img.onerror = () => reject(new Error('Failed to load image'));
        img.src = `data:image/png;base64,${base64Data}`;
    });
}

/**
 * Export single image
 */
export function exportSingleImage(
    base64: string,
    filename: string,
    format: 'png' | 'jpeg' | 'webp' = 'png'
): void {
    const link = document.createElement('a');
    link.href = `data:image/${format};base64,${base64}`;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
