"""
SupResDiffGAN Inference Engine
Wrapper for SupResDiffGAN model
"""
import sys
import os
import torch
import numpy as np
from pathlib import Path
from PIL import Image
import io
import base64
from omegaconf import OmegaConf
from diffusers import AutoencoderKL

# Add repo to sys.path
REPO_PATH = Path(__file__).parent.parent / "SupResDiffGAN_repo"
sys.path.insert(0, str(REPO_PATH))

# Import from repo
try:
    from SupResDiffGAN.SupResDiffGAN import SupResDiffGAN
    from SupResDiffGAN.modules.Diffusion import Diffusion as Diffusion_supresdiffgan
    from SupResDiffGAN.modules.Discriminator import Discriminator as Discriminator_supresdiffgan
    from SupResDiffGAN.modules.UNet import UNet as UNet_supresdiffgan
except ImportError as e:
    print(f"Error importing SupResDiffGAN modules: {e}")
    # Try to add scripts to path as well
    sys.path.insert(0, str(REPO_PATH / "scripts"))
    from SupResDiffGAN.SupResDiffGAN import SupResDiffGAN
    from SupResDiffGAN.modules.Diffusion import Diffusion as Diffusion_supresdiffgan
    from SupResDiffGAN.modules.Discriminator import Discriminator as Discriminator_supresdiffgan
    from SupResDiffGAN.modules.UNet import UNet as UNet_supresdiffgan

class SupResDiffGANEngine:
    def __init__(self, model_path: str, device: str = 'cuda'):
        self.device = device
        self.model_path = model_path
        
        print(f"Initializing SupResDiffGAN from {model_path} on {device}...")
        
        # Load default config
        config_path = REPO_PATH / "conf" / "config_supresdiffgan.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found at {config_path}")
            
        self.cfg = OmegaConf.load(config_path)
        
        # Override config for inference
        self.cfg.model.load_model = model_path
        
        # Initialize model manually to handle VAE issues
        try:
            self.model = self._initialize_model(self.cfg, torch.device(self.device))
        except Exception as e:
            print(f"Error initializing SupResDiffGAN: {e}")
            raise
        
        self.model.to(self.device)
        self.model.eval()
        print("SupResDiffGAN loaded successfully.")
    
    def _initialize_model(self, cfg, device):
        # Load VAE
        # Try to use stabilityai/sd-vae-ft-mse which is public and high quality
        # Fallback to SD 2.1 if needed (might require auth)
        try:
            print("Loading VAE (stabilityai/sd-vae-ft-mse)...")
            autoencoder = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", token=False).to(device)
        except Exception as e:
            print(f"Failed to load sd-vae-ft-mse: {e}")
            print("Trying stabilityai/stable-diffusion-2-1...")
            autoencoder = AutoencoderKL.from_pretrained("stabilityai/stable-diffusion-2-1", subfolder="vae", token=False).to(device)

        # Create components
        # We don't need discriminator for inference, but load_from_checkpoint might expect it 
        # if strict loading is on. However, usually Lightning handles missing keys if strict=False?
        # But here we are passing it to __init__.
        
        discriminator = None 
        # Note: If the checkpoint has discriminator weights, and we pass None, it might be fine 
        # as long as we don't use it. But SupResDiffGAN.__init__ assigns it.
        # Let's create it just in case to match structure, but it's unused.
        # Actually, initialize_supresdiffgan allows use_discriminator=False.
        
        unet = UNet_supresdiffgan(cfg.unet)

        diffusion = Diffusion_supresdiffgan(
            timesteps=cfg.diffusion.timesteps,
            beta_type=cfg.diffusion.beta_type,
            posterior_type=cfg.diffusion.posterior_type,
        )

        vgg_loss = None

        # Load checkpoint
        print(f"Loading checkpoint from {cfg.model.load_model}...")
        model = SupResDiffGAN.load_from_checkpoint(
            cfg.model.load_model,
            map_location=device,
            ae=autoencoder,
            discriminator=discriminator,
            unet=unet,
            diffusion=diffusion,
            learning_rate=cfg.model.lr,
            alfa_perceptual=cfg.model.alfa_perceptual,
            alfa_adv=cfg.model.alfa_adv,
            vgg_loss=vgg_loss,
            strict=False # Allow missing discriminator weights
        )
        
        return model

    def upscale_from_base64(
        self, 
        base64_image: str, 
        scale_factor: int = 4, 
        use_tiling: bool = True,
        progress_callback=None
    ) -> str:
        # Decode
        if progress_callback: progress_callback(5)
        image_data = base64.b64decode(base64_image)
        input_image = Image.open(io.BytesIO(image_data)).convert('RGB')
        
        # Pre-upscale using Bicubic
        target_width = input_image.width * scale_factor
        target_height = input_image.height * scale_factor
        
        upscaled_input = input_image.resize((target_width, target_height), Image.BICUBIC)
        
        # Convert to tensor [-1, 1]
        img_tensor = torch.from_numpy(np.array(upscaled_input)).float() / 127.5 - 1.0
        img_tensor = img_tensor.permute(2, 0, 1).unsqueeze(0).to(self.device)
        
        if progress_callback: progress_callback(20)
        
        # Inference
        with torch.no_grad():
            if use_tiling:
                output = self._process_tiled(img_tensor, tile_size=512, overlap=32, progress_callback=progress_callback)
            else:
                output = self.model(img_tensor)
                if progress_callback: progress_callback(90)
            
        # Post-process
        output = (output.clamp(-1, 1) + 1) / 2.0 * 255.0
        output = output.cpu().permute(0, 2, 3, 1).numpy().astype(np.uint8)[0]
        
        output_image = Image.fromarray(output)
        
        # Encode
        buffer = io.BytesIO()
        output_image.save(buffer, format='PNG')
        buffer.seek(0)
        result_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        if progress_callback: progress_callback(100)
        
        return result_base64

    def _process_tiled(self, img_tensor, tile_size=512, overlap=32, progress_callback=None):
        """Process image in tiles to save memory"""
        b, c, h, w = img_tensor.size()
        tile = min(tile_size, h, w)
        stride = tile - overlap
        
        h_idx_list = list(range(0, h - tile, stride)) + [h - tile]
        w_idx_list = list(range(0, w - tile, stride)) + [w - tile]
        
        E = torch.zeros_like(img_tensor)
        W = torch.zeros_like(E)
        
        total_tiles = len(h_idx_list) * len(w_idx_list)
        processed_tiles = 0
        
        for h_idx in h_idx_list:
            for w_idx in w_idx_list:
                in_patch = img_tensor[..., h_idx:h_idx + tile, w_idx:w_idx + tile]
                out_patch = self.model(in_patch)
                
                out_patch_mask = torch.ones_like(out_patch)
                
                E[..., h_idx:h_idx + tile, w_idx:w_idx + tile].add_(out_patch)
                W[..., h_idx:h_idx + tile, w_idx:w_idx + tile].add_(out_patch_mask)
                
                processed_tiles += 1
                if progress_callback:
                    # Map 20-90% range
                    progress = 20 + int((processed_tiles / total_tiles) * 70)
                    progress_callback(progress)
        
        output = E.div_(W)
        return output

    def get_output_dimensions(self, width, height, scale):
        return width * scale, height * scale
