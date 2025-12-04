"""
GGUF Support Module
Provides functionality to load and use GGUF quantized diffusion models.
Ported from ComfyUI-GGUF by city96 (Apache-2.0)
"""
from .loader import load_gguf_state_dict, get_gguf_info
from .ops import GGMLTensor, dequantize_weight
from .dequant import is_quantized, is_torch_compatible, dequantize_tensor

__all__ = [
    "load_gguf_state_dict",
    "get_gguf_info", 
    "GGMLTensor",
    "dequantize_weight",
    "is_quantized",
    "is_torch_compatible",
    "dequantize_tensor"
]
