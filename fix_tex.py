import sys
with open(sys.argv[1], "rb") as f:
    raw = bytearray(f.read())

# Fix double backslash sequences: replace 0x5c0x5c with 0x5c
# But preserve \\ sequences that are table row terminators (\\\n, \\\r, \\  \n, \\&)
# Strategy: find ALL double 0x5c -> check context after
# If followed by [a-zA-Z@] -> it's a LaTeX command prefix -> fix
# If followed by \n, \r, space+newline, & -> table row -> keep

i = 0
fixes = 0
while i < len(raw) - 1:
    if raw[i] == 0x5c and raw[i+1] == 0x5c:
        # Check what follows the two backslashes
        if i + 2 < len(raw):
            next_char = chr(raw[i+2])
            if next_char.isalpha() or next_char in '{}':
                # It's a LaTeX command prefix (e.g. \\begin, \\mathbf)
                # Fix: replace 0x5c0x5c with 0x5c
                raw[i] = 0x5c  # keep one backslash
                # Shift everything left by 1
                for j in range(i+1, len(raw)-1):
                    raw[j] = raw[j+1]
                raw.pop()  # remove last byte (now duplicate)
                fixes += 1
                continue  # re-check from same i (single \ now)
            else:
                # Line break or row terminator - keep both
                i += 2
                continue
        else:
            i += 2
    else:
        i += 1

with open(f"{sys.argv[1]}.fixed", "wb") as f:
    f.write(raw)

# Count remaining double backslashes
remaining = 0
i = 0
while i < len(raw) - 1:
    if raw[i] == 0x5c and raw[i+1] == 0x5c:
        remaining += 1
        i += 2
    else:
        i += 1

total_singles = sum(1 for b in raw if b == 0x5c)
print(f"Fixes applied: {fixes}")
print(f"Remaining double backslashes: {remaining}")
print(f"Total single backslashes: {total_singles}")
