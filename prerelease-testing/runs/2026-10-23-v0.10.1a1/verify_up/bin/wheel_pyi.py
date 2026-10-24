"""List .pyi members of a wheel (or compare two wheels' .pyi members by content).

Usage: wheel_pyi.py WHEEL            -> prints count and each .pyi path
       wheel_pyi.py WHEEL_A WHEEL_B  -> prints missing/extra/differing .pyi between the two
"""
import hashlib, sys, zipfile

def stubs(path):
    z = zipfile.ZipFile(path)
    return {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.endswith(".pyi")}

a = stubs(sys.argv[1])
if len(sys.argv) == 2:
    print(f"{sys.argv[1]}: {len(a)} .pyi")
    for n in sorted(a):
        print("  ", n)
    sys.exit(0)
b = stubs(sys.argv[2])
only_a = sorted(set(a) - set(b)); only_b = sorted(set(b) - set(a))
diff = sorted(n for n in a if n in b and a[n] != b[n])
print(f"A={sys.argv[1]} ({len(a)} .pyi)\nB={sys.argv[2]} ({len(b)} .pyi)")
print(f"only in A: {len(only_a)} {only_a}\nonly in B: {len(only_b)} {only_b}\ncontent differs: {len(diff)} {diff}")
sys.exit(1 if (only_a or only_b or diff) else 0)
