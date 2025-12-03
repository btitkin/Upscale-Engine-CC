# LumaScale - Desktop Application

Premium AI Image Upscaler with local inference. Standalone desktop application built with Electron.

---

## ⚡ For Users - Installation

### Download & Install:
1. Download `LumaScale-Setup.exe` from releases
2. Run installer
3. Launch LumaScale from desktop icon or Start menu
4. On first run, app will download AI models automatically

**That's it!** No Python, Node.js, or manual setup required for end users.

---

## 🛠️ For Developers - Building from Source

### Prerequisites:
- Python 3.10+
- Node.js 18+
- Git

### Setup:

```bash
# Clone repository
git clone <repo-url>
cd lumascaleproject

# Install Node.js dependencies
npm install

# Setup Python backend
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
cd ..
```

### Development Mode:

```bash
# Run Electron app in development
npm run electron:dev
```

This will:
- Start Vite dev server (http://localhost:5173)
- Launch Electron window
- Auto-start Python backend
- Enable hot-reload for frontend changes

### Building for Production:

```bash
# Build Windows installer
npm run electron:build:win
```

Output: `release/LumaScale-Setup-1.0.0.exe`

### Other Build Commands:

```bash
# Build without creating installer (faster for testing)
npm run package

# Build for all platforms
npm run dist
```

---

## 🎯 Features

- ✅ **4x ESRGAN Upscaling** - Ultra-sharp image enhancement
- ✅ **Skin Texture Enhancement** - SDXL-based detail recovery
- ✅ **HiresFix** - Two-pass generation for maximum quality  
- ⚠️ **Make it Real** - Qwen multimodal (template, needs testing)

---

## 📦 AI Models

Models are auto-downloaded on first use to:
- **Windows**: `%APPDATA%/lumascale/models/`
- **Development**: `./models/`

### Models:
| Model | Size | Purpose |
|-------|------|---------|
| 4x-UltraSharp | 67 MB | ESRGAN upscaling |
| Juggernaut XL 9.0 | 7.1 GB | Skin Texture, HiresFix |
| Qwen Image Edit 2509 | 13.1 GB | Make it Real (optional) |

---

## 🏗️ Architecture

```
LumaScale Desktop
├── Electron (Main Process)
│   ├── Window Management
│   ├── Backend Lifecycle
│   └── IPC Communication
├── React Frontend (Renderer)
│   ├── Vite Dev Server (dev)
│   └── Static Build (prod)
└── Python Backend
    ├── Flask REST API
    ├── ESRGAN Engine
    ├── SDXL Engine
    └── Qwen Engine
```

---

## 🔧 Troubleshooting

### Backend won't start
- Check `%APPDATA%/lumascale/logs/backend.log`
- Ensure Python 3.10+ installed (for development)
- Reinstall dependencies: `cd backend && pip install -r requirements.txt`

### Models not downloading
- Check internet connection
- Verify disk space (~20 GB for all models)
- Check HuggingFace accessibility

### Build fails
- Clear cache: `rm -rf node_modules dist release`
- Reinstall: `npm install`
- Check Node.js version: `node --version` (need 18+)

---

## 📄 License

[Add your license here]

---

## 🤝 Contributing

Contributions welcome! Please open an issue first to discuss changes.

---

**Made with ❤️ and AI**
