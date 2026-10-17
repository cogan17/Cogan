#!/usr/bin/env python3
"""Read an APK's manifest and application label without installing or executing it."""
import io
import struct
import zipfile


def _chunks(data, start, end):
    while start < end:
        kind, header, size = struct.unpack_from("<HHI", data, start)
        if header < 8 or size < header or start + size > end:
            raise ValueError("Invalid Android resource chunk")
        yield kind, header, size, start
        start += size


def _pool(data, offset, header, size):
    count, _, flags, start = struct.unpack_from("<4I", data, offset + 8)
    end = offset + size
    if header < 28 or header + count * 4 > start or start > size:
        raise ValueError("Invalid Android string pool")

    def length(pos, width):
        fmt, mask = ("<B", 0x80) if width == 1 else ("<H", 0x8000)
        value = struct.unpack_from(fmt, data, pos)[0]
        pos += width
        if value & mask:
            value = ((value & (mask - 1)) << (width * 8)) | struct.unpack_from(fmt, data, pos)[0]
            pos += width
        return value, pos

    strings = []
    for index in range(count):
        pos = offset + start + struct.unpack_from("<I", data, offset + header + index * 4)[0]
        if not offset + start <= pos < end:
            raise ValueError("String outside Android string pool")
        if flags & 0x100:
            _, pos = length(pos, 1)
            length_bytes, pos = length(pos, 1)
            encoding = "utf-8"
        else:
            length_chars, pos = length(pos, 2)
            length_bytes, encoding = length_chars * 2, "utf-16-le"
        if pos + length_bytes > end:
            raise ValueError("Truncated Android resource string")
        strings.append(data[pos:pos + length_bytes].decode(encoding))
    return strings


def _root(data, expected):
    kind, header, size = struct.unpack_from("<HHI", data)
    if kind != expected or header < 8 or size != len(data):
        raise ValueError("Invalid Android resource header")
    return _chunks(data, header, size)


def _resource_labels(data, resource, seen=()):
    if resource in seen or len(seen) >= 10:
        raise ValueError("Cyclic application label resource")
    strings, values = [], []
    for kind, header, size, pos in _root(data, 0x0002):
        if kind == 0x0001:
            strings = _pool(data, pos, header, size)
        if kind != 0x0200 or struct.unpack_from("<I", data, pos + 8)[0] != resource >> 24:
            continue
        type_offset = struct.unpack_from("<I", data, pos + 284)[0] if header >= 288 else 0
        for typ, head, length, at in _chunks(data, pos + header, pos + size):
            if typ != 0x0201:
                continue
            type_id, flags, _, count, entries_start = struct.unpack_from("<BBHII", data, at + 8)
            index = resource & 0xffff
            if type_id + type_offset != (resource >> 16) & 0xff:
                continue
            entry_offset = None
            if flags & 1:  # sparse index/offset pairs; offsets are in four-byte units
                for n in range(count):
                    key, value = struct.unpack_from("<HH", data, at + head + n * 4)
                    if key == index:
                        entry_offset = value * 4
                        break
            elif index < count:
                if flags & 2:  # 16-bit offsets, also in four-byte units
                    value = struct.unpack_from("<H", data, at + head + index * 2)[0]
                    entry_offset = None if value == 0xffff else value * 4
                else:
                    value = struct.unpack_from("<I", data, at + head + index * 4)[0]
                    entry_offset = None if value == 0xffffffff else value
            if entry_offset is None:
                continue
            entry = at + entries_start + entry_offset
            if not at + head <= entry <= at + length - 8:
                raise ValueError("Application label entry outside resource table")
            entry_size, entry_flags = struct.unpack_from("<HH", data, entry)
            if entry_flags & 1:
                raise ValueError("Application label is a complex resource")
            if entry_flags & 8:  # compact entries store data type in the high flags byte
                data_type, value = entry_flags >> 8, struct.unpack_from("<I", data, entry + 4)[0]
            else:
                if entry_size < 8 or entry + entry_size + 8 > at + length:
                    raise ValueError("Truncated application label entry")
                _, _, data_type, value = struct.unpack_from("<HBBI", data, entry + entry_size)
            if data_type == 3:
                values.append(strings[value])
            elif data_type == 1:
                values.extend(_resource_labels(data, value, (*seen, resource)))
            else:
                raise ValueError("Application label is not a string")
    if not values:
        raise ValueError("Application label resource not found")
    return values


def apk_identity(payload):
    """Return package, version and every resolved application-label configuration."""
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for name in ("AndroidManifest.xml", "resources.arsc"):
                if archive.getinfo(name).file_size > 64 * 1024 * 1024:
                    raise ValueError("APK metadata is too large")
            data = archive.read("AndroidManifest.xml")
            strings, result = [], {}
            for kind, header, size, pos in _root(data, 0x0003):
                if kind == 0x0001:
                    strings = _pool(data, pos, header, size)
                if kind != 0x0102:
                    continue
                tag = strings[struct.unpack_from("<I", data, pos + 20)[0]]
                if tag not in ("manifest", "application"):
                    continue
                start, stride, count = struct.unpack_from("<HHH", data, pos + 24)
                if stride < 20 or pos + 16 + start + count * stride > pos + size:
                    raise ValueError("Invalid manifest attributes")
                for index in range(count):
                    attr = pos + 16 + start + index * stride
                    _, name, _ = struct.unpack_from("<III", data, attr)
                    _, _, data_type, value = struct.unpack_from("<HBBI", data, attr + 12)
                    key = strings[name]
                    if key not in ("package", "versionName", "versionCode", "label", "name"):
                        continue
                    if data_type == 3:
                        value = strings[value]
                    if tag == "application" and key == "label":
                        result["labels"] = (_resource_labels(archive.read("resources.arsc"), value)
                                            if data_type == 1 else [value])
                    elif tag == "manifest":
                        result[key] = value
            if not result.get("labels") or not result.get("package"):
                raise ValueError("APK application identity is missing")
            return result
    except (struct.error, IndexError, KeyError, UnicodeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Unreadable APK identity: {exc}") from exc


def verify_bakasu_apk(payload):
    identity = apk_identity(payload)
    if set(identity["labels"]) != {"BakaSU"}:
        raise ValueError(f"BakaSU APK required; embedded application label: {identity['labels']!r}. "
                         "Run Cogan Manual Update → update → root-managers.")
    return identity
