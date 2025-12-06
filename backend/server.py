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
import threading
from queue import Queue, Empty
from PIL import Image
from pathlib import Path
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import torch

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from model_downloader import ModelDownloader
from model_manager import ModelManager
from comfyui_executor import make_it_real as comfyui_make_it_real, get_executor
from video_service import is_video_file, get_video_info, extract_frames_to_base64

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Global state
downloader = ModelDownloader()
manager = ModelManager(downloader)

# Progress tracking (per request)
progress_store = {}

# Live preview store (per request) - holds base64 preview images
preview_store = {}  # {request_id: Queue()}

def update_progress(request_id: str, step: str, progress: int, status: str = "processing"):
    """Update progress for a specific request"""
    progress_store[request_id] = {
        "status": status,
        "step": step,
        "progress": progress,
        "timestamp": time.time()
    }
    print(f"[Progress {request_id[:8]}] {step} - {progress}%")

def send_preview(request_id: str, image_base64: str, step: int = 0):
    """Send preview image to SSE stream"""
    if request_id not in preview_store:
        preview_store[request_id] = Queue()
    preview_store[request_id].put({
        "image": image_base64,
        "step": step,
        "timestamp": time.time()
    })
    print(f"[Preview {request_id[:8]}] Step {step} - sent preview")

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
        "qwen": downloader.check_model_exists("qwen"),
        "gfpgan": downloader.check_model_exists("gfpgan")
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

@app.route('/preview/<request_id>', methods=['GET'])
def stream_preview(request_id):
    """
    SSE endpoint for streaming live preview images during processing.
    Sends base64 images as they become available.
    """
    def generate():
        # Initialize queue for this request if not exists
        if request_id not in preview_store:
            preview_store[request_id] = Queue()
        
        queue = preview_store[request_id]
        timeout_count = 0
        max_timeouts = 600  # 5 minutes max (600 * 0.5s)
        
        while timeout_count < max_timeouts:
            try:
                # Wait for preview with 0.5s timeout
                preview_data = queue.get(timeout=0.5)
                
                # Send SSE event
                event_data = json.dumps(preview_data)
                yield f"data: {event_data}\n\n"
                
                timeout_count = 0  # Reset on successful data
                
            except Empty:
                timeout_count += 1
                # Send keepalive every 10 seconds
                if timeout_count % 20 == 0:
                    yield f": keepalive\n\n"
                    
                # Check if processing is done
                if request_id in progress_store:
                    status = progress_store[request_id].get("status", "")
                    if status in ["done", "error"]:
                        # Send final event
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        break
        
        # Cleanup - prevent memory leaks
        if request_id in preview_store:
            del preview_store[request_id]
        if request_id in progress_store:
            del progress_store[request_id]
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

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
        
        # Preview callback for live preview
        def preview_cb(image_b64, step):
            send_preview(request_id, image_b64, step)
        
        result_base64 = sdxl_engine.enhance_from_base64(
            base64_image,
            modules=modules,
            prompt=prompt,
            denoising_strength=data.get('denoising_strength', 0.25),
            cfg_scale=data.get('cfg_scale', 7.0),
            steps=25,
            use_tiling=data.get('use_tiling', True),
            progress_callback=sdxl_progress,
            preview_callback=preview_cb
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

@app.route('/face-enhance', methods=['POST'])
def face_enhance():
    """
    Face Enhancement endpoint using GFPGAN
    Restores and enhances faces in images
    """
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({"error": "No image provided"}), 400
        
        # Decode image
        image_data = base64.b64decode(data['image'])
        input_image = Image.open(io.BytesIO(image_data)).convert('RGB')
        
        # Use client-provided ID or generate new one
        request_id = data.get('request_id', str(uuid.uuid4()))
        
        print(f"[Face Enhance] Request {request_id[:8]}")
        
        update_progress(request_id, "🔄 Loading GFPGAN...", 10)
        
        start_time = time.time()
        
        try:
            gfpgan_engine = manager.get_model("gfpgan")
            
            if not gfpgan_engine.is_available():
                return jsonify({
                    "error": "GFPGAN not available",
                    "hint": "Model may not be downloaded yet"
                }), 503
            
            def progress_cb(p):
                update_progress(request_id, f"✨ Enhancing faces... {p}%", 10 + int(p * 0.8))
            
            update_progress(request_id, "✨ Enhancing faces...", 20)
            
            result_image = gfpgan_engine.enhance_face(
                input_image,
                upscale=data.get('upscale', 2),
                only_center_face=data.get('only_center_face', False),
                progress_callback=progress_cb
            )
            
            if result_image is None:
                return jsonify({
                    "error": "Face enhancement failed",
                    "hint": "No faces detected or processing error"
                }), 500
            
            processing_time = time.time() - start_time
            
            # Convert result to base64
            buffer = io.BytesIO()
            result_image.save(buffer, format="PNG")
            result_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            update_progress(request_id, "✅ Done!", 100, "done")
            
            return jsonify({
                "image": result_b64,
                "width": result_image.width,
                "height": result_image.height,
                "processing_time": round(processing_time, 2)
            })
            
        except FileNotFoundError:
            return jsonify({
                "error": "GFPGAN model not found",
                "hint": "Please download models first"
            }), 503
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/inpaint', methods=['POST'])
def inpaint():
    """
    Inpainting endpoint - mask-based image editing with SDXL
    
    Expects JSON:
        - image: base64 image
        - mask: base64 mask (white = inpaint, black = keep)
        - prompt: what to generate in masked areas
        - strength: 0.3-1.0 (default 0.75)
        - request_id: optional client ID
    
    Returns:
        - image: base64 result
        - width, height
        - processing_time
    """
    try:
        data = request.json
        if not data or 'image' not in data or 'mask' not in data:
            return jsonify({"error": "Image and mask required"}), 400
        
        if not data.get('prompt'):
            return jsonify({"error": "Prompt required"}), 400
        
        request_id = data.get('request_id', str(uuid.uuid4()))
        strength = float(data.get('strength', 0.75))
        
        # Clamp strength
        strength = max(0.3, min(1.0, strength))
        
        print(f"[Inpaint] Request {request_id[:8]}, strength={strength}")
        
        update_progress(request_id, "🔄 Loading inpaint model...", 5)
        
        start_time = time.time()
        
        try:
            inpaint_engine = manager.get_model("inpaint")
            
            if not inpaint_engine.is_available():
                return jsonify({
                    "error": "SDXL Inpaint not available",
                    "hint": "diffusers package may not be installed"
                }), 503
            
            def progress_cb(step, total):
                pct = 10 + int((step / total) * 80)
                update_progress(request_id, f"🎨 Inpainting... {step}/{total}", pct)
            
            update_progress(request_id, "🎨 Starting inpainting...", 10)
            
            result_b64 = inpaint_engine.inpaint_from_base64(
                image_b64=data['image'],
                mask_b64=data['mask'],
                prompt=data['prompt'],
                strength=strength,
                progress_callback=progress_cb
            )
            
            processing_time = time.time() - start_time
            
            # Get result dimensions
            result_data = base64.b64decode(result_b64)
            result_image = Image.open(io.BytesIO(result_data))
            
            update_progress(request_id, "✅ Inpainting complete!", 100, "done")
            
            return jsonify({
                "image": result_b64,
                "width": result_image.width,
                "height": result_image.height,
                "processing_time": round(processing_time, 2)
            })
            
        except Exception as e:
            traceback.print_exc()
            return jsonify({
                "error": f"Inpainting failed: {str(e)}",
                "type": type(e).__name__
            }), 500
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500

@app.route('/make-real', methods=['POST'])
def make_real():
    """Make it Real - Convert image using ComfyUI + Qwen Image Edit"""
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({"error": "No image provided"}), 400

        # Decode image
        image_data = base64.b64decode(data['image'])
        input_image = Image.open(io.BytesIO(image_data)).convert('RGB')
        
        # Use client-provided ID or generate new one
        request_id = data.get('request_id', str(uuid.uuid4()))
        
        # Get prompt (custom or default)
        prompt = data.get('prompt', 'convert to photorealistic, raw photo, dslr quality')
        
        print(f"[Make it Real] Request {request_id[:8]} - Prompt: {prompt[:50]}...")
        
        update_progress(request_id, "🚀 Starting ComfyUI...", 5)
        
        # Progress callback for ComfyUI
        def comfyui_progress(progress: int, status: str):
            update_progress(request_id, f"🎨 {status}", progress)
        
        # Preview callback for live preview
        def preview_cb(image_b64: str, step: int):
            send_preview(request_id, image_b64, step)
        
        # Execute via ComfyUI
        try:
            result_image = comfyui_make_it_real(
                input_image,
                prompt=prompt,
                progress_callback=comfyui_progress,
                preview_callback=preview_cb
            )
            
            if result_image is None:
                return jsonify({
                    "error": "ComfyUI processing failed",
                    "hint": "Check ComfyUI logs for details"
                }), 500
            
            # Convert result to base64
            buffer = io.BytesIO()
            result_image.save(buffer, format="PNG")
            result_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Handle upscaling if requested
            scale_factor = data.get('scale_factor', 1)
            final_b64 = result_b64
            
            if scale_factor > 1:
                print(f"[Make it Real] Upscaling {scale_factor}x...")
                update_progress(request_id, f"🔍 Upscaling {scale_factor}x...", 85)
                
                try:
                    esrgan_engine = manager.get_model("esrgan")
                    
                    def upscale_progress(p):
                        overall = 85 + int(p * 0.1)
                        update_progress(request_id, f"🔍 Upscaling... {p}%", overall)
                    
                    final_b64 = esrgan_engine.upscale_from_base64(
                        result_b64,
                        scale_factor,
                        use_tiling=data.get('use_tiling', True),
                        progress_callback=upscale_progress
                    )
                except Exception as e:
                    print(f"[Make it Real] Upscale failed: {e}, returning non-upscaled result")
                    final_b64 = result_b64
            
            update_progress(request_id, "✓ Complete!", 100, "complete")
            
            # Decode final to get dimensions
            final_bytes = base64.b64decode(final_b64)
            final_image = Image.open(io.BytesIO(final_bytes))
            
            return jsonify({
                "request_id": request_id,
                "image": final_b64,
                "prompt": prompt,
                "width": final_image.width,
                "height": final_image.height
            })
            
        except Exception as e:
            print(f"[Make it Real] ComfyUI error: {e}")
            traceback.print_exc()
            return jsonify({
                "error": str(e),
                "type": type(e).__name__,
                "hint": "Make sure ComfyUI is properly installed"
            }), 500

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500

@app.route('/system/stats', methods=['GET'])
def system_stats():
    """Get system stats (VRAM)"""
    return jsonify(manager.get_status())

@app.route('/comfyui/start', methods=['POST'])
def comfyui_start():
    """Start ComfyUI server if not running"""
    try:
        executor = get_executor()
        
        if executor.is_server_running():
            return jsonify({
                "status": "already_running",
                "message": "ComfyUI is already running"
            })
        
        print("[ComfyUI] Starting server...")
        success = executor.start_server(timeout=120)
        
        if success:
            return jsonify({
                "status": "started",
                "message": "ComfyUI started successfully"
            })
        else:
            return jsonify({
                "error": "Failed to start ComfyUI",
                "hint": "Check if ComfyUI is installed correctly"
            }), 500
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/comfyui/status', methods=['GET'])
def comfyui_status():
    """Check ComfyUI server status"""
    try:
        executor = get_executor()
        running = executor.is_server_running()
        
        return jsonify({
            "running": running,
            "url": f"http://127.0.0.1:8188" if running else None
        })
    except Exception as e:
        return jsonify({"running": False, "error": str(e)})

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


@app.route('/video/info', methods=['POST'])
def video_info():
    """Get video metadata"""
    try:
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        video_file = request.files['video']
        
        # Save temporarily
        temp_path = Path(__file__).parent / "temp_video"
        temp_path.mkdir(exist_ok=True)
        temp_file = temp_path / video_file.filename
        video_file.save(str(temp_file))
        
        try:
            info = get_video_info(str(temp_file))
            if info is None:
                return jsonify({"error": "Cannot read video"}), 400
            return jsonify(info)
        finally:
            temp_file.unlink(missing_ok=True)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/video/extract', methods=['POST'])
def video_extract_frames():
    """
    Extract frames from video file
    
    Form data:
        - video: Video file
        - interval: Seconds between frames (default 1.0)
        - max_frames: Maximum frames to extract (default 100)
    
    Returns:
        JSON with list of extracted frames as base64
    """
    try:
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        video_file = request.files['video']
        interval = float(request.form.get('interval', 1.0))
        max_frames = int(request.form.get('max_frames', 100))
        
        # Limit max frames
        max_frames = min(max_frames, 500)
        
        # Save video temporarily
        temp_path = Path(__file__).parent / "temp_video"
        temp_path.mkdir(exist_ok=True)
        temp_file = temp_path / f"extract_{uuid.uuid4().hex[:8]}_{video_file.filename}"
        video_file.save(str(temp_file))
        
        try:
            print(f"[Video] Extracting frames from {video_file.filename}, interval={interval}s, max={max_frames}")
            
            frames = extract_frames_to_base64(
                str(temp_file),
                interval=interval,
                max_frames=max_frames
            )
            
            print(f"[Video] Extracted {len(frames)} frames")
            
            return jsonify({
                "frames": frames,
                "count": len(frames),
                "interval": interval
            })
            
        finally:
            temp_file.unlink(missing_ok=True)
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    startup_sequence()
    # Auto-install ComfyUI and custom nodes if missing
    try:
        from install_dependencies import check_and_install_dependencies
        check_and_install_dependencies()
    except Exception as e:
        print(f"[Startup] Warning: Failed to check dependencies: {e}")

    # Start the server
    PORT = 5555 # Default port
    print(f"Starting server on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT, threaded=True, use_reloader=False)
