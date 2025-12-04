"""
LumaScale Backend Server
Flask API providing local AI inference endpoints
Refactored to use ModelManager for VRAM efficiency
"""

import os
import sys
import json
import time
import uuid
import traceback
import base64
import io
from PIL import Image
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
import torch

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from model_downloader import ModelDownloader
from model_manager import ModelManager

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Global state
downloader = ModelDownloader()
manager = ModelManager(downloader)

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

@app.route('/status', methods=['GET'])
def get_status():
    """Health check and model availability status"""
    missing_models = downloader.get_missing_models()
    manager_status = manager.get_status()
    
    # Determine which models are "ready" (downloaded)
    models_status = {
        "esrgan": downloader.check_model_exists("upscale"),
        "swinir": downloader.check_model_exists("swinir"),
        "supresdiffgan": downloader.check_model_exists("supresdiffgan"),
        "sdxl": downloader.check_model_exists("sdxl"),
        "qwen": downloader.check_model_exists("qwen")
    }
    
    return jsonify({
        "status": "online",
        "models": models_status,
        "missing_models": missing_models,
        "models_ready": len(missing_models) == 0,
        "active_model": manager_status["active_model"],
        "vram_usage": manager_status["vram_usage"]
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

# Download progress state
download_progress = {
    "active": False,
    "model": "",
    "downloaded": 0,
    "total": 0,
    "percent": 0,
    "speed_mbps": 0,
    "error": None
}

@app.route('/models/download/progress', methods=['GET'])
def get_download_progress():
    """Get current download progress"""
    return jsonify(download_progress)

@app.route('/models/download', methods=['POST'])
def trigger_download():
    """Trigger download of missing models"""
    global download_progress
    
    missing = downloader.get_missing_models()
    if not missing:
        return jsonify({"status": "complete", "message": "All models already downloaded"})
    
    download_progress = {
        "active": True,
        "model": "",
        "downloaded": 0,
        "total": 0,
        "percent": 0,
        "speed_mbps": 0,
        "error": None
    }
    
    import time
    last_time = [time.time()]
    last_bytes = [0]
    
    def progress_callback(model_key, downloaded, total, model_name):
        global download_progress
        now = time.time()
        elapsed = now - last_time[0]
        
        # Calculate speed every 0.5 seconds
        speed = 0
        if elapsed > 0.5:
            bytes_diff = downloaded - last_bytes[0]
            speed = (bytes_diff / elapsed) / (1024 * 1024)  # MB/s
            last_time[0] = now
            last_bytes[0] = downloaded
        else:
            speed = download_progress.get("speed_mbps", 0)
        
        percent = (downloaded / total * 100) if total > 0 else 0
        download_progress = {
            "active": True,
            "model": model_name,
            "downloaded": downloaded,
            "total": total,
            "percent": round(percent, 1),
            "speed_mbps": round(speed, 1),
            "error": None
        }
    
    try:
        success = downloader.download_all_missing(progress_callback)
        download_progress["active"] = False
        
        if success:
            return jsonify({
                "status": "complete",
                "message": "All models downloaded successfully",
                "downloaded": missing
            })
        else:
            download_progress["error"] = "Some models failed to download"
            return jsonify({"status": "error", "message": "Some models failed to download"}), 500
    except Exception as e:
        download_progress["active"] = False
        download_progress["error"] = str(e)
        return jsonify({"status": "error", "message": str(e)}), 500

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
    Upscaling endpoint with progress tracking
    Supports: ESRGAN, SwinIR, SupResDiffGAN
    """
    try:
        data = request.get_json()
        base64_image = data.get('image')
        scale_factor = data.get('scale_factor', 4)
        upscaler_name = data.get('upscaler', 'RealESRGAN x4plus')
        
        # Use client-provided ID or generate new one
        request_id = data.get('request_id', str(uuid.uuid4()))
        
        if not base64_image:
            return jsonify({"error": "No image data"}), 400
        
        # Map UI name to model key
        model_key = "esrgan" # default
        if upscaler_name == 'SwinIR-L 4x':
            model_key = "swinir"
        elif upscaler_name == 'SupResDiffGAN 4x':
            model_key = "supresdiffgan"
            
        update_progress(request_id, f"⏳ Loading {upscaler_name}...", 0)
        
        # Get Engine (Lazy Load)
        try:
            active_engine = manager.get_model(model_key)
        except FileNotFoundError:
             return jsonify({
                 "error": f"Model {upscaler_name} not found",
                 "hint": "Please download models via Settings"
             }), 503
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": f"Failed to load model: {str(e)}"}), 500

        # Progress callback
        def progress_cb(progress):
            step = f"🔧 Upscaling {scale_factor}x [{upscaler_name}]"
            update_progress(request_id, step, progress)
        
        update_progress(request_id, f"🔧 Starting {upscaler_name}...", 5)
        start_time = time.time()
        
        # Call engine
        result_base64 = active_engine.upscale_from_base64(
            base64_image, 
            scale_factor,
            use_tiling=data.get('use_tiling', True),
            progress_callback=progress_cb
        )
        
        processing_time = time.time() - start_time
        
        # Get dimensions
        input_data = base64.b64decode(base64_image)
        input_image = Image.open(io.BytesIO(input_data))
        out_w, out_h = active_engine.get_output_dimensions(
            input_image.width, input_image.height, scale_factor
        )
        
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
    """SDXL img2img enhancement endpoint"""
    try:
        data = request.get_json()
        base64_image = data.get('image')
        modules = data.get('modules', {})
        scale_factor = data.get('scale_factor', 2)
        prompt = data.get('prompt', '')
        
        if not base64_image: return jsonify({"error": "Missing image"}), 400
        
        # Use client-provided ID or generate new one
        request_id = data.get('request_id', str(uuid.uuid4()))
        update_progress(request_id, "🎨 Starting Enhancement...", 0)
        
        # Load SDXL
        try:
            sdxl_engine = manager.get_model("sdxl")
        except Exception as e:
            return jsonify({"error": f"Failed to load SDXL: {str(e)}"}), 503
            
        start_time = time.time()
        
        # SDXL Progress Callback
        def sdxl_progress(p):
            # Map 0-100 to 0-80 range (if upscaling) or 0-100
            if modules.get('upscale', False):
                overall = int(p * 0.8)
            else:
                overall = p
            update_progress(request_id, f"🎨 Enhancing... {p}%", overall)
        
        result_base64 = sdxl_engine.enhance_from_base64(
            base64_image,
            modules=modules,
            prompt=prompt,
            denoising_strength=data.get('denoising_strength', 0.25),
            cfg_scale=data.get('cfg_scale', 7.0),
            steps=25,
            use_tiling=data.get('use_tiling', True),
            progress_callback=sdxl_progress
        )
        
        sdxl_time = time.time() - start_time
        
        # Upscale if requested
        if modules.get('upscale', False):
            print(f"Upscaling result with ESRGAN {scale_factor}x...")
            update_progress(request_id, f"🔍 Upscaling {scale_factor}x...", 80)
            
            # Switch to ESRGAN (will unload SDXL)
            esrgan_engine = manager.get_model("esrgan")
            
            def upscale_progress(p):
                overall = 80 + int(p * 0.2)
                update_progress(request_id, f"🔍 Upscaling... {p}%", overall)
                
            result_base64 = esrgan_engine.upscale_from_base64(
                result_base64, 
                scale_factor,
                use_tiling=data.get('use_tiling', True),
                progress_callback=upscale_progress
            )
            
        update_progress(request_id, "✓ Complete!", 100, "complete")
        
        processing_time = time.time() - start_time
        
        # Get dimensions
        result_data = base64.b64decode(result_base64)
        result_image = Image.open(io.BytesIO(result_data))
        
        return jsonify({
            "request_id": request_id,
            "image": result_base64,
            "width": result_image.width,
            "height": result_image.height,
            "processing_time": round(processing_time, 2),
            "sdxl_time": round(sdxl_time, 2)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500

@app.route('/make-real', methods=['POST'])
def make_real():
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({"error": "No image provided"}), 400

        # Decode image
        image_data = base64.b64decode(data['image'])
        input_image = Image.open(io.BytesIO(image_data)).convert('RGB')
        
        # Use client-provided ID or generate new one
        request_id = data.get('request_id', str(uuid.uuid4()))
        # 1. Get Prompt from Qwen
        print("Phase 1: Analyzing image with Qwen...")
        update_progress(request_id, "🧠 Analyzing image...", 5)
        
        prompt = data.get('prompt', '')
        
        # Only query Qwen if prompt is empty or default
        if not prompt or prompt == 'convert to photorealistic, raw photo, dslr quality':
            try:
                qwen_engine = manager.get_model("qwen")
                prompt = qwen_engine.generate_prompt(input_image)
                print(f"Generated Prompt: {prompt}")
                
                # Force cleanup of Qwen
                print("Unloading Qwen to free VRAM...")
                manager.unload_all()
                import gc
                gc.collect()
                torch.cuda.empty_cache()
                
            except FileNotFoundError:
                 return jsonify({
                     "error": "Qwen model not found",
                     "hint": "Please download Qwen via Settings"
                 }), 503
            except Exception as e:
                print(f"Qwen failed: {e}")
                prompt = "photorealistic, 8k, highly detailed, raw photo, dslr quality"
                # Even if failed, try to cleanup
                manager.unload_all()
                import gc
                gc.collect()
                torch.cuda.empty_cache()

        update_progress(request_id, "🎨 Enhancing details...", 20)

        # 2. Enhance with SDXL
        print("Phase 2: Enhancing with SDXL...")
        try:
            sdxl_engine = manager.get_model("sdxl") # Unloads Qwen
            
            # Prepare modules
            modules = {
                'hires_fix': True,
                'skin_texture': True, # Default for Make it Real
                'upscale': False # We handle upscale separately if needed
            }
            
            # Progress callback for SDXL
            def sdxl_progress(p):
                # Map 0-100 to 20-80 range
                overall = 20 + int(p * 0.6)
                update_progress(request_id, f"🎨 Enhancing... {p}%", overall)
            
            # Use specific settings for Make it Real
            result_image = sdxl_engine.enhance_image(
                input_image,
                modules=modules,
                prompt=prompt,
                denoising_strength=0.65, # Strong style transfer
                cfg_scale=7.5,           # Strong prompt adherence
                steps=30,
                use_tiling=data.get('use_tiling', True),
                progress_callback=sdxl_progress
            )
            
            # 3. Upscale if needed
            scale_factor = data.get('scale_factor', 1)
            final_b64 = ""
            
            if scale_factor > 1:
                print(f"Phase 3: Upscaling {scale_factor}x...")
                update_progress(request_id, f"🔍 Upscaling {scale_factor}x...", 80)
                
                esrgan_engine = manager.get_model("esrgan") # Unloads SDXL
                
                buffer = io.BytesIO()
                result_image.save(buffer, format="PNG")
                res_b64 = base64.b64encode(buffer.getvalue()).decode()
                
                def upscale_progress(p):
                    # Map 0-100 to 80-95 range
                    overall = 80 + int(p * 0.15)
                    update_progress(request_id, f"🔍 Upscaling... {p}%", overall)
                
                final_b64 = esrgan_engine.upscale_from_base64(
                    res_b64, 
                    scale_factor,
                    use_tiling=data.get('use_tiling', True),
                    progress_callback=upscale_progress
                )
                
                update_progress(request_id, "✓ Complete!", 100, "complete")
                
                return jsonify({
                    "request_id": request_id,
                    "image": final_b64,
                    "prompt": prompt,
                    "width": input_image.width * scale_factor,
                    "height": input_image.height * scale_factor
                })
            
            # Return SDXL result
            buffer = io.BytesIO()
            result_image.save(buffer, format="PNG")
            final_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            update_progress(request_id, "✓ Complete!", 100, "complete")
            
            return jsonify({
                "request_id": request_id,
                "image": final_b64,
                "prompt": prompt,
                "width": result_image.width,
                "height": result_image.height
            })

        except Exception as e:
            raise e

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500

@app.route('/system/stats', methods=['GET'])
def system_stats():
    """Get system stats (VRAM)"""
    return jsonify(manager.get_status())

def startup_sequence():
    """Initialize server"""
    print("\n" + "="*60)
    print("Upscale Engine CC Backend Server - Startup")
    print("="*60)
    
    missing = downloader.get_missing_models()
    if missing:
        print(f"\n[!] Missing models: {missing}")
    else:
        print("\n[OK] All models present (Lazy loading enabled)")
    
    print("\n" + "="*60)
    print("Server ready on http://localhost:5555")
    print("="*60 + "\n")

if __name__ == '__main__':
    startup_sequence()
    app.run(host='0.0.0.0', port=5555, debug=True, use_reloader=False)
