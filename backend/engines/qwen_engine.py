"""
Qwen2-VL Engine for Upscale Engine CC
Multimodal vision-language model for image analysis and prompt generation
"""
import os
import base64
import io
from pathlib import Path
from PIL import Image
from typing import Optional

try:
    from llama_cpp import Llama
except ImportError:
    print("llama-cpp-python not installed")
    Llama = None


class QwenEngine:
    """
    Qwen2-VL Engine for image understanding and prompt generation.
    Uses llama-cpp-python with Qwen chat format for multimodal inference.
    """
    
    def __init__(self, model_path: str, device: str = 'cuda'):
        if Llama is None:
            raise ImportError("llama-cpp-python is required for QwenEngine")

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        n_gpu = -1 if device == 'cuda' else 0
        
        print(f"Loading Qwen2-VL from {self.model_path}...")
        print(f"  Device: {'GPU (all layers)' if n_gpu == -1 else 'CPU'}")
        
        # Qwen2-VL GGUF Configuration
        # Uses ChatML format which supports multimodal messages
        load_kwargs = {
            "model_path": str(self.model_path),
            "n_ctx": 4096,  # Larger context for image tokens
            "n_gpu_layers": n_gpu,
            "verbose": False,
            "chat_format": "chatml",  # Qwen uses ChatML format
        }
        
        try:
            self.model = Llama(**load_kwargs)
            print("✓ Qwen2-VL loaded successfully")
            self._test_model()
        except Exception as e:
            print(f"Error loading Qwen on GPU: {e}")
            if n_gpu != 0:
                print("Retrying on CPU (this will be slower)...")
                load_kwargs["n_gpu_layers"] = 0
                try:
                    self.model = Llama(**load_kwargs)
                    print("✓ Qwen2-VL loaded on CPU")
                except Exception as e2:
                    print(f"Failed to load Qwen on CPU: {e2}")
                    raise e2
            else:
                raise e
    
    def _test_model(self):
        """Quick test to verify model responds"""
        try:
            test = self.model.create_chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            print(f"  Model test: OK (responded)")
        except Exception as e:
            print(f"  Model test warning: {e}")
    
    def _image_to_base64(self, image: Image.Image, max_size: int = 768) -> str:
        """Convert PIL Image to base64 data URI, resizing if needed"""
        # Resize large images for faster processing
        if max(image.size) > max_size:
            image = image.copy()
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Convert to RGB if needed (removes alpha channel)
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/jpeg;base64,{img_str}"

    def generate_prompt(self, image: Image.Image) -> str:
        """
        Analyze image and generate a photorealistic enhancement prompt.
        
        Args:
            image: PIL Image to analyze
            
        Returns:
            Text prompt describing how to make the image photorealistic
        """
        try:
            # Convert image to base64 data URI
            data_uri = self._image_to_base64(image)
            
            # Qwen2-VL multimodal message format
            # The model should understand images embedded as data URIs in content
            system_prompt = """You are an expert image analyst. Analyze the provided image and describe what modifications would make it look more photorealistic.
Focus on: lighting, texture, color grading, and fine details. 
Output ONLY a comma-separated list of enhancement keywords (no explanations)."""

            user_content = f"""[Image: {data_uri}]

Analyze this image and provide enhancement keywords to make it photorealistic."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
            
            print("Qwen: Analyzing image...")
            response = self.model.create_chat_completion(
                messages=messages,
                max_tokens=150,
                temperature=0.7,
                top_p=0.9,
                repeat_penalty=1.1
            )
            
            content = response["choices"][0]["message"]["content"].strip()
            print(f"Qwen Response: {content}")
            
            # Clean up response - extract keywords
            prompt = self._clean_prompt(content)
            return prompt
            
        except Exception as e:
            print(f"Qwen generation error: {e}")
            # Fallback prompt if analysis fails
            return "photorealistic, 8k uhd, highly detailed, raw photo, dslr quality, natural lighting"
    
    def _clean_prompt(self, raw_content: str) -> str:
        """Clean and format the model's output into a usable prompt"""
        # Remove common prefixes the model might add
        prefixes_to_remove = [
            "Enhancement keywords:",
            "Keywords:",
            "To make this image photorealistic:",
            "Here are the keywords:",
            "Prompt:"
        ]
        
        content = raw_content
        for prefix in prefixes_to_remove:
            if content.lower().startswith(prefix.lower()):
                content = content[len(prefix):].strip()
        
        # If content is too short or empty, use fallback
        if len(content) < 10:
            return "photorealistic, 8k, highly detailed, raw photo, natural lighting"
        
        # Ensure it ends cleanly (no trailing commas or periods)
        content = content.rstrip('.,;: ')
        
        # Add base quality keywords if not present
        quality_keywords = ["photorealistic", "8k", "detailed"]
        has_quality = any(kw in content.lower() for kw in quality_keywords)
        
        if not has_quality:
            content = f"photorealistic, {content}"
        
        return content
    
    def describe_image(self, image: Image.Image) -> str:
        """
        Generate a detailed description of the image.
        
        Args:
            image: PIL Image to describe
            
        Returns:
            Detailed text description of the image
        """
        try:
            data_uri = self._image_to_base64(image)
            
            messages = [
                {"role": "system", "content": "You are an expert image analyst. Describe images in detail."},
                {"role": "user", "content": f"[Image: {data_uri}]\n\nDescribe this image in detail."}
            ]
            
            response = self.model.create_chat_completion(
                messages=messages,
                max_tokens=300,
                temperature=0.5
            )
            
            return response["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            print(f"Image description error: {e}")
            return "Unable to describe image"
    
    def unload(self):
        """Free GPU memory"""
        if hasattr(self, 'model'):
            del self.model
            print("Qwen model unloaded")

