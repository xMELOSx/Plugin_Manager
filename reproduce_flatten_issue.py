
import os
import sys
import shutil
import time

# Add src to path
sys.path.append(os.getcwd())

from src.core.link_master.deployer import Deployer

def setup_test_env():
    base = os.path.abspath("test_flatten_env")
    if os.path.exists(base):
        try:
            shutil.rmtree(base)
        except:
            # Retry or ignore
            pass
            
    source = os.path.join(base, "source")
    target = os.path.join(base, "target")
    
    os.makedirs(os.path.join(source, "subdir"), exist_ok=True)
    
    with open(os.path.join(source, "file1.txt"), "w") as f: f.write("content1")
    with open(os.path.join(source, "subdir", "file2.txt"), "w") as f: f.write("content2")
    
    os.makedirs(target, exist_ok=True)
    
    return source, target, base

def run_test():
    source, target, base = setup_test_env()
    print(f"Source: {source}")
    print(f"Target: {target}")
    
    deployer = Deployer("TestApp")
    
    print("--- Deploying with type='flatten' ---")
    success = deployer.deploy_with_rules(source, target, deploy_type='flatten')
    print(f"Deploy Success: {success}")
    
    # Verify files in target
    print("--- Verifying Target Content ---")
    files = os.listdir(target)
    print(f"Files in target: {files}")
    
    expected_files = ["file1.txt", "file2.txt"] # Flattened
    for f in expected_files:
        p = os.path.join(target, f)
        if os.path.exists(p):
            is_link = os.path.islink(p)
            print(f"  {f}: Exists, IsLink={is_link}")
            if is_link:
                print(f"    -> Points to: {os.readlink(p)}")
        else:
            print(f"  {f}: MISSING")

    print("--- Checking Link Status ---")
    status = deployer.get_link_status(target, expected_source=source)
    print(f"Status: {status}")
    
    # Cleanup
    # shutil.rmtree(base)

if __name__ == "__main__":
    run_test()
