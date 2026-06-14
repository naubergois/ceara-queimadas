import sys, re

with open(sys.argv[1], "rb") as f:
    raw = f.read()

# Find all remaining double-backslash sequences with context
lines = raw.split(b"\n")
count = 0
for i, line in enumerate(lines):
    for j in range(len(line)-1):
        if line[j]==0x5c and line[j+1]==0x5c:
            count += 1
            if count <= 30:
                ctx = line[max(0,j-3):min(len(line),j+25)]
                print(f"Line {i+1} col {j}: {ctx.decode('latin1', errors='replace')}")
            break

print(f"\nTotal lines with double-backslash: {count}")
