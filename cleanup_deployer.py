
path = r'c:\Users\xMELOSx\.gemini\antigravity\scratch\Projects\Plugin_Manager\src\core\link_master\deployer.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

output = []
skip_next = 0
for i, line in enumerate(lines):
    if skip_next > 0:
        skip_next -= 1
        continue
    
    # Detect redundant/badly indented blocks
    if '# UPDATE CACHE BEFORE RETURN' in line:
        # Check if the next line is indented correctly or not
        next_line = lines[i+1] if i+1 < len(lines) else ""
        if next_line.startswith(' ' * 16 + 'src_m ='):
             # This is a bad block from previous failed edit. Skip it.
             # Look for how many lines to skip (until return or next UPDATE CACHE)
             skip = 1
             while i+skip < len(lines) and not lines[i+skip].strip().startswith('return') and not lines[i+skip].strip().startswith('res_to_cache'):
                 skip += 1
             # If it doesn't end in return, it's definitely garbage
             if not lines[i+skip].strip().startswith('return'):
                 skip_next = skip
                 continue
    
    output.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(output)
print("Cleanup applied successfully")
