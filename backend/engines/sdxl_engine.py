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
from typing import Optional, Dict, Tuple, Callable
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
        denoising_strength: float = 0.25,
        cfg_scale: float = 7.0,
        steps: int = 25,
        seed: Optional[int] = None,
        use_tiling: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
        preview_callback: Optional[Callable[[str, int], None]] = None  # (base64, step)
    ) -> Image.Image:
        """
        Enhance image using SDXL img2img
        
        Args:
            preview_callback: Optional callback(base64_image, step_number) for live preview
        """
        # Build prompts
        positive_prompt, negative_prompt = self._build_prompt(
            prompt,
            enable_skin=modules.get('skin_texture', False),
            enable_hires=modules.get('hires_fix', False)
        )
        
        print(f"Positive: {positive_prompt[:100]}...")
        
        # Set seed
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        
        # Resize for SDXL
        width, height = input_image.size
        width = (width // 64) * 64
        height = (height // 64) * 64
        if (width, height) != input_image.size:
            input_image = input_image.resize((width, height), Image.LANCZOS)

        # Preview dimensions (x2 downscale for speed)
        preview_width = max(256, width // 2)
        preview_height = max(256, height // 2)

        # Helper to decode latents and send preview
        def send_preview_from_latents(latents, step_num):
            if preview_callback is None:
                return
            try:
                with torch.no_grad():
                    # Decode latents to image
                    decoded = self.pipeline.vae.decode(
                        latents / self.pipeline.vae.config.scaling_factor
                    ).sample
                    
                    # Convert to PIL Image
                    decoded = (decoded / 2 + 0.5).clamp(0, 1)
                    decoded = decoded.cpu().permute(0, 2, 3, 1).float().numpy()
                    
                    if decoded.shape[0] > 0:
                        img_array = (decoded[0] * 255).astype(np.uint8)
                        preview_img = Image.fromarray(img_array)
                        
                        # Resize for faster transfer (x2 downscale)
                        preview_img = preview_img.resize(
                            (preview_width, preview_height), 
                            Image.LANCZOS
                        )
                        
                        # Convert to base64
                        buffer = io.BytesIO()
                        preview_img.save(buffer, format='JPEG', quality=70)
                        preview_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        
                        preview_callback(preview_b64, step_num)
            except Exception as e:
                print(f"Preview error: {e}")

        # Helper for inference with retry
        def run_inference(tiling_enabled):
            # Toggle VAE Tiling
            if self.device == 'cuda':
                if tiling_enabled:
                    self.pipeline.enable_vae_tiling()
                    # Disable slicing when tiling is on to prevent conflicts
                    self.pipeline.disable_attention_slicing()
                else:
                    self.pipeline.disable_vae_tiling()
                    self.pipeline.enable_attention_slicing()

            # HiresFix: Two-pass generation
            if modules.get('hires_fix', False):
                print("HiresFix enabled: Running two-pass generation...")
                
                # Pass 1 (0-50%)
                def cb_pass1(pipe, step, t, kwargs):
                    if progress_callback:
                        progress_callback(int((step / steps) * 50))
                    # Send preview every 4 steps
                    if preview_callback and step > 0 and step % 4 == 0:
                        send_preview_from_latents(kwargs.get("latents"), step)
                    return kwargs

                result = self.pipeline(
                    image=input_image,
                    prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    strength=denoising_strength * 0.7,
                    guidance_scale=cfg_scale,
                    num_inference_steps=steps,
                    generator=generator,
                    callback_on_step_end=cb_pass1,
                    callback_on_step_end_tensor_inputs=["latents"]
                ).images[0]
                
                # Pass 2 (50-100%)
                def cb_pass2(pipe, step, t, kwargs):
                    if progress_callback:
                        progress_callback(50 + int((step / (steps // 2)) * 50))
                    # Send preview every 4 steps
                    if preview_callback and step > 0 and step % 4 == 0:
                        send_preview_from_latents(kwargs.get("latents"), steps + step)
                    return kwargs

                result = self.pipeline(
                    image=result,
                    prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    strength=denoising_strength * 0.3,
                    guidance_scale=cfg_scale,
                    num_inference_steps=steps // 2,
                    generator=generator,
                    callback_on_step_end=cb_pass2,
                    callback_on_step_end_tensor_inputs=["latents"]
                ).images[0]
                
            else:
                # Single pass with preview
                def callback_with_preview(pipe, step, t, kwargs):
                    if progress_callback:
                        progress_callback(int((step / steps) * 100))
                    # Send preview every 4 steps
                    if preview_callback and step > 0 and step % 4 == 0:
                        send_preview_from_latents(kwargs.get("latents"), step)
                    return kwargs

                result = self.pipeline(
                    image=input_image,
                    prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    strength=denoising_strength,
                    guidance_scale=cfg_scale,
                    num_inference_steps=steps,
                    generator=generator,
                    callback_on_step_end=callback_with_preview,
                    callback_on_step_end_tensor_inputs=["latents"]
                ).images[0]
            
            return result

        try:
            # Try with requested tiling setting
            result = run_inference(use_tiling)
        except RuntimeError as e:
            if "cannot reshape tensor" in str(e) and use_tiling:
                print(f"[WARN] VAE Tiling failed: {e}")
                print("[INFO] Retrying without VAE tiling...")
                if progress_callback: progress_callback(0) # Reset progress
                result = run_inference(False)
            else:
                raise e
        
        if progress_callback: progress_callback(100)
        return result
    
    def enhance_from_base64(
        self,
        base64_image: str,
        modules: Dict[str, bool],
        prompt: str = "",
        denoising_strength: float = 0.4,
        cfg_scale: float = 7.0,
        steps: int = 25,
        seed: Optional[int] = None,
        use_tiling: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
        preview_callback: Optional[Callable[[str, int], None]] = None
    ) -> str:
        """
        Enhance from base64 string, return base64 string
        
        Args:
            base64_image: Base64 encoded image
            modules: Enhancement modules to enable
            preview_callback: Optional callback(base64_image, step) for live preview
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
        
        # Process
        output_image = self.enhance_image(
            input_image,
            modules=modules,
            prompt=prompt,
            denoising_strength=denoising_strength,
            cfg_scale=cfg_scale,
            steps=steps,
            seed=seed,
            use_tiling=use_tiling,
            progress_callback=progress_callback,
            preview_callback=preview_callback
        )
        
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
