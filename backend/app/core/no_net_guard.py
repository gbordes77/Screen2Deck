"""
No-Net Guard: Blocks all outgoing network connections when AIRGAP=True.
Ensures true offline operation for demos and testing.
"""

import socket
import os
from typing import Any

# Check if AIRGAP mode is enabled
AIRGAP = os.getenv("AIRGAP", "true").lower() == "true"

class _NoNetSocket(socket.socket):
    """Socket that blocks all outgoing connections in AIRGAP mode."""
    
    def connect(self, address: Any) -> None:
        """Block connection attempts with clear error message."""
        # Allow localhost connections (for Redis, PostgreSQL)
        if isinstance(address, tuple):
            host = address[0]
            if host in ('localhost', '127.0.0.1', '::1', 'redis', 'postgres'):
                return super().connect(address)
        
        raise RuntimeError(
            "🔒 Air-gap active: External network connections are forbidden. "
            f"Attempted connection to: {address}"
        )
    
    def connect_ex(self, address: Any) -> int:
        """Block connection attempts for non-blocking sockets."""
        if isinstance(address, tuple):
            host = address[0]
            if host in ('localhost', '127.0.0.1', '::1', 'redis', 'postgres'):
                return super().connect_ex(address)
        
        # Return error code instead of raising
        return 111  # ECONNREFUSED

def enable_no_net():
    """Enable no-net guard by monkey-patching socket globally."""
    if AIRGAP:
        # Save original socket class for restoration if needed
        if not hasattr(socket, '_original_socket'):
            socket._original_socket = socket.socket
        
        # Replace global socket class
        socket.socket = _NoNetSocket
        
        # Log activation (safe since it's to stderr/stdout)
        print("🔒 No-Net Guard ACTIVATED: External connections blocked")
        return True
    return False

def disable_no_net():
    """Restore original socket behavior (for testing only)."""
    if hasattr(socket, '_original_socket'):
        socket.socket = socket._original_socket
        print("🔓 No-Net Guard DEACTIVATED: Normal network restored")
        return True
    return False

# Auto-enable on import if AIRGAP is set
if __name__ != "__main__":
    enable_no_net()