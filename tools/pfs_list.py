import struct, sys, zlib

def read_pfs(path):
    data = open(path, "rb").read()
    dir_off, magic = struct.unpack_from("<I4s", data, 0)
    assert magic == b"PFS ", magic
    count = struct.unpack_from("<I", data, dir_off)[0]
    entries = []
    for i in range(count):
        crc, off, size = struct.unpack_from("<III", data, dir_off + 4 + i * 12)
        entries.append((crc, off, size))
    def read_blocks(off, inflated_size):
        out = b""
        p = off
        while len(out) < inflated_size:
            deflen, inflen = struct.unpack_from("<II", data, p)
            p += 8
            out += zlib.decompress(data[p:p + deflen])
            p += deflen
        return out
    # filename directory = entry with crc 0x61580AC9
    names = []
    for crc, off, size in entries:
        if crc == 0x61580AC9:
            blob = read_blocks(off, size)
            n = struct.unpack_from("<I", blob, 0)[0]
            p = 4
            for _ in range(n):
                ln = struct.unpack_from("<I", blob, p)[0]
                p += 4
                names.append(blob[p:p + ln - 1].decode("latin1"))
                p += ln
    return names, entries, read_blocks

if __name__ == "__main__":
    names, entries, _ = read_pfs(sys.argv[1])
    print(len(names), "files:")
    for n in sorted(names):
        print(" ", n)
