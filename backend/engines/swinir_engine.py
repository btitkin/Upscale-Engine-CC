"""
SwinIR Upscaler Engine
Transformer-based image super-resolution for high-quality upscaling
Based on: https://github.com/JingyunLiang/SwinIR
"""

import os
import sys
import torch
import numpy as np
from PIL import Image
import io
import base64
from pathlib import Path
from typing import Optional, Callable, Tuple

# Add backend/models to path for network_swinir import
sys.path.insert(0, str(Path(__file__).parent.parent / "models"))
from network_swinir import SwinIR as net


class SwinIREngine:
    def __init__(self, model_path: str, device: Optional[str] = None):
        """
        Initialize SwinIR upscaler
        
        Args:
            model_path: Path to .pth model file
            device: 'cuda' or 'cpu', auto-detects if None
        """
        self.model_path = Path(model_path)
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        # Auto-detect device
        if device is None:
            if torch.cuda.is_available():
                self.device = 'cuda'
                print(f"[GPU] CUDA detected: {torch.cuda.get_device_name(0)}")
            else:
                self.device = 'cpu'
                print("[WARNING] CUDA not available, using CPU (will be slow!)")
        else:
            self.device = device
        
        print(f"SwinIR Engine initializing on {self.device.upper()}...")
        
        # Model parameters for Real-World SR Large 4x
        self.model_params = dict(
            upscale=4,
            in_chans=3,
            img_size=64,
            window_size=8,
            img_range=1.,
            depths=[6, 6, 6, 6, 6, 6, 6, 6, 6],
            embed_dim=240,
            num_heads=[8, 8, 8, 8, 8, 8, 8, 8, 8],
            mlp_ratio=2,
            upsampler='nearest+conv',
            resi_connection='3conv'
        )
        
        # Create model
        self.model = net(**self.model_params)
        
        # Load pretrained weights
        pretrained_model = torch.load(str(self.model_path), map_location=self.device)
        param_key_g = 'params_ema'  # Key for real-world SR models
        
        if param_key_g in pretrained_model:
            self.model.load_state_dict(pretrained_model[param_key_g], strict=True)
        elif 'params' in pretrained_model:
            self.model.load_state_dict(pretrained_model['params'], strict=True)
        else:
            self.model.load_state_dict(pretrained_model, strict=True)
        
        # Move to device and set eval mode
        self.model = self.model.to(self.device)
        self.model.eval()
        
        # Disable gradients for inference
        for param in self.model.parameters():
            param.requires_grad = False
        
        print(f"[OK] SwinIR-L Engine ready!")
        print(f"[Info] Model: Real-World SR 4x (Large)")
        print(f"[Info] Window size: 8")
        if self.device == 'cuda':
            print(f"[Info] GPU acceleration enabled")
    
    def upscale_image(
        self,
        input_image: Image.Image,
        scale_factor: int = 4,
        tile_size: int = 512,
        tile_overlap: int = 32,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Image.Image:
        """
        Upscale a PIL Image using SwinIR
        
        Args:
            input_image: PIL Image object
            scale_factor: Fixed at 4 for this model
            tile_size: Tile size for processing large images (reduce if OOM)
            tile_overlap: Overlap between tiles
            progress_callback: Optional function(progress_percent)
        
        Returns:
            Upscaled PIL Image
        """
        # Convert to RGB if needed
        if input_image.mode != 'RGB':
            input_image = input_image.convert('RGB')
        
        if progress_callback:
            progress_callback(5)
        
        # Convert PIL to numpy
        img_np = np.array(input_image).astype(np.float32) / 255.0
        
        # Convert to torch tensor [C, H, W]
        img_tensor = torch.from_numpy(np.transpose(img_np, (2, 0, 1))).float()
        img_tensor = img_tensor.unsqueeze(0).to(self.device)  # [1, C, H, W]
        
        if progress_callback:
            progress_callback(10)
        
        # Inference with tiling for large images
        with torch.no_grad():
            _, _, h_old, w_old = img_tensor.size()
            
            # Check if tiling is needed
            if h_old > tile_size or w_old > tile_size:
                output = self._test_tile(
                    img_tensor,
                    tile_size=tile_size,
                    tile_overlap=tile_overlap,
                    progress_callback=progress_callback
                )
            else:
                if progress_callback:
                    progress_callback(50)
                output = self.model(img_tensor)
                if progress_callback:
                    progress_callback(90)
        
        # Convert back to PIL
        output = output.data.squeeze().float().cpu().clamp_(0, 1).numpy()
        
        if output.ndim == 3:
            output = np.transpose(output, (1, 2, 0))  # [H, W, C]
        
        output = (output * 255.0).round().astype(np.uint8)
        result = Image.fromarray(output)
        
        if progress_callback:
            progress_callback(100)
        
        return result
    
    def _test_tile(
        self,
        img_tensor: torch.Tensor,
        tile_size: int = 512,
        tile_overlap: int = 32,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> torch.Tensor:
        """Process image in tiles to save memory"""
        b, c, h, w = img_tensor.size()
        tile = min(tile_size, h, w)
        stride = tile - tile_overlap
        h_idx_list = list(range(0, h - tile, stride)) + [h - tile]
        w_idx_list = list(range(0, w - tile, stride)) + [w - tile]
        E = torch.zeros(b, c, h * self.model_params['upscale'], w * self.model_params['upscale']).type_as(img_tensor)
        W = torch.zeros_like(E)
        
        total_tiles = len(h_idx_list) * len(w_idx_list)
        processed_tiles = 0
        
        for h_idx in h_idx_list:
            for w_idx in w_idx_list:
                in_patch = img_tensor[..., h_idx:h_idx + tile, w_idx:w_idx + tile]
                out_patch = self.model(in_patch)
                
                out_patch_mask = torch.ones_like(out_patch)
                
                E[..., h_idx * self.model_params['upscale']:(h_idx + tile) * self.model_params['upscale'],
                  w_idx * self.model_params['upscale']:(w_idx + tile) * self.model_params['upscale']].add_(out_patch)
                W[..., h_idx * self.model_params['upscale']:(h_idx + tile) * self.model_params['upscale'],
                  w_idx * self.model_params['upscale']:(w_idx + tile) * self.model_params['upscale']].add_(out_patch_mask)
                
                processed_tiles += 1
                if progress_callback:
                    progress = 10 + int((processed_tiles / total_tiles) * 80)
                    progress_callback(progress)
        
        output = E.div_(W)
        return output
    
    def upscale_from_base64(
        self,
        base64_image: str,
        scale_factor: int = 4,
        use_tiling: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> str:
        """
        Upscale from base64 string, return base64 string
        """
        if progress_callback:
            progress_callback(2)
        
        # Decode base64 to PIL Image
        image_data = base64.b64decode(base64_image)
        input_image = Image.open(io.BytesIO(image_data))
        
        # Set tile size based on use_tiling
        # If tiling is disabled, use a very large tile size to force single pass
        tile_size = 512 if use_tiling else 10000
        
        # Upscale
        output_image = self.upscale_image(
            input_image,
            scale_factor,
            tile_size=tile_size,
            progress_callback=progress_callback
        )
        
        # Encode back to base64
        if progress_callback:
            progress_callback(98)
        
        buffer = io.BytesIO()
        output_image.save(buffer, format='PNG')
        buffer.seek(0)
        result_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        if progress_callback:
            progress_callback(100)
        
        return result_base64
    
    def get_output_dimensions(self, width: int, height: int, scale: int) -> Tuple[int, int]:
        """Calculate output dimensions (always 4x for this model)"""
        return (width * 4, height * 4)
