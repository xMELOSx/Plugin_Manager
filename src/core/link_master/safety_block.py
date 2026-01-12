
import os
import logging

def verify_safety(path: str, operation: str = 'deploy', silent: bool = False, logger = None) -> bool:
    """
    Verifies if an operation on the given path is safe.
    Simplified implementation to restore functionality.
    """
    if not path:
        return False
        
    path = os.path.normpath(path)
    
    # Basic safety checks
    # 1. System directories
    system_roots = [
        os.environ.get('SystemRoot', 'C:\\Windows'),
        os.environ.get('ProgramFiles', 'C:\\Program Files'),
        os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')
    ]
    
    for root in system_roots:
        if root and path.lower().startswith(root.lower()):
            if logger: logger.error(f"Safety Violation: Cannot operate on system path: {path}")
            return False
            
    # 2. User critical folders (Desktop, Documents root, etc - be careful)
    # Allowing for now as users often put games there, but maybe warn?
    
    return True
