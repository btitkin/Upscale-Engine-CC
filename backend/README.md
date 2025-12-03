# LumaScale Backend

Python Flask server providing local AI inference for LumaScale.

## Setup

1. **Install Python 3.10+** (if not already installed)

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Download models** (automatic on first run, or manual):
   ```bash
   python model_downloader.py
   ```

4. **Start server:**
   ```bash
   python server.py
   ```

   Server will start on `http://localhost:5555`

## API Endpoints

### `GET /status`
Health check and model availability
```json
{
  "status": "online",
  "models": {
    "esrgan": true,
    "sdxl": false,
    "qwen": false
  },
  "missing_models": ["sdxl", "qwen"],
  "models_ready": false
}
```

### `GET /models/status`
Detailed model information

### `POST /models/download`
Trigger download of missing models (blocking operation)

### `POST /upscale`
ESRGAN upscaling endpoint

**Request:**
```json
{
  "image": "base64_encoded_image_data",
  "scale_factor": 4
}
```

**Response:**
```json
{
  "image": "base64_encoded_result",
  "width": 2048,
  "height": 2048,
  "processing_time": 3.2
}
```

### `POST /enhance` *(Coming soon - Phase 2)*
SDXL img2img enhancement with HiresFix and Skin Texture modules

### `POST /make-real` *(Coming soon - Phase 3)*
Qwen multimodal image editing for anime→photorealistic conversion

## Model Files

Models are downloaded to `../models/` directory:

- `4x-UltraSharp.pth` (67MB) - ESRGAN upscaler
- `Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors` (7.1GB) - SDXL checkpoint
- `Qwen-Image-Edit-2509-Q4_K_M.gguf` (13.1GB) - Multimodal GGUF model

## Development

### Testing ESRGAN Engine
```bash
cd engines
python esrgan_engine.py
```

### Testing Model Downloader
```bash
python model_downloader.py
```

## Performance

- **GPU (CUDA)**: Automatic detection, uses FP16 for speed
- **CPU Fallback**: Available but 10-50× slower
- **VRAM Requirements**: 
  - ESRGAN only: ~2GB
  - SDXL: ~8GB
  - Qwen: ~6GB

## Troubleshooting

**"Model not found" error:**
- Run `python model_downloader.py` to download models manually
- Check that `../models/` directory exists

**CUDA out of memory:**
- Reduce image size
- Close other GPU applications
- Use CPU mode (slower)

**Import errors:**
- Ensure all requirements installed: `pip install -r requirements.txt`
- Check Python version is 3.10+
