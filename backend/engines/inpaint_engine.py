"""
SDXL Inpainting Engine
Uses diffusers SDXL inpainting pipeline for mask-based image editing
"""
import os
import gc
import base64
import io
from pathlib import Path
from typing import Optional, Callable
import torch
from PIL import Image
import numpy as np


class InpaintEngine:
    """Inpainting engine using SDXL"""
    
    def __init__(self, model_path: Optional[str] = None, device: str = 'cuda'):
        self.device = device if torch.cuda.is_available() else 'cpu'
        self.model_path = model_path
        self.pipe = None
        
    def _load_pipeline(self):
        """Lazy load the inpainting pipeline"""
        if self.pipe is not None:
            return
            
        try:
            from diffusers import StableDiffusionXLInpaintPipeline, AutoencoderKL
            
            print("[Inpaint] Loading SDXL Inpaint pipeline...")
            
            # Try to load from single file if path provided
            if self.model_path and Path(self.model_path).exists():
                # Load from safetensors checkpoint
                self.pipe = StableDiffusionXLInpaintPipeline.from_single_file(
                    self.model_path,
                    torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
                    use_safetensors=True
                )
            else:
                # Fall back to HuggingFace model
                self.pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
                    "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
                    torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
                    variant="fp16" if self.device == 'cuda' else None
                )
            
            self.pipe = self.pipe.to(self.device)
            
            # Enable memory optimizations
            if self.device == 'cuda':
                self.pipe.enable_attention_slicing()
                try:
                    self.pipe.enable_xformers_memory_efficient_attention()
                except:
                    pass
            
            print("[Inpaint] ✓ Pipeline loaded")
            
        except Exception as e:
            print(f"[Inpaint] Failed to load pipeline: {e}")
            raise
    
    def inpaint(
        self,
        image: Image.Image,
        mask: Image.Image,
        prompt: str,
        negative_prompt: str = "blurry, bad quality, distorted, deformed",
        strength: float = 0.75,
        num_steps: int = 30,
        guidance_scale: float = 7.5,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Image.Image:
        """
        Inpaint image using mask
        
        Args:
            image: Input PIL Image (RGB)
            mask: Mask PIL Image (white = inpaint, black = keep)
            prompt: What to generate in masked area
            negative_prompt: What to avoid
            strength: How much to change (0.0-1.0)
            num_steps: Inference steps
            guidance_scale: CFG scale
            progress_callback: Optional callback(step, total_steps)
            
        Returns:
            Inpainted PIL Image
        """
        self._load_pipeline()
        
        # Ensure images are correct size and format
        # SDXL needs dimensions divisible by 8
        target_w = (image.width // 8) * 8
        target_h = (image.height // 8) * 8
        
        if image.size != (target_w, target_h):
            image = image.resize((target_w, target_h), Image.LANCZOS)
        if mask.size != (target_w, target_h):
            mask = mask.resize((target_w, target_h), Image.NEAREST)
        
        # Convert mask to proper format (L mode, white = inpaint)
        if mask.mode != 'L':
            mask = mask.convert('L')
        
        # Callback wrapper for diffusers
        def callback_on_step(step, timestep, latents):
            if progress_callback:
                progress_callback(step + 1, num_steps)
        
        try:
            result = self.pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=image,
                mask_image=mask,
                strength=strength,
                num_inference_steps=num_steps,
                guidance_scale=guidance_scale,
                callback=callback_on_step,
                callback_steps=1
            ).images[0]
            
            return result
            
        except Exception as e:
            print(f"[Inpaint] Error during inference: {e}")
            raise
    
    def inpaint_from_base64(
        self,
        image_b64: str,
        mask_b64: str,
        prompt: str,
        strength: float = 0.75,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> str:
        """
        Inpaint from base64 encoded images
        
        Returns:
            Result image as base64 PNG
        """
        # Decode image
        img_data = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(img_data)).convert('RGB')
        
        # Decode mask (handle data URL format)
        if mask_b64.startswith('data:'):
            mask_b64 = mask_b64.split(',')[1]
        mask_data = base64.b64decode(mask_b64)
        mask = Image.open(io.BytesIO(mask_data)).convert('L')
        
        # Scale mask to match image size
        if mask.size != image.size:
            mask = mask.resize(image.size, Image.NEAREST)
        
        # Run inpainting
        result = self.inpaint(
            image=image,
            mask=mask,
            prompt=prompt,
            strength=strength,
            progress_callback=progress_callback
        )
        
        # Encode result
        buffer = io.BytesIO()
        result.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode()
    
    def unload(self):
        """Unload pipeline to free VRAM"""
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("[Inpaint] Pipeline unloaded")
    
    def is_available(self) -> bool:
        """Check if inpainting is available"""
        try:
            from diffusers import StableDiffusionXLInpaintPipeline
            return True
        except ImportError:
            return False
