"""Tests for hardware detection."""
import json
from pathlib import Path
import pytest
from tengil.discovery.hwdetect import SystemDetector


class TestSystemDetector:
    """Test hardware detection functionality."""

    def test_detect_cpu_basic(self):
        """Test basic CPU detection."""
        lscpu_output = """
Architecture:            x86_64
CPU op-mode(s):          32-bit, 64-bit
Model name:              Intel(R) Core(TM) i5-13500T
CPU(s):                  20
Thread(s) per core:      2
Core(s) per socket:      14
Socket(s):               1
"""
        detector = SystemDetector(run_cmd=lambda cmd: lscpu_output if 'lscpu' in cmd else "")
        cpu = detector._detect_cpu()
        
        assert cpu['model'] == "Intel(R) Core(TM) i5-13500T"
        assert cpu['cores'] == 14
        assert cpu['threads'] == 28  # 14 cores * 2 threads

    def test_detect_cpu_fallback(self):
        """Test CPU detection fallback when lscpu fails."""
        detector = SystemDetector(run_cmd=lambda cmd: "")
        cpu = detector._detect_cpu()
        
        assert cpu['model'] == "Unknown CPU"
        assert cpu['cores'] == 0
        assert cpu['threads'] == 0

    def test_detect_intel_gpu(self):
        """Test Intel GPU detection via lspci."""
        lspci_output = "00:02.0 VGA compatible controller: Intel Corporation Device 4680 (rev 0c) UHD Graphics 770"
        
        def mock_cmd(cmd):
            if 'intel' in cmd.lower():
                return lspci_output
            return ""
        
        detector = SystemDetector(run_cmd=mock_cmd)
        detector._cmd_exists = lambda cmd: False  # No nvidia-smi
        gpus = detector._detect_gpu()
        
        assert len(gpus) == 1
        assert gpus[0]['type'] == 'intel'
        assert 'UHD Graphics 770' in gpus[0]['model']

    def test_detect_nvidia_gpu(self):
        """Test NVIDIA GPU detection via nvidia-smi."""
        nvidia_output = "NVIDIA GeForce RTX 4090, 535.54.03"
        
        def mock_cmd(cmd):
            if 'nvidia-smi' in cmd:
                return nvidia_output
            return ""
        
        detector = SystemDetector(run_cmd=mock_cmd)
        detector._cmd_exists = lambda cmd: cmd == 'nvidia-smi'
        gpus = detector._detect_gpu()
        
        assert len(gpus) == 1
        assert gpus[0]['type'] == 'nvidia'
        assert gpus[0]['model'] == 'NVIDIA GeForce RTX 4090'
        assert gpus[0]['driver'] == '535.54.03'

    def test_detect_amd_gpu(self):
        """Test AMD GPU detection via lspci."""
        lspci_output = "03:00.0 VGA compatible controller: AMD Radeon RX 7900 XTX"
        
        def mock_cmd(cmd):
            if 'amd' in cmd.lower():
                return lspci_output
            return ""
        
        detector = SystemDetector(run_cmd=mock_cmd)
        detector._cmd_exists = lambda cmd: False
        gpus = detector._detect_gpu()
        
        assert len(gpus) == 1
        assert gpus[0]['type'] == 'amd'
        assert 'Radeon RX 7900 XTX' in gpus[0]['model']

    def test_detect_multiple_gpus(self):
        """Test detection of multiple GPUs (Intel iGPU + NVIDIA dGPU)."""
        def mock_cmd(cmd):
            if 'nvidia-smi' in cmd:
                return "NVIDIA GeForce RTX 3060, 535.54.03"
            elif 'intel' in cmd.lower():
                return "00:02.0 VGA: Intel UHD Graphics 730"
            return ""
        
        detector = SystemDetector(run_cmd=mock_cmd)
        detector._cmd_exists = lambda cmd: cmd == 'nvidia-smi'
        gpus = detector._detect_gpu()
        
        assert len(gpus) == 2
        assert gpus[0]['type'] == 'nvidia'
        assert gpus[1]['type'] == 'intel'

    def test_detect_memory(self):
        """Test memory detection from /proc/meminfo."""
        meminfo_output = "MemTotal:       65536000 kB"
        
        detector = SystemDetector(run_cmd=lambda cmd: meminfo_output if 'meminfo' in cmd else "")
        memory = detector._detect_memory()
        
        assert memory['total_gb'] == 62.5  # 65536000 / 1024 / 1024

    def test_detect_network(self):
        """Test network interface detection."""
        ip_output = "1: lo\n2: eth0\n3: wlan0"
        
        def mock_cmd(cmd):
            if 'ip -o' in cmd:
                return "eth0\nwlan0"
            if 'eth0/operstate' in cmd:
                return "up"
            if 'wlan0/operstate' in cmd:
                return "down"
            return ""
        
        detector = SystemDetector(run_cmd=mock_cmd)
        interfaces = detector._detect_network()
        
        assert len(interfaces) == 2
        assert interfaces[0]['name'] == 'eth0'
        assert interfaces[0]['up'] is True
        assert interfaces[1]['name'] == 'wlan0'
        assert interfaces[1]['up'] is False

    def test_detect_storage(self):
        """Test ZFS pool detection."""
        zpool_output = """tank	9.09T	1.23T	7.86T	ONLINE
rpool	476G	89.2G	387G	ONLINE"""
        
        detector = SystemDetector(run_cmd=lambda cmd: zpool_output if 'zpool' in cmd else "")
        pools = detector._detect_storage()
        
        assert len(pools) == 2
        assert pools[0]['name'] == 'tank'
        assert pools[0]['size'] == '9.09T'
        assert pools[0]['alloc'] == '1.23T'
        assert pools[0]['free'] == '7.86T'
        assert pools[0]['health'] == 'ONLINE'
        
        assert pools[1]['name'] == 'rpool'
        assert pools[1]['health'] == 'ONLINE'

    def test_detect_os(self):
        """Test OS detection from /etc/os-release."""
        kernel = "6.8.12-1-pve"
        detector = SystemDetector(run_cmd=lambda cmd: kernel if 'uname' in cmd else "")
        
        # We can't easily mock file reading in unit test, so just verify the structure
        os_info = detector._detect_os()
        
        assert 'name' in os_info
        assert 'kernel' in os_info
        # On the test system, we'll get actual values
        assert isinstance(os_info['name'], str)
        assert isinstance(os_info['kernel'], str)

    def test_detect_all_integration(self):
        """Test complete system detection."""
        def mock_cmd(cmd):
            if 'lscpu' in cmd:
                return """Model name:              Intel(R) Core(TM) i5-13500T
Core(s) per socket:      14
Socket(s):               1
Thread(s) per core:      2"""
            elif 'nvidia-smi' in cmd:
                return ""
            elif 'intel' in cmd.lower():
                return "00:02.0 VGA: Intel UHD 770"
            elif 'meminfo' in cmd:
                return "MemTotal:       65536000 kB"
            elif 'ip -o' in cmd:
                return "eth0"
            elif 'operstate' in cmd:
                return "up"
            elif 'zpool' in cmd:
                return "tank	9.09T	1.23T	7.86T	ONLINE"
            elif 'uname' in cmd:
                return "6.8.12-1-pve"
            return ""
        
        detector = SystemDetector(run_cmd=mock_cmd)
        detector._cmd_exists = lambda cmd: False
        
        facts = detector.detect_all()
        
        assert 'cpu' in facts
        assert 'gpu' in facts
        assert 'memory' in facts
        assert 'network' in facts
        assert 'storage' in facts
        assert 'os' in facts
        
        assert facts['cpu']['model'] == "Intel(R) Core(TM) i5-13500T"
        assert facts['cpu']['cores'] == 14
        assert len(facts['gpu']) == 1
        assert facts['gpu'][0]['type'] == 'intel'
        assert facts['memory']['total_gb'] == 62.5
        assert len(facts['network']) == 1
        assert len(facts['storage']) == 1

    def test_save_state(self, tmp_path):
        """Test saving system state to JSON."""
        def mock_cmd(cmd):
            if 'lscpu' in cmd:
                return "Model name:              Test CPU\nCore(s) per socket:      4\nSocket(s):               1\nThread(s) per core:      2"
            return ""
        
        detector = SystemDetector(run_cmd=mock_cmd)
        detector._cmd_exists = lambda cmd: False
        
        dest = tmp_path / "system.json"
        result_path = detector.save_state(dest)
        
        assert result_path.exists()
        
        with open(result_path) as f:
            data = json.load(f)
        
        assert 'cpu' in data
        assert 'gpu' in data
        assert data['cpu']['model'] == 'Test CPU'
        assert data['cpu']['cores'] == 4


class TestGPUDetectionEdgeCases:
    """Test edge cases in GPU detection."""

    def test_no_gpu_detected(self):
        """Test when no GPU is detected."""
        detector = SystemDetector(run_cmd=lambda cmd: "")
        detector._cmd_exists = lambda cmd: False
        gpus = detector._detect_gpu()
        
        assert gpus == []

    def test_malformed_nvidia_output(self):
        """Test handling of malformed nvidia-smi output."""
        nvidia_output = "Malformed output"
        
        detector = SystemDetector(run_cmd=lambda cmd: nvidia_output if 'nvidia-smi' in cmd else "")
        detector._cmd_exists = lambda cmd: cmd == 'nvidia-smi'
        gpus = detector._detect_gpu()
        
        # Should not crash, may have empty or partial data
        assert isinstance(gpus, list)

    def test_exception_handling(self):
        """Test that exceptions are handled gracefully."""
        def failing_cmd(cmd):
            raise Exception("Command failed")
        
        detector = SystemDetector(run_cmd=failing_cmd)
        
        # All methods should handle exceptions gracefully
        cpu = detector._detect_cpu()
        assert cpu['model'] in ['Unknown', 'Unknown CPU']
        
        gpus = detector._detect_gpu()
        assert isinstance(gpus, list)
        
        memory = detector._detect_memory()
        assert memory['total_gb'] == 0
        
        network = detector._detect_network()
        assert network == []
        
        storage = detector._detect_storage()
        assert storage == []
