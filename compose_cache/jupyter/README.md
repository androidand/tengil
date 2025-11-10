# Jupyter Notebook Compose

Curated Docker Compose configuration for Jupyter Lab with scientific computing stack.

## Image: jupyter/scipy-notebook

The `jupyter/scipy-notebook` image includes:
- JupyterLab interface
- Python 3.x
- NumPy, SciPy, Pandas
- Matplotlib, seaborn
- scikit-learn
- Jupyter extensions

## Configuration Notes

### Security
**⚠️ Warning**: This configuration disables token/password authentication for local development convenience. For production use, you should:
- Remove `--NotebookApp.token=''` and `--NotebookApp.password=''` from command
- Set a token: `--NotebookApp.token='your-secure-token'`
- Or set password hash in environment

### User Configuration
- Running as `root` to allow `pip install` and `apt-get` inside notebooks
- For production, remove `user: root` and use default `jovyan` user
- Grant sudo via `GRANT_SUDO=yes` if needed

### Volumes
- `/notebooks:/home/jovyan/work` - Mount local notebooks directory
- All work in `/home/jovyan/work` persists to host
- Default working directory in JupyterLab

### Ports
- `8888:8888` - JupyterLab web interface
- Access at: http://localhost:8888

### Environment
- `JUPYTER_ENABLE_LAB=yes` - Use JupyterLab (modern interface) instead of classic notebook
- `GRANT_SUDO=yes` - Allow sudo inside container

## Customization for Tengil

When used in Tengil packages:
- Volume `/notebooks` should map to dataset (e.g., `tank/data/notebooks`)
- Port can be customized per deployment
- Token/password should be set via secrets for production
- Consider resource limits (CPU, memory) for multi-user environments

## Upstream

**No official docker-compose.yml provided by Jupyter project.**

This compose file is based on:
- Official image documentation: https://jupyter-docker-stacks.readthedocs.io/
- Common deployment patterns
- Best practices for local development

## Testing

Test this compose file:
```bash
cd compose_cache/jupyter
docker-compose up -d
# Visit http://localhost:8888
docker-compose down
```

Test with Tengil ComposeResolver:
```python
from tengil.services.docker_compose.resolver import ComposeResolver
resolver = ComposeResolver()
result = resolver.resolve({'cache': 'compose_cache/jupyter/docker-compose.yml'})
print(f"Services: {list(result.content['services'].keys())}")
```
