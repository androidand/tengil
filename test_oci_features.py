#!/usr/bin/env python3
"""Comprehensive OCI Backend testing script."""
import sys
from tengil.services.proxmox.backends.oci import OCIBackend

def test_create_minimal_nginx():
    """Test creating a minimal nginx container."""
    print("=" * 60)
    print("TEST 1: Create minimal nginx container")
    print("=" * 60)
    
    backend = OCIBackend()
    
    spec = {
        'oci': {
            'image': 'nginx',
            'tag': 'alpine'
        },
        'hostname': 'test-nginx',
        'cores': 1,
        'memory': 512,
        'disk': 4,
        'network': {
            'bridge': 'vmbr0',
            'ip': 'dhcp'
        }
    }
    
    vmid = backend.create_container(spec, storage='tank')
    if vmid:
        print(f"✅ Container created with VMID: {vmid}")
        
        # Start it
        if backend.start_container(vmid):
            print(f"✅ Container {vmid} started successfully")
            return vmid
        else:
            print(f"❌ Failed to start container {vmid}")
            return None
    else:
        print("❌ Failed to create container")
        return None

def test_create_with_mounts():
    """Test creating container with ZFS mounts."""
    print("\n" + "=" * 60)
    print("TEST 2: Create nginx with ZFS mount")
    print("=" * 60)
    
    backend = OCIBackend()
    
    spec = {
        'oci': {
            'image': 'nginx',
            'tag': 'alpine'
        },
        'hostname': 'test-nginx-mounts',
        'cores': 1,
        'memory': 512,
        'disk': 4,
        'network': {
            'bridge': 'vmbr0',
            'ip': 'dhcp'
        },
        'mounts': [
            {
                'source': '/tank/media',
                'target': '/usr/share/nginx/html/media',
                'readonly': True
            }
        ]
    }
    
    vmid = backend.create_container(spec, storage='tank')
    if vmid:
        print(f"✅ Container created with VMID: {vmid}")
        
        # Start it
        if backend.start_container(vmid):
            print(f"✅ Container {vmid} started successfully")
            print("🔍 Verifying mount inside container...")
            import subprocess
            result = subprocess.run(
                ['ssh', 'root@192.168.1.42', f'pct exec {vmid} -- ls -la /usr/share/nginx/html/'],
                capture_output=True,
                text=True
            )
            if 'media' in result.stdout:
                print("✅ Mount verified inside container")
            else:
                print("⚠️ Mount not visible inside container")
            return vmid
        else:
            print(f"❌ Failed to start container {vmid}")
            return None
    else:
        print("❌ Failed to create container")
        return None

def test_lifecycle():
    """Test container lifecycle operations."""
    print("\n" + "=" * 60)
    print("TEST 3: Container lifecycle (stop, start, destroy)")
    print("=" * 60)
    
    backend = OCIBackend()
    
    # Create simple container
    spec = {
        'oci': {
            'image': 'alpine',
            'tag': 'latest'
        },
        'hostname': 'test-lifecycle',
        'cores': 1,
        'memory': 256,
        'disk': 2
    }
    
    vmid = backend.create_container(spec, storage='tank')
    if not vmid:
        print("❌ Failed to create container")
        return False
    
    print(f"✅ Container created with VMID: {vmid}")
    
    # Start
    if backend.start_container(vmid):
        print(f"✅ Container {vmid} started")
    else:
        print(f"❌ Failed to start container {vmid}")
        return False
    
    # Stop
    if backend.stop_container(vmid, timeout=10):
        print(f"✅ Container {vmid} stopped")
    else:
        print(f"❌ Failed to stop container {vmid}")
        return False
    
    # Start again
    if backend.start_container(vmid):
        print(f"✅ Container {vmid} restarted")
    else:
        print(f"❌ Failed to restart container {vmid}")
        return False
    
    # Destroy
    if backend.destroy_container(vmid, purge=True):
        print(f"✅ Container {vmid} destroyed")
    else:
        print(f"❌ Failed to destroy container {vmid}")
        return False
    
    return True

def main():
    """Run all tests."""
    print("🚀 Starting comprehensive OCI Backend tests")
    print("Server: root@192.168.1.42")
    print()
    
    results = {
        'minimal_nginx': None,
        'nginx_with_mounts': None,
        'lifecycle': None
    }
    
    # Test 1: Minimal nginx
    results['minimal_nginx'] = test_create_minimal_nginx()
    
    # Test 2: Nginx with mounts
    results['nginx_with_mounts'] = test_create_with_mounts()
    
    # Test 3: Lifecycle
    results['lifecycle'] = test_lifecycle()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    if results['minimal_nginx']:
        print(f"✅ TEST 1: Minimal nginx container (VMID {results['minimal_nginx']})")
    else:
        print("❌ TEST 1: Failed")
    
    if results['nginx_with_mounts']:
        print(f"✅ TEST 2: Nginx with mounts (VMID {results['nginx_with_mounts']})")
    else:
        print("❌ TEST 2: Failed")
    
    if results['lifecycle']:
        print("✅ TEST 3: Lifecycle operations")
    else:
        print("❌ TEST 3: Failed")
    
    # Cleanup instructions
    print("\n📝 Cleanup commands:")
    if results['minimal_nginx']:
        print(f"   ssh root@192.168.1.42 'pct stop {results['minimal_nginx']} && pct destroy {results['minimal_nginx']} --purge'")
    if results['nginx_with_mounts']:
        print(f"   ssh root@192.168.1.42 'pct stop {results['nginx_with_mounts']} && pct destroy {results['nginx_with_mounts']} --purge'")
    
    success_count = sum(1 for v in results.values() if v)
    print(f"\n🎯 Tests passed: {success_count}/3")
    
    return 0 if success_count == 3 else 1

if __name__ == '__main__':
    sys.exit(main())
