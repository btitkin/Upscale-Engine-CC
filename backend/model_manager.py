"""
LumaScale Model Manager
Handles lazy loading and unloading of AI models to manage VRAM usage.
"""

import torch
import gc
import sys
from typing import Dict, Optional, Any
from pathlib import Path

# Ensure backend is in path
sys.path.insert(0, str(Path(__file__).parent))

from model_downloader import ModelDownloader
from engines.esrgan_engine import ESRGANEngine
from engines.swinir_engine import SwinIREngine
from engines.supresdiffgan_engine import SupResDiffGANEngine
from engines.sdxl_engine import SDXLEngine
from engines.qwen_engine import QwenEngine
from engines.gfpgan_engine import GFPGANEngine
from engines.inpaint_engine import InpaintEngine

class ModelManager:
    def __init__(self, downloader: ModelDownloader):
        self.downloader = downloader
        self.loaded_models: Dict[str, Any] = {}
        self.active_model_key: Optional[str] = None
        
        # Determine device once
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"ModelManager initialized. Device: {self.device}")

    def unload_all(self):
        """Unload all models to free VRAM"""
        if not self.loaded_models:
            return

        print("Unloading all models...")
        keys = list(self.loaded_models.keys())
        for key in keys:
            print(f"  - Unloading {key}")
            # Explicitly delete the object
            del self.loaded_models[key]
        
        self.loaded_models = {}
        self.active_model_key = None
        
        # Force Garbage Collection
        gc.collect()
        
        # Clear CUDA cache
        if self.device == 'cuda':
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        
        print("VRAM cleared.")

    def get_model(self, model_key: str):
        """
        Get a model instance, loading it if necessary.
        Unloads other models to ensure VRAM availability.
        """
        # If already loaded, return it
        if model_key in self.loaded_models:
            self.active_model_key = model_key
            return self.loaded_models[model_key]
            
        # If another model is loaded, unload it
        # We implement a "Single Active Model" policy for safety
        if self.active_model_key is not None and self.active_model_key != model_key:
            print(f"Switching models: {self.active_model_key} -> {model_key}")
            self.unload_all()
            
        # Load the requested model
        print(f"Loading model: {model_key}...")
        engine = None
        
        try:
            if model_key == "esrgan":
                path = self.downloader.get_model_path("upscale")
                if not path: raise FileNotFoundError("ESRGAN model not found")
                engine = ESRGANEngine(str(path), device=self.device)
                
            elif model_key == "swinir":
                path = self.downloader.get_model_path("swinir")
                if not path: raise FileNotFoundError("SwinIR model not found")
                engine = SwinIREngine(str(path), device=self.device)
                
            elif model_key == "supresdiffgan":
                path = self.downloader.get_model_path("supresdiffgan")
                if not path: raise FileNotFoundError("SupResDiffGAN model not found")
                engine = SupResDiffGANEngine(str(path), device=self.device)
                
            elif model_key == "sdxl":
                path = self.downloader.get_model_path("sdxl")
                if not path: raise FileNotFoundError("SDXL model not found")
                engine = SDXLEngine(str(path)) # SDXL engine handles device internally usually, or we should pass it
                # Checking SDXLEngine source... it usually auto-detects.
            
            elif model_key == "qwen":
                path = self.downloader.get_model_path("qwen")
                if not path: raise FileNotFoundError("Qwen model not found")
                engine = QwenEngine(str(path), device=self.device)
            
            elif model_key == "gfpgan":
                path = self.downloader.get_model_path("gfpgan")
                if not path: raise FileNotFoundError("GFPGAN model not found")
                engine = GFPGANEngine(str(path), device=self.device)
            
            elif model_key == "inpaint":
                # Inpaint uses SDXL model or downloads from HuggingFace
                path = self.downloader.get_model_path("sdxl")
                engine = InpaintEngine(str(path) if path else None, device=self.device)
            
            else:
                raise ValueError(f"Unknown model key: {model_key}")
                
            if engine:
                self.loaded_models[model_key] = engine
                self.active_model_key = model_key
                print(f"✓ {model_key} loaded successfully")
                return engine
                
        except Exception as e:
            print(f"Error loading {model_key}: {e}")
            # If load failed, ensure we clean up
            self.unload_all()
            raise e

    def get_status(self):
        """Get status of loaded models"""
        return {
            "active_model": self.active_model_key,
            "loaded_models": list(self.loaded_models.keys()),
            "vram_usage": self._get_vram_usage()
        }

    def _get_vram_usage(self):
        if self.device == 'cuda':
            try:
                allocated = torch.cuda.memory_allocated() / 1024**3
                reserved = torch.cuda.memory_reserved() / 1024**3
                return {
                    "allocated_gb": round(allocated, 2),
                    "reserved_gb": round(reserved, 2)
                }
            except:
                return None
        return None
