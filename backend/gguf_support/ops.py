"""
GGUF Tensor Operations
Ported from ComfyUI-GGUF by city96 (Apache-2.0)
Standalone version without ComfyUI dependencies
"""
import torch
import gguf
from .dequant import dequantize_tensor, is_quantized, TORCH_COMPATIBLE_QTYPES


class GGMLTensor(torch.Tensor):
    """
    Custom tensor class for storing quantized GGML weights.
    Stores original tensor type and shape for dequantization.
    """
    def __init__(self, *args, tensor_type, tensor_shape, patches=[], **kwargs):
        super().__init__()
        self.tensor_type = tensor_type
        self.tensor_shape = tensor_shape
        self.patches = patches

    def __new__(cls, *args, tensor_type, tensor_shape, patches=[], **kwargs):
        return super().__new__(cls, *args, **kwargs)

    def to(self, *args, **kwargs):
        new = super().to(*args, **kwargs)
        new.tensor_type = getattr(self, "tensor_type", None)
        new.tensor_shape = getattr(self, "tensor_shape", new.data.shape)
        new.patches = getattr(self, "patches", []).copy()
        return new

    def clone(self, *args, **kwargs):
        return self

    def detach(self, *args, **kwargs):
        return self

    @property
    def shape(self):
        if not hasattr(self, "tensor_shape"):
            self.tensor_shape = self.size()
        return self.tensor_shape


def dequantize_weight(tensor, dtype=torch.float16):
    """
    Dequantize a GGMLTensor to standard PyTorch tensor.
    
    Args:
        tensor: GGMLTensor or regular tensor
        dtype: Target dtype for dequantized tensor
        
    Returns:
        Dequantized PyTorch tensor
    """
    if tensor is None:
        return None
    
    if not is_quantized(tensor):
        return tensor.to(dtype)
    
    weight = dequantize_tensor(tensor, dtype, None)
    
    # Prevent propagating custom tensor class
    if isinstance(weight, GGMLTensor):
        weight = torch.Tensor(weight)
    
    return weight
