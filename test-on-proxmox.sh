#!/bin/bash
# Quick test script to validate Tengil installation on Proxmox

echo "=== Testing Tengil Installation ==="
echo ""

# Test 1: Check if tg command exists
echo "1. Testing tg command..."
if command -v tg &> /dev/null; then
    echo "   ✅ tg command found"
else
    echo "   ❌ tg command not found - run: source ~/.bashrc"
    exit 1
fi

# Test 2: Check version
echo ""
echo "2. Testing tg version..."
tg version || echo "   ❌ Failed"

# Test 3: List packages
echo ""
echo "3. Testing package list..."
tg packages list | head -20

# Test 4: Check hardware detection
echo ""
echo "4. Testing hardware detection..."
tg doctor | head -30

# Test 5: Check if on Proxmox
echo ""
echo "5. Checking Proxmox environment..."
if [ -f /etc/pve/.version ]; then
    echo "   ✅ Running on Proxmox VE $(cat /etc/pve/.version)"
else
    echo "   ⚠️  Not on Proxmox (expected for testing)"
fi

# Test 6: Check ZFS pools
echo ""
echo "6. Checking ZFS pools..."
if command -v zpool &> /dev/null; then
    zpool list || echo "   ⚠️  No ZFS pools found"
else
    echo "   ⚠️  ZFS not installed"
fi

echo ""
echo "=== Test Complete ==="
echo ""
echo "Next steps:"
echo "  cd ~/tengil-configs"
echo "  tg packages show nas-basic"
echo "  tg init --package nas-basic"
echo "  tg diff"
