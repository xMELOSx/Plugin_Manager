
import os

path = r'c:\Users\xMELOSx\.gemini\antigravity\scratch\Projects\Plugin_Manager\src\core\link_master\deployer.py'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_patterns = [
    'src_m = get_mtime(expected_source)',
    'tgt_m = get_mtime(target_link_path)',
    'self._status_cache[cache_key] = (now, src_m, tgt_m, res)',
    'return res'
]

# Specifically lines that were injected with too much indentation (17+ spaces) or inside blocks where they shouldn't be.
# However, the caching logic should only happen once at the end.

# Let's try to remove all occurrences of these 4 consecutive lines if they are indented weirdly.

i = 0
while i < len(lines):
    line = lines[i]
    # Check if this is the start of an injection block
    if 'src_m = get_mtime(expected_source)' in line and line.strip().startswith('src_m ='):
        # Peak next lines
        if i + 3 < len(lines) and 'tgt_m = get_mtime' in lines[i+1] and 'self._status_cache' in lines[i+2] and 'return res' in lines[i+3]:
            # This is definitely an injection block. Skip 4 lines.
            i += 4
            continue
    
    new_lines.append(line)
    i += 1

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print(f"Cleaned {path}")
