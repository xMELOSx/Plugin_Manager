import gettext
import os
import struct

def compile_mo(po_path, mo_path):
    """Simple PO to MO compiler using only standard library."""
    messages = {}
    with open(po_path, 'r', encoding='utf-8') as f:
        msgid = None
        for line in f:
            line = line.strip()
            if line.startswith('msgid '):
                msgid = line[7:-1]
            elif line.startswith('msgstr ') and msgid is not None:
                msgstr = line[8:-1]
                if msgid and msgstr:
                    messages[msgid] = msgstr
                msgid = None
    
    # Sort by msgid
    keys = sorted(messages.keys())
    offsets = []
    ids = b""
    strs = b""
    
    for k in keys:
        v = messages[k]
        offsets.append((len(ids), len(k), len(strs), len(v)))
        ids += k.encode('utf-8') + b"\0"
        strs += v.encode('utf-8') + b"\0"
        
    # Build MO header
    # Magic: 0x950412de
    # Revision: 0
    # Num strings: len(keys)
    # Offset msgids: 28
    # Offset msgstrs: 28 + len(keys)*8
    # Hash size: 0
    # Hash offset: 28 + len(keys)*16
    
    nstrings = len(keys)
    id_start = 28 + nstrings * 16
    str_start = id_start + len(ids)
    
    header = struct.pack("<Iiiiiii", 
                         0x950412de, 0, nstrings, 28, 28 + nstrings * 8, 0, 28 + nstrings * 16)
    
    with open(mo_path, 'wb') as f:
        f.write(header)
        for start, length, _, _ in offsets:
            f.write(struct.pack("<ii", length, id_start + start))
        for _, _, start, length in offsets:
            f.write(struct.pack("<ii", length, str_start + start))
        f.write(ids)
        f.write(strs)

if __name__ == "__main__":
    po = r"config\locale\ja\LC_MESSAGES\linkmaster.po"
    mo = r"config\locale\ja\LC_MESSAGES\linkmaster.mo"
    print(f"Compiling {po} to {mo}...")
    compile_mo(po, mo)
    print("Done.")
