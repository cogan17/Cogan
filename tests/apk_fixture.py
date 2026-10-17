"""Small APK metadata fixtures using Android's binary XML/resource formats."""
import io
import struct
import zipfile


def _pool(strings, utf8=True):
    data, offsets = b"", []
    for value in strings:
        offsets.append(len(data))
        encoded = value.encode("utf-8" if utf8 else "utf-16-le")
        data += ((bytes([len(value), len(encoded)]) + encoded + b"\0") if utf8
                 else struct.pack("<H", len(value)) + encoded + b"\0\0")
    data += b"\0" * (-len(data) % 4)
    start = 28 + len(strings) * 4
    return (struct.pack("<HH6I", 1, 28, start + len(data), len(strings), 0, 256 if utf8 else 0, start, 0)
            + struct.pack(f"<{len(strings)}I", *offsets) + data)


def apk_bytes(label="BakaSU", package="com.resukisu.resukisu", version=35231,
              version_name="v4.2.0-rc3", resource=True, utf8=True, entry_flags=0):
    strings = ["manifest", "application", "package", package, "versionName", version_name,
               "versionCode", "label", label]

    def node(tag, attrs):
        data = b"".join(struct.pack("<IIIHBBI", 0xffffffff, name, 0xffffffff, 8, 0, typ, value)
                        for name, typ, value in attrs)
        return (struct.pack("<HHIII", 0x102, 16, 36 + len(data), 1, 0xffffffff)
                + struct.pack("<II6H", 0xffffffff, tag, 20, 20, len(attrs), 0, 0, 0) + data)

    def end(tag):
        return struct.pack("<HH5I", 0x103, 16, 24, 1, 0xffffffff, 0xffffffff, tag)

    xml = (_pool(strings, utf8) + node(0, [(2, 3, 3), (4, 3, 5), (6, 16, version)])
           + node(1, [(7, 1, 0x7f010000)] if resource else [(7, 3, 8)]) + end(1) + end(0))
    manifest = struct.pack("<HHI", 3, 8, 8 + len(xml)) + xml

    type_pool, key_pool = _pool(["string"]), _pool(["app_name"])
    offsets = struct.pack("<HH", 0, 0) if entry_flags & 1 else b"\0\0\0\0"
    entry = struct.pack("<HHIHBBI", 8, 0, 0, 8, 0, 3, 0)
    typ = (struct.pack("<HHIBBHIII", 0x201, 24, 24 + len(offsets) + len(entry),
                       1, entry_flags, 0, 1, 24 + len(offsets), 4) + offsets + entry)
    children = type_pool + key_pool + typ
    package_header = (struct.pack("<HHII", 0x200, 288, 288 + len(children), 0x7f)
                      + "fixture".encode("utf-16-le").ljust(256, b"\0")
                      + struct.pack("<5I", 288, 1, 288 + len(type_pool), 1, 0))
    table = _pool([label], utf8) + package_header + children
    resources = struct.pack("<HHII", 2, 12, 12 + len(table), 1) + table
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("AndroidManifest.xml", manifest)
        archive.writestr("resources.arsc", resources)
    return out.getvalue()
