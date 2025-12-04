"""
GGUF File Loader
Ported from ComfyUI-GGUF by city96 (Apache-2.0)
Standalone version without ComfyUI dependencies
"""
import warnings
import logging
import torch
import gguf

from .ops import GGMLTensor
from .dequant import is_quantized

# Supported architectures
IMG_ARCH_LIST = {"flux", "sd1", "sdxl", "sd3", "aura", "hidream", "cosmos", "ltxv", "hyvid", "wan", "lumina2", "qwen_image"}
TXT_ARCH_LIST = {"t5", "t5encoder", "llama", "qwen2vl", "qwen3", "qwen3vl"}


def get_orig_shape(reader, tensor_name):
    """Get original shape from GGUF metadata if available"""
    field_key = f"comfy.gguf.orig_shape.{tensor_name}"
    field = reader.get_field(field_key)
    if field is None:
        return None
    if len(field.types) != 2 or field.types[0] != gguf.GGUFValueType.ARRAY or field.types[1] != gguf.GGUFValueType.INT32:
        raise TypeError(f"Bad original shape metadata for {field_key}")
    return torch.Size(tuple(int(field.parts[part_idx][0]) for part_idx in field.data))


def get_field(reader, field_name, field_type):
    """Get a field from GGUF metadata"""
    field = reader.get_field(field_name)
    if field is None:
        return None
    elif field_type == str:
        if len(field.types) != 1 or field.types[0] != gguf.GGUFValueType.STRING:
            raise TypeError(f"Bad type for GGUF {field_name} key")
        return str(field.parts[field.data[-1]], encoding="utf-8")
    elif field_type in [int, float, bool]:
        return field_type(field.parts[field.data[-1]])
    else:
        raise TypeError(f"Unknown field type {field_type}")


def load_gguf_state_dict(path, handle_prefix="model.diffusion_model."):
    """
    Load GGUF file and return state dict with GGMLTensor weights.
    
    Args:
        path: Path to GGUF file
        handle_prefix: Prefix to strip from tensor names
        
    Returns:
        Tuple of (state_dict, architecture_string)
    """
    reader = gguf.GGUFReader(path)
    
    # Check for prefix
    has_prefix = False
    if handle_prefix is not None:
        prefix_len = len(handle_prefix)
        tensor_names = set(tensor.name for tensor in reader.tensors)
        has_prefix = any(s.startswith(handle_prefix) for s in tensor_names)
    
    tensors = []
    for tensor in reader.tensors:
        sd_key = tensor_name = tensor.name
        if has_prefix:
            if not tensor_name.startswith(handle_prefix):
                continue
            sd_key = tensor_name[prefix_len:]
        tensors.append((sd_key, tensor))
    
    # Detect architecture
    arch_str = get_field(reader, "general.architecture", str)
    if arch_str is None:
        # Try to infer from tensor names
        arch_str = "unknown"
        for key, _ in tensors:
            if "qwen" in key.lower():
                arch_str = "qwen_image"
                break
    
    logging.info(f"GGUF Architecture: {arch_str}")
    
    if arch_str not in IMG_ARCH_LIST:
        logging.warning(f"Unknown architecture: {arch_str}")
    
    # Load tensors into state dict
    state_dict = {}
    qtype_counts = {}
    
    for sd_key, tensor in tensors:
        tensor_name = tensor.name
        
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="The given NumPy array is not writable")
            torch_tensor = torch.from_numpy(tensor.data)
        
        shape = get_orig_shape(reader, tensor_name)
        if shape is None:
            shape = torch.Size(tuple(int(v) for v in reversed(tensor.shape)))
        
        # Handle F32/F16 tensors directly
        if tensor.tensor_type in {gguf.GGMLQuantizationType.F32, gguf.GGMLQuantizationType.F16}:
            torch_tensor = torch_tensor.view(*shape)
        
        state_dict[sd_key] = GGMLTensor(
            torch_tensor, 
            tensor_type=tensor.tensor_type, 
            tensor_shape=shape
        )
        
        # Track tensor types
        type_name = getattr(tensor.tensor_type, "name", repr(tensor.tensor_type))
        qtype_counts[type_name] = qtype_counts.get(type_name, 0) + 1
    
    # Log loaded types
    logging.info("GGUF qtypes: " + ", ".join(f"{k} ({v})" for k, v in qtype_counts.items()))
    
    # Mark largest tensor for VRAM estimation
    quant_tensors = {k: v for k, v in state_dict.items() if is_quantized(v)}
    if quant_tensors:
        max_key = max(quant_tensors.keys(), key=lambda k: quant_tensors[k].numel())
        state_dict[max_key].is_largest_weight = True
    
    return state_dict, arch_str


def get_gguf_info(path):
    """
    Get basic info about a GGUF file without fully loading it.
    
    Args:
        path: Path to GGUF file
        
    Returns:
        Dict with model info
    """
    reader = gguf.GGUFReader(path)
    
    arch = get_field(reader, "general.architecture", str)
    name = get_field(reader, "general.name", str)
    
    tensor_count = len(reader.tensors)
    
    # Count quantization types
    qtype_counts = {}
    for tensor in reader.tensors:
        type_name = getattr(tensor.tensor_type, "name", "unknown")
        qtype_counts[type_name] = qtype_counts.get(type_name, 0) + 1
    
    return {
        "architecture": arch,
        "name": name,
        "tensor_count": tensor_count,
        "quantization_types": qtype_counts
    }
