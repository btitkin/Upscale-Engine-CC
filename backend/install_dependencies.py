"""
Upscale Engine CC - Complete First-Run Installation Script
============================================================
This script checks and installs all required dependencies:
- Python packages
- PyTorch with CUDA
- ComfyUI and custom nodes
- Required models (CLIP, LoRA, VAE, UNET)
"""

import os
import sys
import subprocess
import urllib.request
import shutil
from pathlib import Path
from typing import Optional, Callable
import hashlib

# =============================================================================
# CONFIGURATION
# =============================================================================

# Paths
BACKEND_DIR = Path(__file__).parent
PROJECT_DIR = BACKEND_DIR.parent
COMFYUI_DIR = PROJECT_DIR / "comfyui"
CUSTOM_NODES_DIR = COMFYUI_DIR / "custom_nodes"
MODELS_DIR = PROJECT_DIR / "models"

# ComfyUI Version
COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
COMFYUI_VERSION = "v0.3.73"

# Required Custom Nodes
REQUIRED_NODES = {
    "ComfyUI-Custom-Scripts": "https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git",
    "rgthree-comfy": "https://github.com/rgthree/rgthree-comfy.git",
    "ComfyUI-GGUF": "https://github.com/City96/ComfyUI-GGUF.git",
    "ComfyUI-KJNodes": "https://github.com/kijai/ComfyUI-KJNodes.git",
    "ComfyUI-Easy-Use": "https://github.com/yolain/ComfyUI-Easy-Use.git",
}

# Required Models for Make It Real
REQUIRED_MODELS = {
    # CLIP Text Encoder
    "clip/qwen_2.5_vl_7b_fp8_scaled.safetensors": {
        "url": "https://huggingface.co/Comfy-Org/Qwen2.5-VL-7B-Instruct_fp8_e4m3fn_scaled/resolve/main/qwen2.5_vl_7b_fp8_scaled.safetensors",
        "size_mb": 8948,
        "description": "Qwen 2.5 VL CLIP encoder (FP8)"
    },
    # VAE
    "vae/qwen_image_vae.safetensors": {
        "url": "https://huggingface.co/Comfy-Org/Qwen2.5-VL-7B-Instruct_fp8_e4m3fn_scaled/resolve/main/qwen_image_vae.safetensors",
        "size_mb": 242,
        "description": "Qwen Image VAE"
    },
    # UNET GGUF
    "Qwen_Image_Edit-Q4_K_S.gguf": {
        "url": "https://huggingface.co/City96/Qwen2-VL-Image-Editing-gguf/resolve/main/Qwen_Image_Edit-Q4_K_S.gguf",
        "size_mb": 4400,
        "description": "Qwen Image Edit GGUF (Q4_K_S quantized)"
    },
    # LoRA - Lightning 4 steps
    "loras/Qwen-Image-Lightning-4steps-V1.0.safetensors": {
        "url": "https://huggingface.co/Kijai/Qwen2-VL-Image-Editing-loras/resolve/main/Qwen-Image-Lightning-4steps-V1.0.safetensors",
        "size_mb": 1620,
        "description": "Lightning LoRA for 4-step generation"
    },
    # LoRA - Anime to Realism
    "loras/qwen anime into realism_base.safetensors": {
        "url": "https://huggingface.co/Kijai/Qwen2-VL-Image-Editing-loras/resolve/main/qwen%20anime%20into%20realism_base.safetensors",
        "size_mb": 563,
        "description": "Anime to Realism LoRA"
    },
}

# PyTorch CUDA version
PYTORCH_CUDA_VERSION = "cu124"  # CUDA 12.4

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def print_step(text: str):
    """Print a step message"""
    print(f"\n[*] {text}")

def print_success(text: str):
    """Print success message"""
    print(f"    [OK] {text}")

def print_error(text: str):
    """Print error message"""
    print(f"    [ERROR] {text}")

def print_info(text: str):
    """Print info message"""
    print(f"    -> {text}")


def run_command(args: list, cwd: Optional[str] = None, check: bool = True) -> bool:
    """Run a shell command"""
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {' '.join(args)}")
        if e.stderr:
            print_error(e.stderr[:500])
        return False

def run_pip(args: list) -> bool:
    """Run pip command"""
    return run_command([sys.executable, "-m", "pip"] + args)

def download_file(url: str, dest: Path, progress_callback: Optional[Callable] = None) -> bool:
    """Download a file with progress"""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        # Create request with user agent
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(request) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            block_size = 8192 * 16  # 128KB blocks
            
            with open(dest, 'wb') as f:
                while True:
                    block = response.read(block_size)
                    if not block:
                        break
                    f.write(block)
                    downloaded += len(block)
                    if progress_callback and total_size:
                        progress_callback(downloaded / total_size * 100)
        
        return True
    except Exception as e:
        print_error(f"Download failed: {e}")
        if dest.exists():
            dest.unlink()
        return False

# =============================================================================
# INSTALLATION FUNCTIONS
# =============================================================================

def check_python_version() -> bool:
    """Check if Python version is compatible"""
    print_step("Checking Python version...")
    
    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 10:
        print_success(f"Python {major}.{minor} detected")
        return True
    else:
        print_error(f"Python 3.10+ required, found {major}.{minor}")
        return False

def install_pytorch_cuda() -> bool:
    """Install PyTorch with CUDA support"""
    print_step("Checking PyTorch with CUDA...")
    
    try:
        import torch
        if torch.cuda.is_available():
            print_success(f"PyTorch {torch.__version__} with CUDA already installed")
            print_info(f"GPU: {torch.cuda.get_device_name(0)}")
            return True
        else:
            print_info("PyTorch CPU-only detected, upgrading to CUDA...")
    except ImportError:
        print_info("PyTorch not found, installing with CUDA...")
    
    # Uninstall CPU version
    run_pip(["uninstall", "-y", "torch", "torchvision", "torchaudio"])
    
    # Install CUDA version
    print_info(f"Installing PyTorch with CUDA {PYTORCH_CUDA_VERSION}...")
    success = run_pip([
        "install", "torch", "torchvision", "torchaudio",
        "--index-url", f"https://download.pytorch.org/whl/{PYTORCH_CUDA_VERSION}"
    ])
    
    if success:
        print_success("PyTorch with CUDA installed successfully")
    return success

def install_backend_requirements() -> bool:
    """Install backend Python requirements"""
    print_step("Installing backend requirements...")
    
    req_file = BACKEND_DIR / "requirements.txt"
    if req_file.exists():
        success = run_pip(["install", "-r", str(req_file)])
        if success:
            print_success("Backend requirements installed")
        return success
    else:
        print_error("requirements.txt not found")
        return False

def install_comfyui() -> bool:
    """Install or update ComfyUI"""
    print_step("Checking ComfyUI...")
    
    if not COMFYUI_DIR.exists():
        print_info(f"Cloning ComfyUI {COMFYUI_VERSION}...")
        if not run_command(["git", "clone", COMFYUI_REPO, str(COMFYUI_DIR)]):
            return False
        if not run_command(["git", "checkout", COMFYUI_VERSION], cwd=str(COMFYUI_DIR)):
            return False
        print_success("ComfyUI cloned successfully")
    else:
        print_success("ComfyUI already exists")
        # Fetch and checkout specific version
        run_command(["git", "fetch", "--tags"], cwd=str(COMFYUI_DIR), check=False)
        run_command(["git", "checkout", COMFYUI_VERSION], cwd=str(COMFYUI_DIR), check=False)
    
    # Install ComfyUI requirements
    print_info("Installing ComfyUI requirements...")
    req_file = COMFYUI_DIR / "requirements.txt"
    if req_file.exists():
        run_pip(["install", "-r", str(req_file)])
    
    # Install additional modules needed by custom nodes
    print_info("Installing additional modules...")
    run_pip(["install", "gguf", "einops", "torchsde", "kornia", "av", "aiohttp"])
    
    return True

def install_custom_nodes() -> bool:
    """Install required custom nodes"""
    print_step("Installing custom nodes...")
    
    CUSTOM_NODES_DIR.mkdir(parents=True, exist_ok=True)
    
    for name, url in REQUIRED_NODES.items():
        node_path = CUSTOM_NODES_DIR / name
        if not node_path.exists():
            print_info(f"Cloning {name}...")
            if run_command(["git", "clone", url, str(node_path)]):
                print_success(f"{name} installed")
                
                # Install node requirements
                req_file = node_path / "requirements.txt"
                if req_file.exists():
                    run_pip(["install", "-r", str(req_file)])
            else:
                print_error(f"Failed to install {name}")
        else:
            print_success(f"{name} already exists")
    
    return True

def load_models_from_file() -> dict:
    """Load model definitions from required_models.txt"""
    models_file = MODELS_DIR / "required_models.txt"
    models = {}
    
    if not models_file.exists():
        return models
    
    try:
        with open(models_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split('|')
                if len(parts) >= 4:
                    path, url, size_mb, description = parts[:4]
                    models[path] = {
                        'url': url,
                        'size_mb': int(size_mb),
                        'description': description
                    }
    except Exception as e:
        print_error(f"Error reading models file: {e}")
    
    return models

def download_models() -> bool:
    """Download required models"""
    print_step("Checking required models...")
    
    all_success = True
    
    # Combine hardcoded models with file-based models
    models_to_download = dict(REQUIRED_MODELS)
    file_models = load_models_from_file()
    models_to_download.update(file_models)
    
    total_size = sum(info['size_mb'] for path, info in models_to_download.items() 
                     if not (MODELS_DIR / path).exists())
    
    if total_size > 0:
        print_info(f"Total download size: ~{total_size / 1024:.1f} GB")
    
    for model_path, info in models_to_download.items():
        full_path = MODELS_DIR / model_path
        
        if full_path.exists():
            print_success(f"{model_path} already exists")
            continue
        
        print_info(f"Downloading {info['description']} ({info['size_mb']} MB)...")
        
        def progress(pct):
            print(f"\r    → Progress: {pct:.1f}%", end="", flush=True)
        
        if download_file(info['url'], full_path, progress):
            print()  # New line after progress
            print_success(f"Downloaded {model_path}")
        else:

            print()
            print_error(f"Failed to download {model_path}")
            all_success = False
    
    return all_success

def create_model_config() -> bool:
    """Create ComfyUI extra_model_paths.yaml"""
    print_step("Creating model paths configuration...")
    
    config_path = COMFYUI_DIR / "extra_model_paths.yaml"
    models_path = str(MODELS_DIR).replace("\\", "/")
    
    config_content = f"""# ComfyUI extra model paths for Upscale Engine
# Auto-generated by install_dependencies.py

upscale_engine:
    base_path: {models_path}/
    is_default: true
    checkpoints: checkpoints/
    text_encoders: |
        text_encoders/
        clip/
    clip_vision: clip_vision/
    configs: configs/
    controlnet: controlnet/
    diffusion_models: |
        diffusion_models/
        unet/
        ./
    embeddings: embeddings/
    loras: loras/
    upscale_models: upscale_models/
    vae: vae/
    unet: |
        unet/
        ./
"""
    
    try:
        with open(config_path, 'w') as f:
            f.write(config_content)
        print_success("Model paths configuration created")
        return True
    except Exception as e:
        print_error(f"Failed to create config: {e}")
        return False

def create_model_directories() -> bool:
    """Create required model directories"""
    print_step("Creating model directories...")
    
    directories = [
        "checkpoints",
        "clip",
        "clip_vision",
        "configs",
        "controlnet",
        "embeddings",
        "loras",
        "upscale_models",
        "vae",
        "workflow"
    ]
    
    for dir_name in directories:
        dir_path = MODELS_DIR / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
    
    print_success("Model directories created")
    return True

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def check_and_install_dependencies(download_models_flag: bool = True) -> bool:
    """
    Main entry point for dependency checking and installation.
    
    Args:
        download_models_flag: If True, download required models (default: True)
    
    Returns:
        bool: True if all dependencies are satisfied
    """
    print_header("Upscale Engine CC - Dependency Manager")
    
    success = True
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install PyTorch with CUDA
    if not install_pytorch_cuda():
        success = False
    
    # Install backend requirements
    if not install_backend_requirements():
        success = False
    
    # Install ComfyUI
    if not install_comfyui():
        success = False
    
    # Install custom nodes
    if not install_custom_nodes():
        success = False
    
    # Create model directories
    if not create_model_directories():
        success = False
    
    # Create model configuration
    if not create_model_config():
        success = False
    
    # Download models
    if download_models_flag:
        if not download_models():
            print_info("Some models failed to download. You can run this script again.")
            success = False
    
    print_header("Installation Complete" if success else "Installation Incomplete")
    
    if success:
        print("\n✓ All dependencies installed successfully!")
        print("\nTo start the application:")
        print("  1. Run START_UPSCALE_ENGINE.bat")
        print("  2. Or: cd backend && python server.py\n")
    else:
        print("\n⚠ Some dependencies could not be installed.")
        print("Please check the errors above and try again.\n")
    
    return success

def main():
    """CLI entry point"""
    import argparse
    parser = argparse.ArgumentParser(description="Upscale Engine CC Dependency Manager")
    parser.add_argument("--skip-models", action="store_true", 
                       help="Skip model downloads")
    parser.add_argument("--models-only", action="store_true",
                       help="Only download models, skip other dependencies")
    args = parser.parse_args()
    
    if args.models_only:
        print_header("Downloading Models Only")
        create_model_directories()
        download_models()
    else:
        check_and_install_dependencies(download_models_flag=not args.skip_models)

if __name__ == "__main__":
    main()
