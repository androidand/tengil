# Ollama Docker Compose

## Source
Official Docker image: https://hub.docker.com/r/ollama/ollama  
Documentation: https://github.com/ollama/ollama#docker

## Why This Exists
Ollama does **not** provide an official `docker-compose.yml` file - only a Docker image. We created this minimal compose configuration based on their documentation.

## Configuration
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - /root/.ollama:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
```

## What Tengil Uses
- **Volume mount**: `/root/.ollama` - Model storage (managed by Tengil as ZFS dataset)
- **Port**: `11434` - Ollama API endpoint
- **Environment**: `OLLAMA_HOST=0.0.0.0` - Accept connections from all interfaces

## GPU Support
For GPU support, add the appropriate runtime:

### NVIDIA
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

### AMD ROCm
```yaml
devices:
  - /dev/kfd
  - /dev/dri
```

Tengil handles GPU passthrough automatically via `gpu_passthrough: auto` in package definitions.

## Last Verified
2025-11-10 - Confirmed this configuration works with ollama/ollama:latest

##Modifications
None - this is a clean, minimal configuration based on official documentation.
