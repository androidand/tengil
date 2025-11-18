"""Dataset discovery helpers for existing ZFS infrastructure."""
from __future__ import annotations

from typing import Dict, List, Optional

from tengil.core.logger import get_logger
from tengil.core.zfs_manager import ZFSManager
from tengil.services.nas.smb import SMBManager
from tengil.services.nas.nfs import NFSManager

logger = get_logger(__name__)


class DatasetDiscovery:
    """Discover datasets, inferred profiles, and NAS shares."""

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.zfs = ZFSManager(mock=mock)
        self.smb = SMBManager(mock=mock)
        self.nfs = NFSManager(mock=mock)

    def discover_pool(self, pool: str) -> Dict[str, Dict]:
        """Return dataset configuration suggestions for a pool."""
        datasets = {}
        try:
            zfs_state = self.zfs.list_datasets(pool)
        except FileNotFoundError:
            logger.warning("zfs command not available; cannot discover datasets")
            return {}

        if not zfs_state:
            return {}

        smb_index = self._index_smb_shares()
        nfs_exports = self.nfs.parse_nfs_exports()

        prefix = f"{pool}/"
        for full_name, info in zfs_state.items():
            if full_name == pool or not full_name.startswith(prefix):
                continue

            dataset_name = full_name[len(prefix):]
            if not dataset_name:
                continue

            dataset_path = f"/{full_name}"
            config = self._build_dataset_config(dataset_name, dataset_path, info, smb_index, nfs_exports)
            datasets[dataset_name] = config

        return datasets

    def _index_smb_shares(self) -> Dict[str, Dict]:
        """Return parsed Samba shares keyed by share name."""
        try:
            shares = self.smb.parse_smb_conf()
            return shares or {}
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to parse smb.conf: %s", exc)
            return {}

    def _build_dataset_config(
        self,
        dataset_name: str,
        dataset_path: str,
        info: Dict[str, Optional[str]],
        smb_index: Dict[str, Dict],
        nfs_exports: Dict[str, Dict],
    ) -> Dict[str, Dict]:
        """Create a dataset configuration entry from discovered state."""
        config: Dict[str, Dict] = {}

        profile = self._infer_profile(info.get('compression'), info.get('recordsize'))
        config['profile'] = profile

        zfs_props = {}
        for key in ('compression', 'recordsize', 'atime', 'sync'):
            value = info.get(key)
            if value not in (None, '', '-'):
                zfs_props[key] = value
        if zfs_props:
            config['zfs'] = zfs_props

        shares = {}
        smb_matches = self._match_smb_shares(dataset_path, smb_index)
        if smb_matches:
            if len(smb_matches) == 1:
                shares['smb'] = {'name': smb_matches[0], '_from_consumer': True}
            else:
                shares['smb'] = [
                    {'name': share_name, '_from_consumer': True}
                    for share_name in smb_matches
                ]

        if dataset_path in nfs_exports:
            shares['nfs'] = True

        if shares:
            config['shares'] = shares

        return config

    def _match_smb_shares(self, dataset_path: str, smb_index: Dict[str, Dict]) -> List[str]:
        """Return share names whose path maps to the dataset path."""
        matches: List[str] = []
        for name, share in smb_index.items():
            path = share.get('path')
            if path and path.rstrip('/') == dataset_path.rstrip('/'):
                matches.append(name)
        return matches

    def _infer_profile(self, compression: Optional[str], recordsize: Optional[str]) -> str:
        """Infer Tengil profile from dataset properties."""
        compression_normalized = (compression or '').lower()
        recordsize_normalized = (recordsize or '').upper()

        if recordsize_normalized in {'1M', '1024K'} and compression_normalized in {'off', '', 'lz4'}:
            return 'media'
        if 'zstd' in compression_normalized:
            return 'backups'
        if recordsize_normalized in {'128K', '131072'} and compression_normalized not in {'off', ''}:
            return 'documents'
        return 'media'