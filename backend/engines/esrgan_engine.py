"""
ESRGAN Inference Engine
Handles upscaling with GPU/CPU auto-detection and progress tracking
"""

import os
import io
import base64
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, Tuple, Callable
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer


class ESRGANEngine:
    def __init__(self, model_path: str, device: Optional[str] = None):
        """
        Initialize ESRGAN upscaler
        
        Args:
            model_path: Path to .pth model file
            device: 'cuda' or 'cpu', auto-detects if None
        """
        self.model_path = Path(model_path)
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        # AGGRESSIVE GPU FORCING
        if device is None:
            if torch.cuda.is_available():
                self.device = 'cuda'
                print(f"[GPU] CUDA detected: {torch.cuda.get_device_name(0)}")
            else:
                self.device = 'cpu'
                print("[WARNING] CUDA not available, using CPU (will be slow!)")
        else:
            self.device = device
        
        # FORCE torch to use CUDA
        if self.device == 'cuda':
            torch.cuda.set_device(0)
            print(f"[GPU] Set default CUDA device to: {torch.cuda.current_device()}")
        
        print(f"ESRGAN Engine initializing on {self.device.upper()}...")
        
        # Define model architecture (RealESRGAN x4plus uses standard RRDB)
        self.model = RRDBNet(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_block=23,
            num_grow_ch=32,
            scale=4
        )
        
        # FORCE model to GPU BEFORE RealESRGANer
        if self.device == 'cuda':
            self.model = self.model.to('cuda')
            print(f"[GPU] Model moved to CUDA")
        
        # Initialize upscaler with PERFORMANCE OPTIMIZATIONS
        tile_size = 512 if self.device == 'cuda' else 256
        
        self.upsampler = RealESRGANer(
            scale=4,
            model_path=str(self.model_path),
            model=self.model,
            tile=tile_size,
            tile_pad=10,
            pre_pad=0,
            half=True if self.device == 'cuda' else False,
            device=self.device,
            gpu_id=0 if self.device == 'cuda' else None
        )
        
        # VERIFY device after init
        if hasattr(self.upsampler, 'device'):
            actual_device = str(self.upsampler.device)
            print(f"[DEBUG] RealESRGANer device: {actual_device}")
            if self.device == 'cuda' and 'cpu' in actual_device.lower():
                print("[ERROR] RealESRGANer reverted to CPU! Forcing again...")
                # Force upsampler model to GPU
                if hasattr(self.upsampler, 'model'):
                    self.upsampler.model = self.upsampler.model.to('cuda')
                    self.upsampler.device = torch.device('cuda')
        
        print(f"[OK] ESRGAN Engine ready!")
        print(f"[Info] Using tile size: {tile_size}x{tile_size}")
        if self.device == 'cuda':
            print(f"[Info] GPU acceleration enabled (FP16)")
    
    def upscale_image(
        self, 
        input_image: Image.Image, 
        scale_factor: int = 4,
        outscale: Optional[float] = None,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Image.Image:
        """
        Upscale a PIL Image with optional progress tracking
        
        Args:
            input_image: PIL Image object
            scale_factor: Target scale (2 or 4, model supports 4x natively)
            outscale: Final output scale (e.g., 2.0 for 2x despite 4x model)
            progress_callback: Optional function(progress_percent) for real-time updates
        
        Returns:
            Upscaled PIL Image
        """
        # Convert PIL to numpy array
        img_array = np.array(input_image)
        
        # Handle grayscale
        if len(img_array.shape) == 2:
            img_array = np.stack([img_array] * 3, axis=-1)
        
        # Handle RGBA (remove alpha)
        if img_array.shape[-1] == 4:
            img_array = img_array[:, :, :3]
        
        # Report start
        if progress_callback:
            progress_callback(10)  # Starting
        
        # Perform upscaling
        try:
            # If scale_factor is 2, we'll use outscale=2 to downsample 4x result
            if scale_factor == 2:
                output, _ = self.upsampler.enhance(img_array, outscale=2.0)
            else:
                output, _ = self.upsampler.enhance(img_array, outscale=outscale)
            
            if progress_callback:
                progress_callback(90)  # Processing complete
            
            # Convert back to PIL
            result = Image.fromarray(output)
            
            if progress_callback:
                progress_callback(100)  # Finished
            
            return result
            
        except Exception as e:
            print(f"Upscale error: {e}")
            raise
    
    def upscale_from_base64(
        self, 
        base64_image: str, 
        scale_factor: int = 4,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> str:
        """
        Upscale from base64 string, return base64 string
        
        Args:
            base64_image: Base64 encoded image
            scale_factor: 2 or 4
            progress_callback: Optional progress callback
        
        Returns:
            Base64 encoded upscaled image
        """
        # Decode base64 to PIL Image
        if progress_callback:
            progress_callback(5)  # Decoding
        
        image_data = base64.b64decode(base64_image)
        input_image = Image.open(io.BytesIO(image_data))
        
        # Upscale
        output_image = self.upscale_image(input_image, scale_factor, progress_callback=progress_callback)
        
        # Encode back to base64
        if progress_callback:
            progress_callback(95)  # Encoding
        
        buffer = io.BytesIO()
        output_image.save(buffer, format='PNG')
        buffer.seek(0)
        result_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        if progress_callback:
            progress_callback(100)  # Complete
        
        return result_base64
    
    def get_output_dimensions(self, width: int, height: int, scale: int) -> Tuple[int, int]:
        """Calculate output dimensions"""
        return (width * scale, height * scale)
