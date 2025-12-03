import React, { useRef, useState } from 'react';
import { Upload, FileImage, MousePointer2, Layers } from 'lucide-react';

interface ImageUploadProps {
  onUpload: (files: File[]) => void;
  isLoading: boolean;
}

const ImageUpload: React.FC<ImageUploadProps> = ({ onUpload, isLoading }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  };

  const handleFiles = (fileList: FileList) => {
    if (isLoading) return;
    const files: File[] = [];
    for (let i = 0; i < fileList.length; i++) {
        const file = fileList[i];
        if (file.type.startsWith('image/')) {
            files.push(file);
        }
    }
    
    if (files.length === 0) {
      alert('No valid image files found.');
      return;
    }
    onUpload(files);
  };

  return (
    <div className="flex flex-col items-center justify-center h-full w-full">
      <div 
        className={`relative w-[400px] h-[300px] border-2 border-dashed rounded-xl flex flex-col items-center justify-center gap-4 transition-all duration-300
           ${dragActive ? 'border-white bg-white/5' : 'border-white/10 hover:border-white/20 hover:bg-white/5'}
        `}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !isLoading && fileInputRef.current?.click()}
      >
          <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-2 relative">
             <FileImage className="text-white/50" size={32} />
             <Layers className="absolute -bottom-1 -right-1 text-white/30" size={16} />
          </div>
          
          <div className="text-center">
             <h3 className="text-lg font-medium text-white">Import Images</h3>
             <p className="text-xs text-app-muted mt-2">Drag & Drop Batch or Click to Browse</p>
          </div>

          <div className="flex gap-8 mt-4 opacity-50">
             <div className="flex flex-col items-center gap-1">
                <MousePointer2 size={12} />
                <span className="text-[10px] uppercase">Drop</span>
             </div>
             <div className="flex flex-col items-center gap-1">
                <Upload size={12} />
                <span className="text-[10px] uppercase">Load</span>
             </div>
          </div>

          <input 
              ref={fileInputRef}
              type="file" 
              accept="image/*" 
              className="hidden" 
              multiple
              onChange={handleChange}
          />
      </div>
    </div>
  );
};

export default ImageUpload;