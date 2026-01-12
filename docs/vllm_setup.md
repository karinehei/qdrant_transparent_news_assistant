# vLLM Setup Guide

vLLM is a **high-performance LLM inference engine** that can be **10-20x faster** than Ollama, especially with GPU support.

## Why vLLM?

### Performance Comparison

| Metric | Ollama | vLLM |
|--------|--------|------|
| **Throughput** | ~41 TPS | **~793 TPS** |
| **Latency** | 60-120s (CPU) | **2-5s (GPU)** |
| **Concurrency** | Limited | Excellent |
| **Hardware** | CPU/GPU | **GPU required** |

### When to Use vLLM

✅ **Use vLLM if:**
- You have a GPU (NVIDIA with CUDA)
- You need fast responses (2-5 seconds)
- You're experiencing slow Ollama performance
- You need to handle concurrent requests

❌ **Stick with Ollama if:**
- No GPU available
- CPU-only setup
- Simple local development
- Apple Silicon Mac

## Installation

### Prerequisites

- **NVIDIA GPU** with CUDA support
- **Python 3.8+**
- **CUDA 11.8+** or **CUDA 12.1+**

### Install vLLM

```bash
# Install vLLM
pip install vllm

# Or with specific CUDA version
pip install vllm --extra-index-url https://download.pytorch.org/whl/cu121
```

### Start vLLM Server

```bash
# Start vLLM server with a model
# Note: Use port 8001 to avoid conflict with API server (port 8000)
python -m vllm.entrypoints.openai.api_server \
    --model microsoft/Phi-3-mini-4k-instruct \
    --port 8001 \
    --host 0.0.0.0
```

**Recommended models for speed:**
- `microsoft/Phi-3-mini-4k-instruct` (~2GB, very fast)
- `microsoft/Phi-3-medium-4k-instruct` (~7GB, good quality)
- `mistralai/Mistral-7B-Instruct-v0.2` (~4GB, high quality)

## Configuration

### Option 1: Environment Variables

Update your `.env` file:

```bash
# Use vLLM instead of Ollama
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8001
VLLM_MODEL=microsoft/Phi-3-mini-4k-instruct
```

### Option 2: Docker Compose

Add vLLM service to `docker-compose.yml`:

```yaml
services:
  vllm:
    image: vllm/vllm-openai:latest
    container_name: news_vllm
    ports:
      - "8001:8001"
    environment:
      - MODEL=microsoft/Phi-3-mini-4k-instruct
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    command: --host 0.0.0.0 --port 8001

  api:
    # ... existing config ...
    environment:
      - LLM_PROVIDER=vllm
      - VLLM_BASE_URL=http://vllm:8001
      - VLLM_MODEL=microsoft/Phi-3-mini-4k-instruct
    depends_on:
      - vllm
```

**Note:** Requires Docker with NVIDIA Container Toolkit installed.

## Usage

Once configured, the system automatically uses vLLM:

```bash
# Restart API
docker-compose restart api

# Or if running locally
python -m news_assistant.api
```

## Performance Tips

1. **Use GPU**: vLLM requires GPU for good performance
2. **Choose smaller models**: Phi-3-mini is much faster than larger models
3. **Adjust max_tokens**: Lower values = faster responses
4. **Batch requests**: vLLM handles batching efficiently

## Troubleshooting

### "Cannot connect to vLLM"

1. **Check vLLM is running:**
   ```bash
   curl http://localhost:8001/v1/models
   ```

2. **Check GPU availability:**
   ```bash
   nvidia-smi
   ```

3. **Check vLLM logs:**
   ```bash
   # If running in Docker
   docker logs news_vllm
   ```

### "Cannot connect to vLLM" on Windows/WSL (host.docker.internal issues)

If you see `Cannot connect to vLLM at http://host.docker.internal:8001`:

**Solution 1: Use environment variable override (Recommended)**
   
   Update your `.env` file or set environment variable:
   ```bash
   # In .env file
   VLLM_BASE_URL=http://localhost:8001
   
   # Or if vLLM is in Docker (uncomment vllm service in docker-compose.yml)
   VLLM_BASE_URL=http://vllm:8001
   ```
   
   Then restart:
   ```bash
   docker-compose restart api
   ```

**Solution 2: Find your host IP address**
   
   ```powershell
   # Windows PowerShell - find your IP
   ipconfig
   # Look for IPv4 Address (e.g., 192.168.1.100)
   
   # Then in .env or docker-compose.yml:
   VLLM_BASE_URL=http://192.168.1.100:8001
   ```

**Solution 3: Run vLLM in Docker (Best for production)**
   
   1. Uncomment the `vllm` service in `docker-compose.yml`
   2. Set `VLLM_BASE_URL=http://vllm:8001` in your `.env` file
   3. Restart: `docker-compose up -d`

**Solution 4: Ensure vLLM is bound to 0.0.0.0**
   
   When starting vLLM on the host, make sure it's bound to all interfaces:
   ```bash
   python -m vllm.entrypoints.openai.api_server \
       --model microsoft/Phi-3-mini-4k-instruct \
       --port 8001 \
       --host 0.0.0.0  # Important: not 127.0.0.1!
   ```

**Solution 5: Check Windows Firewall**
   
   Ensure port 8001 is allowed through Windows Firewall:
   ```powershell
   # Check firewall rules
   Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*8001*"}
   
   # Add rule if needed (run as Administrator)
   New-NetFirewallRule -DisplayName "vLLM Port 8001" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
   ```

### "CUDA out of memory"

- Use a smaller model
- Reduce `max_model_len` in vLLM
- Close other GPU applications

### "Model not found"

- Check model name is correct (HuggingFace format)
- Ensure model is downloaded
- Check vLLM logs for download progress

### "Address already in use" / Port Conflict

If you see `OSError: [Errno 98] Address already in use`:

1. **Check what's using the port:**
   ```bash
   # Linux/WSL
   lsof -i :8001
   # or
   netstat -tulpn | grep 8001
   
   # Windows PowerShell
   netstat -ano | findstr :8001
   ```

2. **Solutions:**
   - **Option A**: Stop the process using the port
   - **Option B**: Use a different port for VLLM (e.g., 8002) and update `VLLM_BASE_URL` in your `.env` file
   - **Option C**: If the API server is on port 8000, ensure VLLM uses port 8001 (default)

3. **Verify port availability:**
   ```bash
   # Test if port is available
   curl http://localhost:8001/v1/models
   ```

## Comparison: Ollama vs vLLM

| Feature | Ollama | vLLM |
|---------|--------|------|
| **Speed (GPU)** | Medium | **Very Fast** |
| **Speed (CPU)** | Slow | **Not supported** |
| **Setup** | Easy | Moderate |
| **GPU Required** | No | **Yes** |
| **Concurrency** | Limited | **Excellent** |
| **API** | Custom | **OpenAI-compatible** |
| **Best For** | Development, CPU | **Production, GPU** |

## Expected Performance

With vLLM on GPU:
- **Simple queries**: 2-5 seconds
- **Complex queries**: 5-10 seconds
- **Concurrent requests**: Handles many simultaneously

With Ollama on CPU:
- **Simple queries**: 60-120 seconds
- **Complex queries**: 120+ seconds
- **Concurrent requests**: Limited

## Quick Start

```bash
# 1. Install vLLM
pip install vllm

# 2. Start vLLM server (use port 8001 to avoid conflict with API server)
python -m vllm.entrypoints.openai.api_server \
    --model microsoft/Phi-3-mini-4k-instruct \
    --port 8001

# 3. Update .env
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8001
VLLM_MODEL=microsoft/Phi-3-mini-4k-instruct

# 4. Restart API
docker-compose restart api
```

## See Also

- [vLLM Documentation](https://docs.vllm.ai/)
- [Performance Optimization Guide](performance_optimization.md)
- [Ollama Setup Guide](ollama_setup.md)
