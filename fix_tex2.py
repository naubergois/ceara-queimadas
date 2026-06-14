import sys

with open(sys.argv[1], "rb") as f:
    raw = bytearray(f.read())

# Fix remaining double-backslash in LaTeX shorthand commands
# Pattern: 5c5c followed by a non-alpha char (;, |, &, etc.)
# These are doubled LaTeX shorthands: \\; should be \\;  (wait, that's same)
# Actually: original file has 5c5c 3b (two backslashes before ;) = \\; in LaTeX 
# But LaTeX wants \; (single backslash before ; = thick space)
# The double-escaped form is \\; which is wrong, should be \;

# Fixes for 2-byte LaTeX commands
# \\;  -> \;  (thick space)
# \\|  -> \|  (norm/double vert)
# \\, -> \,  (thin space)
# \\! -> \!  (negative thin space)
# \\: -> \:  (medium space)

two_byte_cmds = [
    (b'\\\\;', b'\\;'),
    (b'\\\\|', b'\\|'),
    (b'\\\\,', b'\\,'),
    (b'\\\\!', b'\\!'),
    (b'\\\\:', b'\\:'),
]

for old, new in two_byte_cmds:
    count = raw.count(old)
    if count > 0:
        raw = raw.replace(old, new)
        print(f"Fixed {count}x {old!r} -> {new!r}")

with open(sys.argv[1], "wb") as f:
    f.write(raw)

# Count remaining
remaining = 0
for i in range(len(raw)-1):
    if raw[i]==0x5c and raw[i+1]==0x5c:
        remaining += 1
print(f"\nRemaining double-0x5c sequences: {remaining}")
