"""ZFS property profiles for common data types."""

PROFILES = {
    'media': {
        'recordsize': '1M',
        'compression': 'off',
        'atime': 'off',
        'sync': 'standard'
    },
    'documents': {
        'recordsize': '128K',
        'compression': 'zstd',
        'atime': 'off',
        'copies': '2'
    },
    'photos': {
        'recordsize': '1M',
        'compression': 'lz4',  # Light compression for already-compressed JPEGs
        'atime': 'off',
        'copies': '2'
    },
    'backups': {
        'recordsize': '128K',   # Better for varied backup file sizes
        'compression': 'zstd',  # High compression for backups
        'atime': 'off'
    },
    'dev': {
        'recordsize': '128K',
        'compression': 'lz4',
        'atime': 'off'
    },
    'gaming': {
        'recordsize': '128K',
        'compression': 'lz4',
        'atime': 'off',
        'sync': 'standard'
    },
    'roms': {
        'recordsize': '128K',
        'compression': 'lz4',
        'atime': 'off',
        'copies': '2'  # Extra safety for ROM collections
    },
    'ai-models': {
        'recordsize': '1M',
        'compression': 'lz4',
        'atime': 'off',
        'primarycache': 'metadata'  # Models too large for ARC
    },
    'audio': {
        'recordsize': '1M',
        'compression': 'lz4',  # Audio files already compressed
        'atime': 'off',
        'sync': 'standard'
    },
    'video': {
        'recordsize': '1M',
        'compression': 'off',  # Video already compressed, no benefit
        'atime': 'off',
        'sync': 'standard'
    }
}
