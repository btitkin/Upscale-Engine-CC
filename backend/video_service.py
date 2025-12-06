"""
Video Frame Extraction Service
Extracts frames from videos for individual processing
"""
import os
import base64
import io
from pathlib import Path
from typing import List, Optional, Tuple, Generator, Callable
from PIL import Image
import numpy as np

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    print("⚠ OpenCV not available for video processing")


def is_video_file(filename: str) -> bool:
    """Check if file is a video based on extension"""
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.wmv', '.flv', '.m4v'}
    return Path(filename).suffix.lower() in video_extensions


def get_video_info(video_path: str) -> Optional[dict]:
    """
    Get video metadata
    
    Returns:
        dict with fps, frame_count, duration, width, height
    """
    if not HAS_OPENCV:
        return None
        
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        
        return {
            "fps": fps,
            "frame_count": frame_count,
            "duration": duration,
            "width": width,
            "height": height
        }
    finally:
        cap.release()


def extract_frames(
    video_path: str,
    interval: float = 1.0,
    max_frames: int = 100,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Generator[Tuple[int, Image.Image], None, None]:
    """
    Extract frames from video at specified interval
    
    Args:
        video_path: Path to video file
        interval: Seconds between extracted frames (default 1.0)
        max_frames: Maximum number of frames to extract
        progress_callback: Optional callback(current, total)
        
    Yields:
        Tuple of (frame_number, PIL.Image)
    """
    if not HAS_OPENCV:
        raise RuntimeError("OpenCV not installed. Run: pip install opencv-python")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Calculate frame interval
        frame_interval = max(1, int(fps * interval))
        
        # Calculate expected number of frames
        expected_frames = min(max_frames, frame_count // frame_interval)
        
        extracted = 0
        frame_idx = 0
        
        while extracted < max_frames:
            # Seek to frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(frame_rgb)
            
            extracted += 1
            
            if progress_callback:
                progress_callback(extracted, expected_frames)
            
            yield (frame_idx, pil_image)
            
            frame_idx += frame_interval
            
    finally:
        cap.release()


def extract_frames_to_base64(
    video_path: str,
    interval: float = 1.0,
    max_frames: int = 100,
    quality: int = 85,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[dict]:
    """
    Extract frames from video and return as base64 JPEG
    
    Returns:
        List of dicts with frame_number, image_b64, timestamp
    """
    if not HAS_OPENCV:
        raise RuntimeError("OpenCV not installed")
    
    info = get_video_info(video_path)
    if not info:
        raise ValueError("Cannot read video info")
    
    fps = info["fps"]
    results = []
    
    for frame_idx, pil_image in extract_frames(
        video_path, interval, max_frames, progress_callback
    ):
        # Convert to base64 JPEG
        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=quality)
        image_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        timestamp = frame_idx / fps if fps > 0 else 0
        
        results.append({
            "frame_number": frame_idx,
            "timestamp": round(timestamp, 2),
            "image_b64": image_b64,
            "width": pil_image.width,
            "height": pil_image.height
        })
    
    return results


def reassemble_video(
    frames: List[Tuple[int, Image.Image]],
    output_path: str,
    fps: float = 30.0,
    codec: str = 'mp4v'
) -> bool:
    """
    Reassemble processed frames into a video
    
    Args:
        frames: List of (frame_number, PIL.Image) tuples
        output_path: Path for output video
        fps: Output frame rate
        codec: FourCC codec code
        
    Returns:
        True if successful
    """
    if not HAS_OPENCV or not frames:
        return False
    
    # Sort frames by number
    frames = sorted(frames, key=lambda x: x[0])
    
    # Get dimensions from first frame
    first_frame = frames[0][1]
    width, height = first_frame.size
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*codec)
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        return False
    
    try:
        for _, pil_image in frames:
            # Convert PIL to numpy BGR
            frame_rgb = np.array(pil_image)
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            
            # Resize if needed
            if frame_bgr.shape[1] != width or frame_bgr.shape[0] != height:
                frame_bgr = cv2.resize(frame_bgr, (width, height))
            
            out.write(frame_bgr)
        
        return True
        
    finally:
        out.release()


# Add video extraction endpoint to server
"""
To add to server.py:

@app.route('/video/extract', methods=['POST'])
def extract_video_frames():
    # Expects: video file upload
    # Returns: list of extracted frames as base64
    pass
"""
