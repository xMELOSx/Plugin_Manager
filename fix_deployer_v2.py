
path = r'c:\Users\xMELOSx\.gemini\antigravity\scratch\Projects\Plugin_Manager\src\core\link_master\deployer.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = 0
for i in range(len(lines)):
    if skip > 0:
        skip -= 1
        continue
    
    # Target the messy block around 708
    if 'get_mtime(expected_source) if expected_source else 0' in lines[i] and 'res_to_cache' in lines[i+2]:
        # This is the 4-line block we want to replace
        indent = "                  " # 18 spaces? Let's match the 'else:' above it if possible.
        # Line 700 'else:' had some spaces.
        # Actually 18 spaces matches the 'if os.path.exists' block better.
        new_lines.append(indent + "src_m = get_mtime(expected_source) if expected_source else 0\n")
        new_lines.append(indent + "tgt_m = get_mtime(target_link_path)\n")
        new_lines.append(indent + "self._status_cache[cache_key] = (now, src_m, tgt_m, res)\n")
        new_lines.append(indent + "return res\n")
        skip = 3
        continue
    
    new_lines.append(lines[i])

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Surgical fix applied")
