"""
ComfyUI Workflow Executor for Qwen Image Edit
Executes the Make it Real workflow via ComfyUI API
"""
import os
import sys
import json
import time
import uuid
import base64
import logging
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import requests
from PIL import Image
import io

# ComfyUI settings
COMFYUI_HOST = "127.0.0.1"
COMFYUI_PORT = 8188
COMFYUI_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
COMFYUI_DIR = PROJECT_DIR / "comfyui"
WORKFLOW_DIR = PROJECT_DIR / "models" / "workflow"
WORKFLOW_NORMAL = WORKFLOW_DIR / "MakeItReal_Normal.json"
WORKFLOW_HIRESFIX = WORKFLOW_DIR / "MakeItReal_HiresFix.json"
WORKFLOW_SDXL_TILED_UPSCALE = WORKFLOW_DIR / "SDXL_TiledUpscale.json"


class ComfyUIExecutor:
    """Executes workflows via ComfyUI API"""
    
    def __init__(self):
        self.client_id = str(uuid.uuid4())
        self.process: Optional[subprocess.Popen] = None
        self._workflow_cache = None
        self._node_info_cache = {}  # Cache for node widget info from API
    
    def get_node_info(self, node_type: str) -> Optional[Dict]:
        """Get node info from ComfyUI API, with caching"""
        if node_type in self._node_info_cache:
            return self._node_info_cache[node_type]
        
        try:
            response = requests.get(f"{COMFYUI_URL}/object_info/{node_type}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                info = data.get(node_type, {})
                self._node_info_cache[node_type] = info
                return info
        except Exception as e:
            logging.debug(f"Failed to get node info for {node_type}: {e}")
        
        return None

    
    def is_server_running(self) -> bool:
        """Check if ComfyUI server is already running"""
        try:
            response = requests.get(f"{COMFYUI_URL}/system_stats", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def start_server(self, timeout: int = 120) -> bool:
        """Start ComfyUI server as subprocess"""
        if self.is_server_running():
            logging.info("ComfyUI already running")
            return True
        
        main_py = COMFYUI_DIR / "main.py"
        if not main_py.exists():
            logging.error(f"ComfyUI not found at {main_py}")
            return False
        
        # Find Python executable
        python_exe = sys.executable
        
        cmd = [
            python_exe,
            str(main_py),
            "--listen", COMFYUI_HOST,
            "--port", str(COMFYUI_PORT),
            "--disable-auto-launch",
            "--preview-method", "auto",
            "--lowvram",  # Aggressively unload models from VRAM when not in use
            "--use-pytorch-cross-attention",  # Same as Stability Matrix
        ]
        
        logging.info(f"Starting ComfyUI: {' '.join(cmd)}")
        
        try:
            # Windows: CREATE_NO_WINDOW flag
            creationflags = 0
            if sys.platform == 'win32':
                creationflags = subprocess.CREATE_NO_WINDOW
            
            # Set up environment with UTF-8 encoding to handle emoji in output
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            # Disable tqdm to prevent stderr flush issues
            env['TQDM_DISABLE'] = '1'
            env['DISABLE_TQDM'] = '1'
            env['COMFY_DISABLE_TQDM'] = '1'
            # Force no unbuffered output
            env['PYTHONUNBUFFERED'] = '0'
            
            self.process = subprocess.Popen(
                cmd,
                cwd=str(COMFYUI_DIR),
                stdout=subprocess.DEVNULL,  # Also suppress stdout to prevent tqdm flush errors
                stderr=subprocess.DEVNULL,  # Suppress stderr to avoid tqdm flush errors
                env=env,
                creationflags=creationflags
            )
            # Note: stdout/stderr are redirected to DEVNULL to prevent tqdm flush issues
            
        except Exception as e:
            logging.error(f"Failed to start ComfyUI: {e}")
            return False
        
        # Wait for server
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_server_running():
                logging.info("ComfyUI server ready!")
                return True
            time.sleep(1)
        
        logging.error("ComfyUI failed to start")
        return False
    
    def stop_server(self):
        """Stop ComfyUI subprocess"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
    
    def load_workflow(self, use_hires_fix: bool = False) -> Dict:
        """Load workflow JSON (Normal or HiresFix version)"""
        workflow_path = WORKFLOW_HIRESFIX if use_hires_fix else WORKFLOW_NORMAL
        logging.info(f"Loading workflow: {workflow_path.name}")
        with open(workflow_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def prepare_workflow(self, workflow: Dict, image_b64: str, prompt: str) -> Dict:
        """
        Prepare workflow for API execution.
        Supports both frontend format (list of nodes) and API format (dict with IDs as keys).
        Updates prompt in workflow if provided.
        """
        # Check if this is API format (dict with numeric string keys like "1", "2")
        if "nodes" not in workflow and any(k.isdigit() for k in workflow.keys()):
            # API format - nodes are in the dict with ID as key
            # Update prompt in TextEncodeQwen nodes if prompt is provided
            if prompt and prompt.strip():
                for node_id, node_data in workflow.items():
                    if not isinstance(node_data, dict):
                        continue
                    class_type = node_data.get("class_type", "")
                    if "TextEncodeQwen" in class_type:
                        if "inputs" in node_data:
                            node_data["inputs"]["prompt"] = prompt
                            logging.info(f"API workflow: Set prompt to: {prompt[:50]}...")
            return workflow
        
        # Frontend format - has "nodes" list
        nodes = workflow.get("nodes", [])
        
        for node in nodes:
            node_type = node.get("type", "")
            
            # Find TextEncodeQwenImageEdit node (prompt input)
            if "TextEncodeQwen" in node_type:
                widgets = node.get("widgets_values", [])
                if widgets and prompt and prompt.strip():
                    node["widgets_values"][0] = prompt
                    logging.info(f"Set prompt: {prompt[:50]}...")
            
            # Find LoadImage node - handled separately
            elif node_type == "LoadImage":
                pass
        
        return workflow
    
    def upload_image(self, image: Image.Image, filename: str = "input.png") -> Optional[str]:
        """Upload image to ComfyUI input folder"""
        try:
            # Convert to bytes
            img_bytes = io.BytesIO()
            image.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            files = {
                'image': (filename, img_bytes, 'image/png')
            }
            
            response = requests.post(
                f"{COMFYUI_URL}/upload/image",
                files=files,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("name", filename)
            else:
                logging.error(f"Upload failed: {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Upload error: {e}")
            return None
    
    def update_loadimage_nodes(self, workflow: Dict, image_filename: str) -> Dict:
        """Update LoadImage nodes to use uploaded image. Supports both formats."""
        
        # Check if API format (dict with numeric string keys)
        if "nodes" not in workflow and any(k.isdigit() for k in workflow.keys()):
            # API format - nodes are in the dict with ID as key
            for node_id, node_data in workflow.items():
                if not isinstance(node_data, dict):
                    continue
                if node_data.get("class_type") == "LoadImage":
                    if "inputs" in node_data:
                        node_data["inputs"]["image"] = image_filename
                        logging.info(f"Set LoadImage to: {image_filename}")
            return workflow
        
        # Frontend format - has "nodes" list
        nodes = workflow.get("nodes", [])
        
        for node in nodes:
            if node.get("type") == "LoadImage":
                widgets = node.get("widgets_values", [])
                if widgets:
                    node["widgets_values"][0] = image_filename
                    logging.info(f"Set LoadImage to: {image_filename}")
        
        return workflow

    
    def resolve_setget_nodes(self, workflow: Dict) -> Dict:
        """
        Resolve SetNode/GetNode virtual links.
        
        SetNode and GetNode are frontend-only JavaScript nodes that create
        "virtual links" - they don't exist in the Python API. This function:
        1. Finds all SetNode nodes and their input sources
        2. Finds all GetNode nodes 
        3. Creates direct links from GetNode destinations to SetNode sources
        4. Removes SetNode/GetNode from the workflow
        
        NOTE: If workflow is already in API format (no "nodes" list), skip this step.
        """
        # Check if API format - no nodes list, just dict with numeric keys
        if "nodes" not in workflow and any(k.isdigit() for k in workflow.keys()):
            # Already API format - no SetNode/GetNode to resolve
            return workflow
        
        nodes = workflow.get("nodes", [])
        links = workflow.get("links", [])

        
        # Build node lookup
        node_by_id = {n["id"]: n for n in nodes}
        
        # Build link lookup
        link_by_id = {}
        for link in links:
            if len(link) >= 6:
                link_id, from_node, from_slot, to_node, to_slot, link_type = link[:6]
                link_by_id[link_id] = {
                    "from_node": from_node,
                    "from_slot": from_slot,
                    "to_node": to_node,
                    "to_slot": to_slot,
                    "type": link_type
                }
        
        # 1. Find all SetNodes and their sources
        setnode_sources = {}  # name -> (source_node_id, source_slot, type)
        setnode_ids = set()
        
        for node in nodes:
            if node.get("type") == "SetNode":
                setnode_ids.add(node["id"])
                name = ""
                widgets = node.get("widgets_values", [])
                if widgets:
                    name = widgets[0]
                
                # Find what's connected to this SetNode's input
                inputs = node.get("inputs", [])
                if inputs:
                    link_id = inputs[0].get("link")
                    if link_id and link_id in link_by_id:
                        link_info = link_by_id[link_id]
                        setnode_sources[name] = (
                            link_info["from_node"],
                            link_info["from_slot"],
                            link_info["type"]
                        )
                        logging.debug(f"SetNode '{name}': source is node {link_info['from_node']} slot {link_info['from_slot']}")
        
        # 2. Find all GetNodes and redirect their outputs
        getnode_ids = set()
        getnode_redirects = {}  # getnode_id -> (actual_source_node, actual_source_slot)
        
        for node in nodes:
            if node.get("type") == "GetNode":
                getnode_ids.add(node["id"])
                name = ""
                widgets = node.get("widgets_values", [])
                if widgets:
                    name = widgets[0]
                
                if name in setnode_sources:
                    source_node, source_slot, source_type = setnode_sources[name]
                    getnode_redirects[node["id"]] = (source_node, source_slot)
                    logging.debug(f"GetNode '{name}' (id={node['id']}): redirect to node {source_node} slot {source_slot}")
                else:
                    logging.warning(f"GetNode '{name}' has no matching SetNode!")
        
        # 3. Update links: redirect any link FROM a GetNode to point to the actual source
        new_links = []
        for link in links:
            if len(link) >= 6:
                link_id, from_node, from_slot, to_node, to_slot, link_type = link[:6]
                
                # Skip links TO SetNode (they're consumed)
                if to_node in setnode_ids:
                    continue
                
                # Skip links TO GetNode (shouldn't exist but just in case)
                if to_node in getnode_ids:
                    continue
                
                # Handle links FROM GetNode
                if from_node in getnode_ids:
                    if from_node in getnode_redirects:
                        # Redirect to actual source
                        actual_source, actual_slot = getnode_redirects[from_node]
                        new_link = [link_id, actual_source, actual_slot, to_node, to_slot, link_type]
                        if len(link) > 6:
                            new_link.extend(link[6:])
                        new_links.append(new_link)
                        logging.debug(f"Redirected link {link_id}: {from_node}->{to_node} becomes {actual_source}->{to_node}")
                    else:
                        # Orphaned GetNode - skip this link entirely
                        logging.warning(f"Skipping link from orphaned GetNode {from_node}")
                        continue
                else:
                    new_links.append(link)

        
        # 4. Remove SetNode and GetNode from nodes list
        new_nodes = [n for n in nodes if n["id"] not in setnode_ids and n["id"] not in getnode_ids]
        
        logging.info(f"Resolved {len(setnode_ids)} SetNodes and {len(getnode_ids)} GetNodes")
        
        # =====================================================
        # 5. Handle Any Switch (rgthree) - frontend-only passthrough
        # This node selects one of multiple inputs to output
        # We redirect links FROM Any Switch to its first connected input
        # =====================================================
        
        # Rebuild link_by_id with updated links
        link_by_id_updated = {}
        for link in new_links:
            if len(link) >= 6:
                link_id, from_node, from_slot, to_node, to_slot, link_type = link[:6]
                link_by_id_updated[link_id] = {
                    "id": link_id,
                    "from_node": from_node,
                    "from_slot": from_slot,
                    "to_node": to_node,
                    "to_slot": to_slot,
                    "type": link_type
                }
        
        anyswitch_ids = set()
        anyswitch_redirects = {}  # anyswitch_id -> (source_node, source_slot)
        
        for node in new_nodes:
            if node.get("type") == "Any Switch (rgthree)":
                anyswitch_ids.add(node["id"])
                
                # Find first connected input
                inputs = node.get("inputs", [])
                for inp in inputs:
                    link_id = inp.get("link")
                    if link_id and link_id in link_by_id_updated:
                        link_info = link_by_id_updated[link_id]
                        anyswitch_redirects[node["id"]] = (link_info["from_node"], link_info["from_slot"])
                        logging.debug(f"Any Switch (id={node['id']}): redirect to node {link_info['from_node']} slot {link_info['from_slot']}")
                        break  # Use first connected input
        
        # Update links to redirect FROM Any Switch
        final_links = []
        for link in new_links:
            if len(link) >= 6:
                link_id, from_node, from_slot, to_node, to_slot, link_type = link[:6]
                
                # Skip links TO Any Switch
                if to_node in anyswitch_ids:
                    continue
                
                # Redirect links FROM Any Switch
                if from_node in anyswitch_redirects:
                    actual_source, actual_slot = anyswitch_redirects[from_node]
                    new_link = [link_id, actual_source, actual_slot, to_node, to_slot, link_type]
                    if len(link) > 6:
                        new_link.extend(link[6:])
                    final_links.append(new_link)
                    logging.debug(f"Redirected Any Switch link {link_id}")
                else:
                    final_links.append(link)
        
        # Remove Any Switch nodes
        final_nodes = [n for n in new_nodes if n["id"] not in anyswitch_ids]
        
        if anyswitch_ids:
            logging.info(f"Resolved {len(anyswitch_ids)} Any Switch (rgthree) nodes")
        
        return {
            **workflow,
            "nodes": final_nodes,
            "links": final_links
        }
    

    def convert_to_api_format(self, workflow: Dict) -> Dict:
        """
        Convert UI workflow to API format.
        
        The API format requires:
        - class_type: node type name
        - inputs: dict of input_name -> value or [node_id, slot]
        
        NOTE: If workflow is already in API format (no "nodes" list), return as-is.
        """
        # Check if already API format - no nodes list, just dict with numeric keys
        if "nodes" not in workflow and any(k.isdigit() for k in workflow.keys()):
            # Already API format - return as-is
            logging.info("Workflow already in API format, skipping conversion")
            return workflow
        
        # Widget values from UI need to be mapped to their input names.
        api_workflow = {}

        
        nodes = workflow.get("nodes", [])
        links = workflow.get("links", [])
        
        # Create link lookup: link_id -> (from_node, from_slot)
        link_map = {}
        for link in links:
            if len(link) >= 6:
                link_id, from_node, from_slot, to_node, to_slot, link_type = link[:6]
                link_map[link_id] = (from_node, from_slot)
        
        # Class type aliases - map old names to new API names
        CLASS_TYPE_ALIASES = {
            "LoaderGGUF": "UnetLoaderGGUF",  # Old ComfyUI-GGUF name
        }

        
        # Widget name mappings for common Qwen workflow nodes
        # Maps node_type -> list of (widget_name, widget_type) in order
        WIDGET_MAPPINGS = {
            "UNETLoaderGGUF": [
                ("unet_name", "combo"),
            ],
            "VAELoader": [
                ("vae_name", "combo"),
            ],
            "DualCLIPLoaderGGUF": [
                ("clip_name1", "combo"),
                ("clip_name2", "combo"),
                ("type", "combo"),
            ],
            "CLIPLoader": [
                ("clip_name", "combo"),
                ("type", "combo"),
                ("device", "combo"),
            ],
            "LoraLoaderModelOnly": [
                ("lora_name", "combo"),
                ("strength_model", "float"),
            ],
            "LoRALoaderQwenImage": [
                ("lora_name", "combo"),
                ("strength", "float"),
            ],
            "LoadImage": [
                ("image", "combo"),
                ("upload", "hidden"),
            ],
            "TextEncodeQwenImageEdit": [
                ("prompt", "string"),  # API expects 'prompt' not 'text'
            ],

            "KSampler": [
                ("seed", "int"),
                ("control_after_generate", "combo"),  # control widget - skip
                ("steps", "int"),
                ("cfg", "float"),
                ("sampler_name", "combo"),
                ("scheduler", "combo"),
                ("denoise", "float"),
            ],
            "KSamplerSelect": [
                ("sampler_name", "combo"),
            ],

            "BasicScheduler": [
                ("scheduler", "combo"),
                ("steps", "int"),
                ("denoise", "float"),
            ],
            "SamplerCustomAdvanced": [
                ("noise_seed", "int"),
                ("control_after_generate", "combo"),
            ],
            "EmptyLatentImage": [
                ("width", "int"),
                ("height", "int"),
                ("batch_size", "int"),
            ],
            "ImageScaleToTotalPixels": [
                ("upscale_method", "combo"),
                ("megapixels", "float"),
            ],
            "VAEDecode": [],  # No widgets
            "VAEEncode": [],  # No widgets

            "SaveImage": [
                ("filename_prefix", "string"),
            ],
            "PreviewImage": [],  # No widgets
            "SetNode": [
                ("name", "string"),
            ],
            "GetNode": [
                ("name", "string"),
            ],
            "easy cleanGpuUsed": [
                ("action", "combo"),
            ],
            "Any Switch (rgthree)": [
                ("any_01", "wildcard"),
                ("any_02", "wildcard"),
            ],
        }
        
        for node in nodes:
            node_id = str(node["id"])
            node_type = node.get("type", "")
            
            # Skip UI-only nodes
            if node_type in ["Note", "Label (rgthree)", "Fast Groups Bypasser (rgthree)", "Reroute"]:
                continue
            
            # Skip bypassed nodes (mode 4 = bypassed)
            if node.get("mode", 0) == 4:
                continue
            
            # Apply class type alias if exists
            api_class_type = CLASS_TYPE_ALIASES.get(node_type, node_type)
            
            api_node = {
                "class_type": api_class_type,

                "inputs": {},
                "_meta": {"title": node.get("title", node_type)}
            }
            
            # 1. Process widget values
            widgets = node.get("widgets_values", [])
            widget_names = WIDGET_MAPPINGS.get(node_type, [])
            
            # If no static mapping, try to get from API
            if not widget_names:
                widget_names = WIDGET_MAPPINGS.get(api_class_type, [])
            
            # If still no mapping, try dynamic lookup from API
            if not widget_names:
                node_info = self.get_node_info(api_class_type)
                if node_info:
                    # Extract required inputs that are not node connections
                    required = node_info.get("input", {}).get("required", {})
                    for input_name, input_info in required.items():
                        # Check if it's a widget (not a connection type like MODEL, LATENT, etc.)
                        if isinstance(input_info, list) and len(input_info) > 0:
                            first_val = input_info[0]
                            # If first value is a list of options or a primitive type, it's a widget
                            if isinstance(first_val, list) or isinstance(first_val, str) and first_val in ["INT", "FLOAT", "STRING", "BOOLEAN"]:
                                widget_names.append((input_name, "dynamic"))
            
            widget_idx = 0
            for i, widget_val in enumerate(widgets):
                if widget_idx < len(widget_names):
                    name, wtype = widget_names[widget_idx]
                    # Skip hidden/control widgets
                    if wtype not in ["hidden"]:
                        # Handle special "control_after_generate" which is control widget
                        if name == "control_after_generate":
                            widget_idx += 1
                            continue
                        api_node["inputs"][name] = widget_val
                    widget_idx += 1
                else:
                    # Unknown widget, skip
                    pass

            
            # 2. Process linked inputs (override widgets if linked)
            inputs = node.get("inputs", [])
            for inp in inputs:
                link_id = inp.get("link")
                inp_name = inp.get("name", "")
                if link_id is not None and link_id in link_map:
                    from_node, from_slot = link_map[link_id]
                    api_node["inputs"][inp_name] = [str(from_node), from_slot]
            
            api_workflow[node_id] = api_node
        
        return api_workflow
    
    def queue_prompt(self, workflow: Dict) -> Optional[str]:
        """Queue workflow for execution"""
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }
        
        try:
            response = requests.post(
                f"{COMFYUI_URL}/prompt",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("prompt_id")
            else:
                logging.error(f"Queue failed: {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Queue error: {e}")
            return None
    
    def wait_for_result(
        self, 
        prompt_id: str, 
        timeout: int = 600,  # Increased for HiresFix workflows
        progress_callback: Optional[Callable[[int, str], None]] = None,
        preview_callback: Optional[Callable[[str, int], None]] = None  # (base64, step)
    ) -> Optional[bytes]:
        """
        Wait for execution and get result image.
        Uses WebSocket for real-time progress and preview updates.
        
        Args:
            preview_callback: Optional callback(base64_image, step) for live preview
        """
        import websocket
        import struct
        
        start_time = time.time()
        result_image = None
        current_step = 0
        preview_interval = 4  # Send preview every 4 steps
        
        try:
            # Connect to ComfyUI WebSocket
            ws_url = f"ws://{COMFYUI_HOST}:{COMFYUI_PORT}/ws?clientId={self.client_id}"
            ws = websocket.create_connection(ws_url, timeout=5)
            ws.settimeout(1.0)  # Non-blocking with timeout
            
            logging.info(f"WebSocket connected for prompt {prompt_id[:8]}...")
            
            while time.time() - start_time < timeout:
                try:
                    # Receive message
                    msg = ws.recv()
                    
                    # Binary message = preview image
                    if isinstance(msg, bytes):
                        if len(msg) > 8 and preview_callback:
                            # ComfyUI binary format: type(4) + format(4) + image_data
                            try:
                                # Extract image data (skip first 8 bytes header)
                                image_data = msg[8:]
                                
                                # Convert to base64 - keep reasonable size for preview
                                img = Image.open(io.BytesIO(image_data))
                                
                                # Scale preview to reasonable size while maintaining aspect ratio
                                w, h = img.size
                                # Target: keep longest side at 75% but minimum 512px
                                max_dim = max(w, h)
                                target_dim = max(512, int(max_dim * 0.75))
                                scale = target_dim / max_dim
                                preview_w = int(w * scale)
                                preview_h = int(h * scale)
                                preview_img = img.resize((preview_w, preview_h), Image.LANCZOS)
                                
                                # Convert to JPEG base64
                                buffer = io.BytesIO()
                                preview_img.save(buffer, format='JPEG', quality=75)
                                preview_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                                
                                preview_callback(preview_b64, current_step)
                                logging.debug(f"Preview sent: step {current_step}")
                            except Exception as e:
                                logging.debug(f"Preview decode error: {e}")
                        continue
                    
                    # JSON message = status update
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    msg_data = data.get("data", {})
                    
                    if msg_type == "progress":
                        # Progress update
                        value = msg_data.get("value", 0)
                        max_val = msg_data.get("max", 1)
                        current_step = value
                        
                        if max_val > 0:
                            progress = int((value / max_val) * 100)
                            if progress_callback:
                                progress_callback(progress, f"Step {value}/{max_val}")
                    
                    elif msg_type == "executing":
                        node = msg_data.get("node")
                        if node is None and msg_data.get("prompt_id") == prompt_id:
                            # Execution complete
                            logging.info("Execution complete, fetching result...")
                            break
                    
                    elif msg_type == "execution_error":
                        error_msg = msg_data.get("exception_message", "Unknown error")
                        node_id = msg_data.get("node_id", "?")
                        node_type = msg_data.get("node_type", "?")
                        logging.error(f"ComfyUI execution error in node {node_id} ({node_type}): {error_msg}")
                        ws.close()
                        raise RuntimeError(f"ComfyUI error in {node_type}: {error_msg}")
                        
                except websocket.WebSocketTimeoutException:
                    # Timeout on recv, continue polling
                    pass
                except RuntimeError:
                    # Re-raise our explicit errors
                    raise
                except Exception as e:
                    logging.debug(f"WS recv error: {e}")
            
            ws.close()
            
        except Exception as e:
            logging.warning(f"WebSocket failed, falling back to polling: {e}")
            # Fallback to polling if WebSocket fails
            return self._poll_for_result(prompt_id, timeout, start_time, progress_callback)
        
        # Fetch result from history
        return self._fetch_result_from_history(prompt_id)
    
    def _poll_for_result(
        self, 
        prompt_id: str, 
        timeout: int,
        start_time: float,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Optional[bytes]:
        """Fallback polling method"""
        while time.time() - start_time < timeout:
            result = self._fetch_result_from_history(prompt_id)
            if result:
                return result
            
            elapsed = time.time() - start_time
            progress = min(95, int((elapsed / timeout) * 100))
            if progress_callback:
                progress_callback(progress, "Processing...")
            
            time.sleep(0.5)
        return None
    
    def _fetch_result_from_history(self, prompt_id: str) -> Optional[bytes]:
        """Fetch result image from ComfyUI history"""
        try:
            response = requests.get(
                f"{COMFYUI_URL}/history/{prompt_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                history = response.json()
                
                if prompt_id in history:
                    result = history[prompt_id]
                    
                    # Check for errors
                    status = result.get("status", {})
                    if status.get("status_str") == "error":
                        logging.error(f"Execution error: {result}")
                        return None
                    
                    # Get outputs
                    outputs = result.get("outputs", {})
                    if outputs:
                        # Find first image output
                        for node_id, output in outputs.items():
                            images = output.get("images", [])
                            if images:
                                img_info = images[0]
                                return self._download_image(
                                    img_info["filename"],
                                    img_info.get("subfolder", ""),
                                    img_info.get("type", "output")
                                )
        except Exception as e:
            logging.debug(f"History fetch error: {e}")
        
        return None
    
    def _download_image(self, filename: str, subfolder: str, folder_type: str) -> Optional[bytes]:
        """Download result image from ComfyUI"""
        try:
            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type
            }
            response = requests.get(
                f"{COMFYUI_URL}/view",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.content
            return None
            
        except Exception as e:
            logging.error(f"Download error: {e}")
            return None
    
    def execute(
        self,
        image: Image.Image,
        prompt: str,
        use_hires_fix: bool = False,
        hires_fix_mode: str = "normal",
        denoise: float = 0.6,
        sdxl_saturation: float = 0.2,
        sdxl_steps: int = 8,
        sdxl_denoise: float = 0.7,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        preview_callback: Optional[Callable[[str, int], None]] = None  # (base64, step)
    ) -> Optional[Image.Image]:
        """
        Execute Make it Real workflow.
        
        Args:
            image: Input PIL Image
            prompt: Text prompt for transformation
            use_hires_fix: If True, use HiresFix workflow (2x upscale + refine)
            hires_fix_mode: "normal" or "advanced"
            denoise: Denoise strength for KSampler (0.0-1.0), lower = closer to original
            progress_callback: Optional callback(progress_percent, status_text)
            preview_callback: Optional callback(base64_image, step) for live preview
            
        Returns:
            Result PIL Image or None
        """
        if progress_callback:
            progress_callback(5, "Starting ComfyUI...")
        
        # Ensure server is running
        if not self.start_server():
            logging.error("Failed to start ComfyUI")
            return None
        
        if progress_callback:
            progress_callback(10, "Uploading image...")
        
        # Upload image
        img_name = f"input_{uuid.uuid4().hex[:8]}.png"
        uploaded_name = self.upload_image(image, img_name)
        if not uploaded_name:
            logging.error("Failed to upload image")
            return None
        
        if progress_callback:
            # Determine which base workflow to use
            # If Advanced HiresFix, use the dedicated HiresFix workflow
            # If Normal HiresFix or No HiresFix, use the Normal workflow (we chain manually for Normal)
            use_integrated_hires = use_hires_fix and hires_fix_mode == "advanced"
            wf_name = "HiresFix (Advanced)" if use_integrated_hires else "Normal"
            progress_callback(15, f"Preparing {wf_name} workflow...")
        
        # Load and prepare workflow
        use_integrated_hires = use_hires_fix and hires_fix_mode == "advanced"
        workflow = self.load_workflow(use_hires_fix=use_integrated_hires)
        workflow = self.prepare_workflow(workflow, "", prompt)
        workflow = self.update_loadimage_nodes(workflow, uploaded_name)
        
        # Apply denoise to first KSampler (node 560)
        if "560" in workflow and "inputs" in workflow["560"]:
            workflow["560"]["inputs"]["denoise"] = denoise
            logging.info(f"Applied denoise={denoise} to KSampler node 560")
        
        # Resolve SetNode/GetNode virtual links (frontend-only nodes)
        workflow = self.resolve_setget_nodes(workflow)
        
        # Convert to API format
        api_workflow = self.convert_to_api_format(workflow)

        
        if progress_callback:
            progress_callback(20, "Queuing...")
        
        # Queue prompt
        prompt_id = self.queue_prompt(api_workflow)
        if not prompt_id:
            logging.error("Failed to queue prompt")
            return None
        
        if progress_callback:
            progress_callback(25, "Processing with Qwen...")
        
        # Wait for result
        def internal_progress(p, msg):
            if progress_callback:
                # Map 0-100 to 25-95 (leave room for potential second pass)
                end_range = 50 if (use_hires_fix and hires_fix_mode == "normal") else 95
                overall = 25 + int(p * (end_range - 25) / 100)
                progress_callback(overall, msg)
        
        result_bytes = self.wait_for_result(
            prompt_id, 
            progress_callback=internal_progress,
            preview_callback=preview_callback
        )
        
        if not result_bytes:
            return None
            
        result_image = Image.open(io.BytesIO(result_bytes))
        
        # === Step 2: Hires Fix Normal (Chained SDXL Tiled Upscale x1) ===
        if use_hires_fix and hires_fix_mode == "normal":
            logging.info("Starting HiresFix Normal (SDXL Tiled x1) pass...")
            
            def hires_progress(p, msg):
                if progress_callback:
                    # Map 0-100 to 50-100
                    overall = 50 + int(p * 0.5)
                    progress_callback(overall, f"HiresFix: {msg}")
            
            # Execute SDXL Tiled Upscale x1
            result_image = self.execute_sdxl_tiled_upscale(
                result_image, 
                scale_factor=1, 
                sdxl_saturation=sdxl_saturation,
                sdxl_steps=sdxl_steps,
                sdxl_denoise=sdxl_denoise,
                progress_callback=hires_progress,
                preview_callback=preview_callback
            )
            
        return result_image
    
    def execute_sdxl_tiled_upscale(
        self,
        image: Image.Image,
        scale_factor: int = 2,
        sdxl_saturation: float = 0.2,
        sdxl_steps: int = 8,
        sdxl_denoise: float = 0.7,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        preview_callback: Optional[Callable[[str, int], None]] = None
    ) -> Optional[Image.Image]:
        """
        Execute SDXL Realistic Advanced Tiled Upscale workflow.
        
        This workflow uses:
        - AnalogMadness SDXL checkpoint
        - SDXL Lightning 8-step LoRA for fast inference
        - Tile ControlNet for detail preservation
        - 2x2 tiling for memory efficiency
        - Film grain and sharpening post-processing
        
        Args:
            image: Input PIL Image
            progress_callback: Optional callback(progress_percent, status_text)
            preview_callback: Optional callback(base64_image, step) for live preview
            
        Returns:
            Result PIL Image (2x upscaled) or None
        """
        if progress_callback:
            progress_callback(5, "Starting ComfyUI...")
        
        # Ensure server is running
        if not self.start_server():
            logging.error("Failed to start ComfyUI")
            return None
        
        if progress_callback:
            progress_callback(10, "Uploading image...")
        
        # Upload image
        img_name = f"input_{uuid.uuid4().hex[:8]}.png"
        uploaded_name = self.upload_image(image, img_name)
        if not uploaded_name:
            logging.error("Failed to upload image")
            return None
        
        if progress_callback:
            progress_callback(15, "Preparing SDXL Tiled Upscale workflow...")
        
        # Load workflow
        logging.info(f"Loading workflow: {WORKFLOW_SDXL_TILED_UPSCALE.name}")
        with open(WORKFLOW_SDXL_TILED_UPSCALE, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        # Update LoadImage node (node "129") with input image
        workflow = self.update_loadimage_nodes(workflow, uploaded_name)
        
        # Update Scale Factor
        if "114:47" in workflow and "inputs" in workflow["114:47"]:
            workflow["114:47"]["inputs"]["scale_by"] = scale_factor
            logging.info(f"Updated SDXL upscale factor to {scale_factor}x")

        # Update Saturation (FastFilmGrain - Node 100)
        if "100" in workflow and "inputs" in workflow["100"]:
            workflow["100"]["inputs"]["saturation_mix"] = sdxl_saturation
            logging.info(f"Updated SDXL Saturation Mix to {sdxl_saturation}")

        # Update Steps and Denoise for all KSamplers
        # Identified KSamplers: 114:23, 114:19, 114:58
        target_ksamplers = ["114:23", "114:19", "114:58"]
        for node_id in target_ksamplers:
            if node_id in workflow and "inputs" in workflow[node_id]:
                workflow[node_id]["inputs"]["steps"] = sdxl_steps
                workflow[node_id]["inputs"]["denoise"] = sdxl_denoise
        logging.info(f"Updated SDXL KSamplers (Steps: {sdxl_steps}, Denoise: {sdxl_denoise})")
        
        # Resolve SetNode/GetNode virtual links (frontend-only nodes)
        workflow = self.resolve_setget_nodes(workflow)
        
        # Convert to API format
        api_workflow = self.convert_to_api_format(workflow)
        
        if progress_callback:
            progress_callback(20, "Queuing...")
        
        # Queue prompt
        prompt_id = self.queue_prompt(api_workflow)
        if not prompt_id:
            logging.error("Failed to queue prompt")
            return None
        
        if progress_callback:
            progress_callback(25, "Processing with SDXL Tiled Upscale...")
        
        # Wait for result
        def internal_progress(p, msg):
            if progress_callback:
                # Map 0-100 to 25-95
                overall = 25 + int(p * 0.7)
                progress_callback(overall, msg)
        
        result_bytes = self.wait_for_result(
            prompt_id, 
            timeout=900,  # 15 minutes for large images
            progress_callback=internal_progress,
            preview_callback=preview_callback
        )
        
        if result_bytes:
            if progress_callback:
                progress_callback(100, "Complete!")
            return Image.open(io.BytesIO(result_bytes))
        
        return None


# Global executor instance
_executor: Optional[ComfyUIExecutor] = None

def get_executor() -> ComfyUIExecutor:
    """Get or create global executor"""
    global _executor
    if _executor is None:
        _executor = ComfyUIExecutor()
    return _executor


def make_it_real(
    image: Image.Image,
    prompt: str = "convert to photorealistic, raw photo, dslr quality",
    use_hires_fix: bool = False,
    hires_fix_mode: str = "normal",
    denoise: float = 0.6,
    sdxl_saturation: float = 0.2,
    sdxl_steps: int = 8,
    sdxl_denoise: float = 0.7,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    preview_callback: Optional[Callable[[str, int], None]] = None  # (base64, step)
) -> Optional[Image.Image]:
    """
    Main entry point for Make it Real feature.
    """
    executor = get_executor()
    return executor.execute(
        image, prompt, use_hires_fix, hires_fix_mode, denoise, 
        sdxl_saturation, sdxl_steps, sdxl_denoise,
        progress_callback, preview_callback
    )


def sdxl_tiled_upscale(
    image: Image.Image,
    scale_factor: int = 2,
    sdxl_saturation: float = 0.2,
    sdxl_steps: int = 8,
    sdxl_denoise: float = 0.7,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    preview_callback: Optional[Callable[[str, int], None]] = None
) -> Optional[Image.Image]:
    """
    Entry point for SDXL Tiled Upscale.
    
    Args:
        image: Input PIL Image
        scale_factor: Upscale factor (e.g., 2 for 2x)
        sdxl_saturation: Saturation mix for FastFilmGrain node
        sdxl_steps: Number of steps for KSamplers
        sdxl_denoise: Denoise value for KSamplers
        progress_callback: Optional progress callback
        preview_callback: Optional callback(base64_image, step) for live preview
        
    Returns:
        2x Upscaled PIL Image or None
    """
    executor = get_executor()
    return executor.execute_sdxl_tiled_upscale(
        image, scale_factor, 
        sdxl_saturation, sdxl_steps, sdxl_denoise,
        progress_callback, preview_callback
    )


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    executor = ComfyUIExecutor()
    print(f"ComfyUI running: {executor.is_server_running()}")
    print(f"Workflow exists: {WORKFLOW_PATH.exists()}")
