"""
SDXL Inference Engine
Handles Stable Diffusion XL img2img with Juggernaut XL 9.0
Includes HiresFix and Skin Texture enhancement modules
"""

import os
import io
import base64
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, Dict, Tuple
from diffusers import (
    StableDiffusionXLImg2ImgPipeline,
    DPMSolverMultistepScheduler,
    AutoencoderKL
)


class SDXLEngine:
    def __init__(self, model_path: str, device: Optional[str] = None):
        """
        Initialize SDXL engine with Juggernaut XL checkpoint
        
        Args:
            model_path: Path to .safetensors checkpoint file
            device: 'cuda' or 'cpu', auto-detects if None
        """
        self.model_path = Path(model_path)
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        # Auto-detect device
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        print(f"SDXL Engine initializing on {self.device.upper()}...")
        
        # Load SDXL pipeline from single safetensors file
        # NOTE: load_safety_checker removed in diffusers 0.31+
        self.pipeline = StableDiffusionXLImg2ImgPipeline.from_single_file(
            str(self.model_path),
            torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
            use_safetensors=True
        )
        
        # Move to device
        self.pipeline = self.pipeline.to(self.device)
        
        # Set scheduler to DPM++ 2M Karras (high quality, fast)
        self.pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
            self.pipeline.scheduler.config,
            use_karras_sigmas=True,
            algorithm_type="dpmsolver++"
        )
        
        # Enable optimizations for GPU
        if self.device == 'cuda':
            # Enable memory efficient attention
            self.pipeline.enable_attention_slicing()
            
            # Enable VAE tiling for large images
            self.pipeline.enable_vae_tiling()
            
            # Enable xformers if available (huge speedup)
            try:
                self.pipeline.enable_xformers_memory_efficient_attention()
                print("[OK] xformers enabled for faster inference")
            except Exception as e:
                print(f"[!] xformers not available: {e}")
        
        print(f"[OK] SDXL Engine ready!")
    
    def _build_prompt(
        self, 
        base_prompt: str,
        enable_skin: bool = False,
        enable_hires: bool = False
    ) -> Tuple[str, str]:
        """
        Build enhanced prompts based on active modules
        
        Returns:
            (positive_prompt, negative_prompt)
        """
        positive = ["masterpiece", "best quality", "8k uhd", "highly detailed"]
        negative = [
            "blur", "low quality", "lowres", "artifacts", "watermark", "text", "jpeg artifacts",
            "deformed", "disfigured", "mutation", "mutated",  # Prevent mutations
            "different face", "altered features", "changed appearance",  # Face preservation
            "extra limbs", "bad anatomy", "bad proportions"  # Anatomy preservation
        ]
        
        # Add user's base prompt
        if base_prompt:
            positive.insert(0, base_prompt)
        
        # Skin Texture Module
        if enable_skin:
            positive.extend([
                "highly detailed skin",
                "skin pores",
                "natural skin texture",
                "subsurface scattering",
                "hyper-detailed face",
                "realistic skin",
                "pore-level details"
            ])
            negative.extend([
                "smooth skin",
                "plastic skin",
                "airbrushed",
                "wax skin",
                "doll skin"
            ])
        
        # HiresFix Module (adds general detail enhancement)
        if enable_hires:
            positive.extend([
                "sharp focus",
                "intricate details",
                "fine details",
                "crisp",
                "clear"
            ])
            negative.extend([
                "soft focus",
                "blurry background"
            ])
        
        return ", ".join(positive), ", ".join(negative)
    
    def enhance_image(
        self,
        input_image: Image.Image,
        modules: Dict[str, bool],
        prompt: str = "",
        denoising_strength: float = 0.25,  # Lowered from 0.4 for better preservation
        cfg_scale: float = 7.0,
        steps: int = 25,
        seed: Optional[int] = None
    ) -> Image.Image:
        """
        Enhance image using SDXL img2img
        
        Args:
            input_image: PIL Image
            modules: Dict with keys 'skin_texture', 'hires_fix', 'upscale'
            prompt: Optional user prompt
            denoising_strength: How much to change (0.0-1.0)
            cfg_scale: Prompt adherence (1.0-20.0)
            steps: Number of inference steps
            seed: Random seed for reproducibility
            
        Returns:
            Enhanced PIL Image
        """
        # Build prompts based on active modules
        positive_prompt, negative_prompt = self._build_prompt(
            prompt,
            enable_skin=modules.get('skin_texture', False),
            enable_hires=modules.get('hires_fix', False)
        )
        
        print(f"Positive: {positive_prompt[:100]}...")
        print(f"Negative: {negative_prompt[:100]}...")
        
        # Set seed if provided
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        
        # Prepare image dimensions (SDXL works best with multiples of 64)
        width, height = input_image.size
        width = (width // 64) * 64
        height = (height // 64) * 64
        
        if (width, height) != input_image.size:
            print(f"Resizing from {input_image.size} to ({width}, {height}) for SDXL compatibility")
            input_image = input_image.resize((width, height), Image.LANCZOS)
        
        # HiresFix: Two-pass generation for better quality
        if modules.get('hires_fix', False):
            print("HiresFix enabled: Running two-pass generation...")
            
            # First pass: Lower denoising
            result = self.pipeline(
                image=input_image,
                prompt=positive_prompt,
                negative_prompt=negative_prompt,
                strength=denoising_strength * 0.7,  # 70% of requested strength
                guidance_scale=cfg_scale,
                num_inference_steps=steps,
                generator=generator
            ).images[0]
            
            # Second pass: Refinement
            result = self.pipeline(
                image=result,
                prompt=positive_prompt,
                negative_prompt=negative_prompt,
                strength=denoising_strength * 0.3,  # 30% refinement
                guidance_scale=cfg_scale,
                num_inference_steps=steps // 2,  # Fewer steps for refinement
                generator=generator
            ).images[0]
            
        else:
            # Single pass generation
            result = self.pipeline(
                image=input_image,
                prompt=positive_prompt,
                negative_prompt=negative_prompt,
                strength=denoising_strength,
                guidance_scale=cfg_scale,
                num_inference_steps=steps,
                generator=generator
            ).images[0]
        
        return result
    
    def enhance_from_base64(
        self,
        base64_image: str,
        modules: Dict[str, bool],
        prompt: str = "",
        denoising_strength: float = 0.4,
        cfg_scale: float = 7.0,
        steps: int = 25,
        seed: Optional[int] = None
    ) -> str:
        """
        Enhance from base64 string, return base64 string
        
        Args:
            base64_image: Base64 encoded image
            modules: Enhancement modules to enable
            Other args: Same as enhance_image()
            
        Returns:
            Base64 encoded enhanced image
        """
        # Decode base64 to PIL Image
        image_data = base64.b64decode(base64_image)
        input_image = Image.open(io.BytesIO(image_data))
        
        # Convert RGBA to RGB if needed
        if input_image.mode == 'RGBA':
            rgb_image = Image.new('RGB', input_image.size, (255, 255, 255))
            rgb_image.paste(input_image, mask=input_image.split()[3])
            input_image = rgb_image
        elif input_image.mode != 'RGB':
            input_image = input_image.convert('RGB')
        
        buffer = io.BytesIO()
        output_image.save(buffer, format='PNG')
        buffer.seek(0)
        result_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        return result_base64
    
    def unload(self):
        """Free GPU memory"""
        if hasattr(self, 'pipeline'):
            del self.pipeline
            if self.device == 'cuda':
                torch.cuda.empty_cache()
