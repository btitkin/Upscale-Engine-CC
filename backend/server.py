"""
LumaScale Backend Server
Flask API providing local AI inference endpoints
"""

import os
import sys
import json
import time
import uuid
import traceback
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from model_downloader import ModelDownloader
from engines.esrgan_engine import ESRGANEngine
from engines.sdxl_engine import SDXLEngine


app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Global state
models_dir = Path(__file__).parent.parent / "models"  # Project root models/
downloader = ModelDownloader()  # Will use same path automatically
esrgan_engine = None
sdxl_engine = None

# Model loading status
model_status = {
    "esrgan_loaded": False,
    "sdxl_loaded": False,
    "qwen_loaded": False,
    "loading_error": None
}

# Progress tracking (per request)
progress_store = {}

def update_progress(request_id: str, step: str, progress: int, status: str = "processing"):
    """Update progress for a specific request"""
    progress_store[request_id] = {
        "status": status,
        "step": step,
        "progress": progress,
        "timestamp": time.time()
    }
    print(f"[Progress {request_id[:8]}] {step} - {progress}%")


def initialize_esrgan():
    """Initialize ESRGAN engine if model available"""
    global esrgan_engine, model_status
    
    try:
        model_path = downloader.get_model_path("upscale")
        if model_path is None:
            model_status["loading_error"] = "ESRGAN model not downloaded"
            return False
        
        print(f"Loading ESRGAN from {model_path}...")
        
        # Force CUDA if available
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        print(f"[SERVER DEBUG] torch.cuda.is_available() = {torch.cuda.is_available()}")
        print(f"[SERVER DEBUG] Selected device: {device}")
        print(f"[SERVER DEBUG] Calling ESRGANEngine(device='{device}')")
        
        esrgan_engine = ESRGANEngine(str(model_path), device=device)
        model_status["esrgan_loaded"] = True
        print("[OK] ESRGAN engine ready")
        return True
        
    except Exception as e:
        error_msg = f"ESRGAN load error: {str(e)}"
        print(error_msg)
        model_status["loading_error"] = error_msg
        return False


def initialize_sdxl():
    """Initialize SDXL engine if model available"""
    global sdxl_engine, model_status
    
    try:
        model_path = downloader.get_model_path("sdxl")
        if model_path is None:
            model_status["loading_error"] = "SDXL model not downloaded"
            return False
        
        print(f"Loading SDXL from {model_path}...")
        print("[!] This may take 1-2 minutes on first load...")
        sdxl_engine = SDXLEngine(str(model_path))
        model_status["sdxl_loaded"] = True
        print("[OK] SDXL engine ready")
        return True
        
    except Exception as e:
        error_msg = f"SDXL load error: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        model_status["loading_error"] = error_msg
        return False


@app.route('/status', methods=['GET'])
def get_status():
    """Health check and model availability status"""
    missing_models = downloader.get_missing_models()
    
    return jsonify({
        "status": "online",
        "models": {
            "esrgan": model_status["esrgan_loaded"],
            "sdxl": model_status["sdxl_loaded"],
            "qwen": model_status["qwen_loaded"]
        },
        "missing_models": missing_models,
        "models_ready": len(missing_models) == 0,
        "error": model_status["loading_error"]
    })


@app.route('/models/status', methods=['GET'])
def get_models_status():
    """Detailed model download status"""
    status = {}
    
    for model_key, model_info in downloader.manifest.items():
        exists = downloader.check_model_exists(model_key)
        status[model_key] = {
            "name": model_info["name"],
            "filename": model_info["filename"],
            "size": model_info["size"],
            "downloaded": exists
        }
    
    missing = downloader.get_missing_models()
    
    return jsonify({
        "models": status,
        "all_ready": len(missing) == 0,
        "missing": missing
    })


@app.route('/models/download', methods=['POST'])
def trigger_download():
    """
    Trigger download of missing models
    Note: This is a blocking operation. For production, should use background tasks.
    """
    missing = downloader.get_missing_models()
    
    if not missing:
        return jsonify({"status": "complete", "message": "All models already downloaded"})
    
    try:
        # Download all missing models
        success = downloader.download_all_missing()
        
        if success:
            # Try to initialize engines with newly downloaded models
            if "upscale" in missing:
                initialize_esrgan()
            if "sdxl" in missing:
                initialize_sdxl()
            
            return jsonify({
                "status": "complete",
                "message": "All models downloaded successfully",
                "downloaded": missing
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Some models failed to download"
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/progress/<request_id>', methods=['GET'])
def get_progress(request_id):
    """Get current progress for a request"""
    if request_id in progress_store:
        return jsonify(progress_store[request_id])
    else:
        return jsonify({"status": "unknown", "step": "Not found", "progress": 0}), 404


@app.route('/upscale', methods=['POST'])
def upscale_image():
    """
    ESRGAN upscaling endpoint with progress tracking
    
    Request JSON:
    {
        "image": "base64_encoded_image",
        "scale_factor": 2 or 4 (optional, default 4),
        "request_id": "unique_id" (optional)
    }
    """
    if esrgan_engine is None:
        return jsonify({
            "error": "ESRGAN engine not loaded",
            "hint": "Check /status endpoint"
        }), 503
    
    try:
        data = request.get_json()
        base64_image = data.get('image')
        scale_factor = data.get('scale_factor', 4)
        use_tiling = data.get('use_tiling', True)
        
        # Generate UUID for this request
        request_id = str(uuid.uuid4())
        
        if not base64_image:
            return jsonify({"error": "No image data"}), 400
        
        # Tiling status message
        tiling_msg = "Tiling: ON" if use_tiling else "Tiling: OFF"
        
        # Progress callback
        def progress_cb(progress):
            step = f"🔧 Upscaling {scale_factor}x [{tiling_msg}]"
            update_progress(request_id, step, progress)
        
        update_progress(request_id, "🔧 Initializing upscale...", 0)
        start_time = time.time()
        
        result_base64 = esrgan_engine.upscale_from_base64(
            base64_image, 
            scale_factor,
            use_tiling=use_tiling,
            progress_callback=progress_cb
        )
        
        processing_time = time.time() - start_time
        
        # Get dimensions
        from PIL import Image
        import io
        import base64 as b64
        
        input_data = b64.b64decode(base64_image)
        input_image = Image.open(io.BytesIO(input_data))
        out_w, out_h = esrgan_engine.get_output_dimensions(
            input_image.width, input_image.height, scale_factor
        )
        
        # Mark complete and cleanup
        update_progress(request_id, "✓ Upscale complete!", 100, "complete")
        
        return jsonify({
            "request_id": request_id,
            "image": result_base64,
            "width": out_w,
            "height": out_h,
            "processing_time": round(processing_time, 2)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/enhance', methods=['POST'])

def enhance_image():
    """
    SDXL img2img enhancement endpoint
    
    Request JSON:
    {
        "image": "base64_encoded_image",
        "modules": {
            "skin_texture": bool,
            "hires_fix": bool,
            "upscale": bool
        },
        "scale_factor": 2 or 4 (optional, for upscale)
        "denoising_strength": 0.0-1.0 (optional, default 0.4),
        "cfg_scale": 1.0-20.0 (optional, default 7.0),
        "prompt": "additional prompt" (optional)
    }
    
    Response JSON:
    {
        "image": "base64_encoded_result",
        "width": output_width,
        "height": output_height,
        "processing_time": seconds
    }
    """
    if sdxl_engine is None:
        return jsonify({
            "error": "SDXL engine not loaded",
            "hint": "Model may not be downloaded. Check /status endpoint."
        }), 503
    
    try:
        data = request.get_json()
        
        if 'image' not in data:
            return jsonify({"error": "Missing 'image' field"}), 400
        
        if 'modules' not in data:
            return jsonify({"error": "Missing 'modules' field"}), 400
        
        base64_image = data['image']
        modules = data['modules']
        scale_factor = data.get('scale_factor', 2)
        denoising_strength = data.get('denoising_strength', 0.25)  # Lower for preservation
        cfg_scale = data.get('cfg_scale', 7.0)
        prompt = data.get('prompt', '')
        
        # Process with SDXL
        start_time = time.time()
        
        result_base64 = sdxl_engine.enhance_from_base64(
            base64_image,
            modules=modules,
            prompt=prompt,
            denoising_strength=denoising_strength,
            cfg_scale=cfg_scale,
            steps=25
        )
        
        sdxl_time = time.time() - start_time
        
        # If upscale module enabled, run ESRGAN after SDXL
        if modules.get('upscale', False) and esrgan_engine is not None:
            print(f"Upscaling result with ESRGAN {scale_factor}x...")
            result_base64 = esrgan_engine.upscale_from_base64(result_base64, scale_factor)
        
        processing_time = time.time() - start_time
        
        # Get dimensions
        from PIL import Image
        import io
        import base64 as b64
        
        result_data = b64.b64decode(result_base64)
        result_image = Image.open(io.BytesIO(result_data))
        
        return jsonify({
            "image": result_base64,
            "width": result_image.width,
            "height": result_image.height,
            "processing_time": round(processing_time, 2),
            "sdxl_time": round(sdxl_time, 2)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "type": type(e).__name__
        }), 500


@app.route('/make-real', methods=['POST'])
def make_real():
    """
    Qwen multimodal "Make it Real" (Phase 3 - not yet implemented)
    """
    return jsonify({
        "error": "Qwen 'Make it Real' not yet implemented",
        "status": "coming_soon"
    }), 501


def startup_sequence():
    """Initialize models on server startup"""
    print("\n" + "="*60)
    print("Upscale Engine CC Backend Server - Startup")
    print("="*60)
    
    # Check for missing models
    missing = downloader.get_missing_models()
    
    if missing:
        print(f"\n[!] Missing models: {missing}")
        print("Frontend will need to trigger download via /models/download")
    else:
        print("\n[OK] All models present")
        
        # Try to load ESRGAN
        if "upscale" not in missing:
            initialize_esrgan()
        
        # Try to load SDXL (Phase 2)
        if "sdxl" not in missing:
            initialize_sdxl()
    
    print("\n" + "="*60)
    print("Server ready on http://localhost:5555")
    print("="*60 + "\n")


if __name__ == '__main__':
    # Run startup checks
    startup_sequence()
    
    # Start Flask server
    app.run(
        host='0.0.0.0',
        port=5555,
        debug=True,
        use_reloader=False  # Disable reloader to avoid double initialization
    )
