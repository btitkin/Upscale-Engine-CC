"""
GFPGAN Face Enhancement Engine
Provides face restoration and enhancement using GFPGAN
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


class GFPGANEngine:
    """Face enhancement using GFPGAN"""
    
    def __init__(self, model_path: Optional[str] = None, device: str = 'cuda'):
        self.device = device if torch.cuda.is_available() else 'cpu'
        self.model_path = model_path
        self.restorer = None
        
        # Try to load GFPGAN
        self._load_model()
    
    def _load_model(self):
        """Load GFPGAN model"""
        try:
            from gfpgan import GFPGANer
            
            # Default model path
            if self.model_path is None:
                # Check common locations
                possible_paths = [
                    Path(__file__).parent.parent.parent / "models" / "GFPGANv1.4.pth",
                    Path(__file__).parent.parent.parent / "models" / "gfpgan" / "GFPGANv1.4.pth",
                ]
                for p in possible_paths:
                    if p.exists():
                        self.model_path = str(p)
                        break
            
            if self.model_path and Path(self.model_path).exists():
                # Background upscaler
                bg_upsampler = None
                
                self.restorer = GFPGANer(
                    model_path=self.model_path,
                    upscale=2,
                    arch='clean',
                    channel_multiplier=2,
                    bg_upsampler=bg_upsampler,
                    device=torch.device(self.device)
                )
                print(f"✓ GFPGAN loaded from {self.model_path}")
            else:
                print(f"⚠ GFPGAN model not found at {self.model_path}")
                self.restorer = None
                
        except ImportError:
            print("⚠ GFPGAN not installed. Run: pip install gfpgan")
            self.restorer = None
        except Exception as e:
            print(f"⚠ GFPGAN load error: {e}")
            self.restorer = None
    
    def is_available(self) -> bool:
        """Check if GFPGAN is available"""
        return self.restorer is not None
    
    def enhance_face(
        self, 
        image: Image.Image,
        upscale: int = 2,
        only_center_face: bool = False,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Optional[Image.Image]:
        """
        Enhance faces in image
        
        Args:
            image: Input PIL Image
            upscale: Upscale factor (1-4)
            only_center_face: Only restore the center face
            progress_callback: Optional progress callback
            
        Returns:
            Enhanced PIL Image or None
        """
        if not self.is_available():
            print("GFPGAN not available")
            return None
        
        try:
            if progress_callback:
                progress_callback(10)
            
            # Convert PIL to numpy BGR (OpenCV format)
            img_np = np.array(image)
            if len(img_np.shape) == 2:
                img_np = np.stack([img_np] * 3, axis=-1)
            elif img_np.shape[2] == 4:
                img_np = img_np[:, :, :3]
            
            # RGB to BGR
            img_bgr = img_np[:, :, ::-1]
            
            if progress_callback:
                progress_callback(30)
            
            # Restore faces
            _, _, restored_img = self.restorer.enhance(
                img_bgr,
                has_aligned=False,
                only_center_face=only_center_face,
                paste_back=True
            )
            
            if progress_callback:
                progress_callback(90)
            
            if restored_img is None:
                print("No faces detected or restoration failed")
                return image  # Return original if no faces
            
            # BGR to RGB and convert to PIL
            restored_rgb = restored_img[:, :, ::-1]
            result = Image.fromarray(restored_rgb)
            
            if progress_callback:
                progress_callback(100)
            
            return result
            
        except Exception as e:
            print(f"Face enhancement error: {e}")
            return None
    
    def enhance_from_base64(
        self,
        image_b64: str,
        upscale: int = 2,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Optional[str]:
        """
        Enhance faces from base64 image
        
        Returns:
            Enhanced image as base64 string
        """
        try:
            # Decode
            img_data = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(img_data)).convert('RGB')
            
            # Enhance
            result = self.enhance_face(image, upscale, progress_callback=progress_callback)
            
            if result is None:
                return None
            
            # Encode
            buffer = io.BytesIO()
            result.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode()
            
        except Exception as e:
            print(f"Face enhancement from base64 error: {e}")
            return None
    
    def unload(self):
        """Unload model to free VRAM"""
        if self.restorer is not None:
            self.restorer = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("GFPGAN unloaded")
