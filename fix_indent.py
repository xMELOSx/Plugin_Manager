
path = r'c:\Users\xMELOSx\.gemini\antigravity\scratch\Projects\Plugin_Manager\src\core\link_master\deployer.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

import re

# We want to find get_link_status and everything inside it.
# This is a bit complex with regex, let's use a line-by-line parser with indentation tracking.

lines = text.splitlines()
output = []
in_func = False
func_indent = 0

for i, line in enumerate(lines):
    stripped = line.strip()
    indent = len(line) - len(line.lstrip())
    
    if line.lstrip().startswith('def get_link_status('):
        in_func = True
        func_indent = indent
        output.append(line)
        continue
    
    if in_func:
        # Check if we left the function (unindent to func level or less, except empty lines)
        if stripped and indent <= func_indent and i > 0 and not line.lstrip().startswith('def '):
            if not stripped.startswith('"""') and not stripped.startswith('def '):
                # Still in docstring or something? 
                pass
            else:
                in_func = False
        
        # If we are in the function and see a return that is NOT the last one we already handled
        if in_func and stripped.startswith('return ') and 'final_res' not in stripped and i < 800: # safety cap
            # Extract the return value
            val = stripped[7:].strip()
            # Replace with a block
            output.append(' ' * indent + 'res_to_cache = ' + val)
            output.append(' ' * indent + 'src_m = get_mtime(expected_source) if expected_source else 0')
            output.append(' ' * indent + 'tgt_m = get_mtime(target_link_path)')
            output.append(' ' * indent + 'self._status_cache[cache_key] = (now, src_m, tgt_m, res_to_cache)')
            output.append(' ' * indent + 'return res_to_cache')
            continue

    output.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output) + '\n')
print("Transformation applied successfully")
