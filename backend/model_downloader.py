"""
LumaScale Model Downloader
Auto-downloads required AI models with progress tracking and resume capability
"""

import os
import json
import requests
from pathlib import Path
from typing import Dict, Callable, Optional


class ModelDownloader:
    def __init__(self, models_dir: str = None):
        # Always use project root models/ directory
        if models_dir is None:
            # Get project root (backend's parent directory)
            backend_dir = Path(__file__).parent
            project_root = backend_dir.parent
            models_dir = project_root / "models"
        else:
            models_dir = Path(models_dir)
        
        self.models_dir = models_dir
        self.models_dir.mkdir(exist_ok=True)
        self.manifest_path = self.models_dir / "model-manifest.json"
        self.manifest = self._load_manifest()
    
    def _load_manifest(self) -> Dict:
        """Load model manifest defining what to download"""
        default_manifest = {
            "upscale": {
                "name": "RealESRGAN x4plus",
                "filename": "RealESRGAN_x4plus.pth",
                "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
                "size": 67040989,
                "type": "esrgan"
            },
            "sdxl": {
                "name": "Juggernaut XL 9.0",
                "filename": "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
                "url": "https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
                "size": 7110000000,
                "type": "sdxl"
            },
            "qwen": {
                "name": "Qwen Image Edit 2509",
                "filename": "Qwen-Image-Edit-2509-Q4_K_M.gguf",
                "url": "https://huggingface.co/QuantStack/Qwen-Image-Edit-2509-GGUF/resolve/main/Qwen-Image-Edit-2509-Q4_K_M.gguf",
                "size": 13100000000,
                "type": "gguf"
            }
        }
        
        # Write manifest if it doesn't exist
        if not self.manifest_path.exists():
            with open(self.manifest_path, 'w') as f:
                json.dump(default_manifest, f, indent=2)
        
        with open(self.manifest_path, 'r') as f:
            return json.load(f)
    
    def check_model_exists(self, model_key: str) -> bool:
        """Check if model is already downloaded and valid"""
        if model_key not in self.manifest:
            return False
        
        model_info = self.manifest[model_key]
        model_path = self.models_dir / model_info["filename"]
        
        if not model_path.exists():
            return False
        
        # Verify file size matches expected
        actual_size = model_path.stat().st_size
        expected_size = model_info["size"]
        
        # Allow 1% variance for size check
        size_diff = abs(actual_size - expected_size) / expected_size
        return size_diff < 0.01
    
    def get_missing_models(self) -> list:
        """Returns list of model keys that need to be downloaded"""
        missing = []
        for model_key in self.manifest.keys():
            if not self.check_model_exists(model_key):
                missing.append(model_key)
        return missing
    
    def download_model(
        self, 
        model_key: str, 
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """
        Download a specific model with progress tracking
        
        Args:
            model_key: Key from manifest (e.g., 'upscale', 'sdxl', 'qwen')
            progress_callback: Function(downloaded_bytes, total_bytes, model_name) called during download
        
        Returns:
            True if download successful, False otherwise
        """
        if model_key not in self.manifest:
            print(f"Error: Model '{model_key}' not found in manifest")
            return False
        
        model_info = self.manifest[model_key]
        model_path = self.models_dir / model_info["filename"]
        url = model_info["url"]
        model_name = model_info["name"]
        
        print(f"Downloading {model_name}...")
        print(f"URL: {url}")
        print(f"Destination: {model_path}")
        
        # Check if partially downloaded file exists
        temp_path = model_path.with_suffix(model_path.suffix + ".temp")
        resume_byte_pos = 0
        
        if temp_path.exists():
            resume_byte_pos = temp_path.stat().st_size
            print(f"Resuming download from {resume_byte_pos:,} bytes")
        
        # Setup headers for resume
        headers = {}
        if resume_byte_pos > 0:
            headers['Range'] = f'bytes={resume_byte_pos}-'
        
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get total size
            total_size = int(response.headers.get('content-length', 0))
            if 'content-range' in response.headers:
                # If resuming, content-length is remaining bytes
                total_size = int(response.headers['content-range'].split('/')[-1])
            
            downloaded = resume_byte_pos
            chunk_size = 8192  # 8KB chunks
            
            mode = 'ab' if resume_byte_pos > 0 else 'wb'
            
            with open(temp_path, mode) as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Call progress callback
                        if progress_callback:
                            progress_callback(downloaded, total_size, model_name)
                        
                        # Print progress
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\rProgress: {percent:.1f}% ({downloaded:,}/{total_size:,} bytes)", end='')
            
            print()  # New line after progress
            
            # Verify download completed
            if total_size > 0 and downloaded < total_size:
                print(f"Warning: Download incomplete ({downloaded}/{total_size} bytes)")
                return False
            
            # Move temp file to final location
            temp_path.rename(model_path)
            print(f"✓ {model_name} downloaded successfully!")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Download error: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
    
    def download_all_missing(
        self, 
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None
    ) -> bool:
        """
        Download all missing models
        
        Args:
            progress_callback: Function(model_key, downloaded, total, model_name)
        
        Returns:
            True if all downloads successful
        """
        missing = self.get_missing_models()
        
        if not missing:
            print("All models already downloaded!")
            return True
        
        print(f"Need to download {len(missing)} models: {missing}")
        
        success = True
        for model_key in missing:
            # Wrapper to add model_key to callback
            def wrapped_callback(downloaded, total, name):
                if progress_callback:
                    progress_callback(model_key, downloaded, total, name)
            
            if not self.download_model(model_key, wrapped_callback):
                success = False
                print(f"Failed to download {model_key}")
        
        return success
    
    def get_model_path(self, model_key: str) -> Optional[Path]:
        """Get the full path to a downloaded model"""
        if not self.check_model_exists(model_key):
            return None
        
        model_info = self.manifest[model_key]
        return self.models_dir / model_info["filename"]


# CLI usage
if __name__ == "__main__":
    print("LumaScale Model Downloader")
    print("=" * 50)
    
    downloader = ModelDownloader()
    
    # Check status
    missing = downloader.get_missing_models()
    if missing:
        print(f"\nMissing models: {missing}")
        
        # Ask user to proceed
        response = input("\nDownload missing models? (y/n): ")
        if response.lower() == 'y':
            downloader.download_all_missing()
    else:
        print("\n✓ All models present!")
        
        # Show paths
        for key in downloader.manifest.keys():
            path = downloader.get_model_path(key)
            print(f"  {key}: {path}")
