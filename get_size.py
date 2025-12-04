import requests

url = "https://huggingface.co/MonsterMMORPG/Wan_GGUF/resolve/main/Qwen-Image-Edit-Plus-2509-Q3_K_M.gguf"

print(f"Checking size for: {url}")
try:
    response = requests.head(url, allow_redirects=True)
    size = int(response.headers.get('content-length', 0))
    print(f"Size: {size}")
except Exception as e:
    print(f"Error: {e}")
