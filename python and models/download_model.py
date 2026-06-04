#!/usr/bin/env python3
"""Download model.safetensors from HuggingFace."""
import sys
from pathlib import Path

models_dir = Path(__file__).parent / "models"
models_dir.mkdir(parents=True, exist_ok=True)
model_file = models_dir / "model.safetensors"

if model_file.exists() and model_file.stat().st_size > 0:
    print(f"✅ Model already exists ({model_file.stat().st_size / 1024 / 1024:.1f} MB)")
    sys.exit(0)

print("⏳ Downloading model.safetensors from HuggingFace...")
print("   Repo: fancyfeast/joytag")
print("   This may take a few minutes...")

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("❌ huggingface_hub not installed. Run 'pip install huggingface-hub' first.")
    sys.exit(1)

try:
    # Download to a temp dir first, then move to avoid partial files
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        path = snapshot_download(
            repo_id="fancyfeast/joytag",
            allow_patterns=["model.safetensors"],
            cache_dir=tmpdir,
        )
        # Copy the file (snapshot_download returns the dir, not the file)
        import shutil
        src = Path(path) / "model.safetensors"
        shutil.copy2(src, model_file)
    
    size_mb = model_file.stat().st_size / 1024 / 1024
    print(f"✅ Model downloaded: {model_file} ({size_mb:.1f} MB)")
except Exception as e:
    print(f"❌ Failed to download model: {e}")
    sys.exit(1)
