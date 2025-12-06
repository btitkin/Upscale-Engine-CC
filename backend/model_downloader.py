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
            "swinir": {
                "name": "SwinIR-L 4x",
                "filename": "RealSR_BSRGAN_SwinIR_L.pth",
                "url": "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x4_GAN.pth",
                "size": 284951549,
                "type": "swinir"
            },
            "sdxl": {
                "name": "Juggernaut XL 9.0",
                "filename": "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
                "url": "https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
                "size": 7110000000,
                "type": "sdxl"
            },
            "qwen": {
                "name": "Qwen Image Edit Q4_K_S (12GB)",
                "filename": "Qwen_Image_Edit-Q4_K_S.gguf",
                "url": "https://huggingface.co/city96/Qwen2-VL-Instruct-GGUF/resolve/main/qwen_image/Qwen_Image_Edit-Q4_K_S.gguf",
                "size": 12600000000,
                "type": "gguf",
                "subdir": ""
            },
            "qwen_vae": {
                "name": "Qwen Image VAE",
                "filename": "qwen_image_vae.safetensors",
                "url": "https://huggingface.co/city96/GGUF-Tools/resolve/main/qwen_image/qwen_image_vae.safetensors",
                "size": 254000000,
                "type": "vae",
                "subdir": "vae"
            },
            "qwen_clip": {
                "name": "Qwen 2.5 VL 7B FP8 CLIP",
                "filename": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                "url": "https://huggingface.co/city96/GGUF-Tools/resolve/main/qwen_image/qwen_2.5_vl_7b_fp8_scaled.safetensors",
                "size": 9400000000,
                "type": "clip",
                "subdir": "clip"
            },
            "qwen_lightning_lora": {
                "name": "Qwen Lightning 4-Steps LoRA",
                "filename": "Qwen-Image-Lightning-4steps-V1.0.safetensors",
                "url": "https://huggingface.co/city96/GGUF-Tools/resolve/main/qwen_image/Qwen-Image-Lightning-4steps-V1.0.safetensors",
                "size": 1700000000,
                "type": "lora",
                "subdir": "loras"
            },
            "makeitreal_lora": {
                "name": "Qwen Anime to Realism LoRA",
                "filename": "qwen anime into realism_base.safetensors",
                "url": "https://huggingface.co/caganseyrek/qwen-image-loaders/resolve/main/loras/qwen%20anime%20into%20realism_base.safetensors",
                "size": 590000000,
                "type": "lora",
                "subdir": "loras"
            },
            "supresdiffgan": {
                "name": "SupResDiffGAN 4x",
                "filename": "SupResDiffGAN-imagenet.ckpt",
                "url": "https://github.com/Dawir7/SupResDiffGAN/releases/download/v1.0/SupResDiffGAN-imagenet.ckpt",
                "size": 1014183293,
                "type": "supresdiffgan"
            },
            "gfpgan": {
                "name": "GFPGAN v1.4 (Face Enhance)",
                "filename": "GFPGANv1.4.pth",
                "url": "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth",
                "size": 348632874,
                "type": "gfpgan"
            }
        }
        
        # Write manifest if it doesn't exist
        if not self.manifest_path.exists():
            with open(self.manifest_path, 'w') as f:
                json.dump(default_manifest, f, indent=2)
        
        with open(self.manifest_path, 'r') as f:
            return json.load(f)
    
    def verify_gguf_integrity(self, file_path: Path) -> bool:
        """
        Check if GGUF file has valid header and reasonable metadata count.
        Returns True if valid, False if corrupted.
        """
        try:
            import struct
            with open(file_path, "rb") as f:
                magic = f.read(4)
                if magic != b'GGUF':
                    return False
                
                version = struct.unpack("I", f.read(4))[0]
                tensor_count = struct.unpack("Q", f.read(8))[0]
                metadata_kv_count = struct.unpack("Q", f.read(8))[0]
                
                # A valid GGUF should have more than 3 keys (usually 20+)
                # Relaxed check: Some GGUFs have very few keys.
                if metadata_kv_count < 2:
                    print(f"Warning: GGUF file {file_path.name} seems corrupted (only {metadata_kv_count} metadata keys)")
                    return False
                    
                return True
        except Exception as e:
            print(f"Error verifying GGUF integrity: {e}")
            return False

    def check_model_exists(self, model_key: str) -> bool:
        """Check if model is already downloaded and valid"""
        if model_key not in self.manifest:
            return False
        
        model_info = self.manifest[model_key]
        
        # Handle subdirectory
        subdir = model_info.get("subdir", "")
        if subdir:
            target_dir = self.models_dir / subdir
        else:
            target_dir = self.models_dir
            
        model_path = target_dir / model_info["filename"]
        
        if not model_path.exists():
            return False
        
        # Verify file size matches expected
        actual_size = model_path.stat().st_size
        expected_size = model_info["size"]
        
        # Allow 5% variance for size check (HuggingFace sizes can vary slightly)
        size_diff = abs(actual_size - expected_size) / expected_size
        if size_diff >= 0.05:
            return False
            
        # Extra check for GGUF files
        if model_info.get("type") == "gguf":
            if not self.verify_gguf_integrity(model_path):
                print(f"Detected corrupted GGUF file: {model_path.name}. Deleting...")
                try:
                    model_path.unlink() # Delete corrupted file
                except Exception as e:
                    print(f"Failed to delete corrupted file: {e}")
                return False
                
        return True
    
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
        
        # Handle subdirectory
        subdir = model_info.get("subdir", "")
        if subdir:
            target_dir = self.models_dir / subdir
            target_dir.mkdir(exist_ok=True)
        else:
            target_dir = self.models_dir
            
        model_path = target_dir / model_info["filename"]
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
            chunk_size = 1048576  # 1MB chunks for faster download
            
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
        
        # Handle subdirectory
        subdir = model_info.get("subdir", "")
        if subdir:
            target_dir = self.models_dir / subdir
        else:
            target_dir = self.models_dir
            
        return target_dir / model_info["filename"]


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
