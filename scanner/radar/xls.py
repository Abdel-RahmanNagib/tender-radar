"""Minimal reader for old Excel files (.xls, BIFF8 inside an OLE2 container), standard library only.

read_rows(data) returns the first worksheet as a list of rows; each row is a list of cell values
(str, float, bool or None). Excel dates come back as floats: use excel_date() to convert them.
Enough for the tender lists some portals publish as .xls; formulas, styles and charts are ignored.
"""
import struct
from datetime import date, timedelta

_END = 0xFFFFFFFA  # sector numbers at or above this end a chain


def _ole_stream(data, names=("Workbook", "Book")):
    if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("not an Excel 97-2003 (.xls) file")
    ssz = 1 << struct.unpack_from("<H", data, 30)[0]
    msz = 1 << struct.unpack_from("<H", data, 32)[0]
    num_fat, dir_start = struct.unpack_from("<II", data, 44)
    mini_cutoff, minifat_start, _num_minifat, difat_start, num_difat = struct.unpack_from("<IIIII", data, 56)
    per = ssz // 4

    def sector(s):
        off = (s + 1) * ssz
        return data[off:off + ssz]

    difat = list(struct.unpack_from("<109I", data, 76))
    s = difat_start
    for _ in range(num_difat):
        if s >= _END:
            break
        vals = struct.unpack(f"<{per}I", sector(s))
        difat.extend(vals[:-1])
        s = vals[-1]
    fat = []
    for sec in difat[:num_fat]:
        if sec < _END:
            fat.extend(struct.unpack(f"<{per}I", sector(sec)))

    def chain(start, table):
        out, s, seen = [], start, set()
        while s < _END and s < len(table) and s not in seen:
            seen.add(s)
            out.append(s)
            s = table[s]
        return out

    def read(start, size=None):
        b = b"".join(sector(s) for s in chain(start, fat))
        return b if size is None else b[:size]

    dirs = read(dir_start)
    entries = []
    for i in range(0, len(dirs) - 127, 128):
        e = dirs[i:i + 128]
        nlen = struct.unpack_from("<H", e, 64)[0]
        start, size = struct.unpack_from("<II", e, 116)
        entries.append((e[:max(nlen - 2, 0)].decode("utf-16-le", "ignore"), e[66], start, size))
    root = next((x for x in entries if x[1] == 5), None)
    for name, etype, start, size in entries:
        if etype != 2 or name not in names:
            continue
        if size >= mini_cutoff or root is None:
            return read(start, size)
        ministream = read(root[2], root[3])
        minifat = []
        for sec in chain(minifat_start, fat):
            minifat.extend(struct.unpack(f"<{per}I", sector(sec)))
        return b"".join(ministream[m * msz:(m + 1) * msz] for m in chain(start, minifat))[:size]
    raise ValueError("no workbook stream in the file")


def _records(stream):
    pos, n = 0, len(stream)
    while pos + 4 <= n:
        rtype, rlen = struct.unpack_from("<HH", stream, pos)
        yield rtype, stream[pos + 4:pos + 4 + rlen]
        pos += 4 + rlen


def _sst(blocks, count):
    """Shared strings; a string may continue in the next CONTINUE block, which then starts with an option byte."""
    strings, bi, data, pos = [], 0, blocks[0], 8
    for _ in range(count):
        if pos >= len(data) and bi + 1 < len(blocks):
            bi, pos = bi + 1, 0
            data = blocks[bi]
        if pos + 3 > len(data):
            break
        nchars, options = struct.unpack_from("<HB", data, pos)
        pos += 3
        runs = phonetic = 0
        if options & 0x08:
            runs = struct.unpack_from("<H", data, pos)[0]
            pos += 2
        if options & 0x04:
            phonetic = struct.unpack_from("<i", data, pos)[0]
            pos += 4
        parts, got = [], 0
        while True:
            need = nchars - got
            if options & 0x01:
                take = min((len(data) - pos) >> 1, need)
                parts.append(data[pos:pos + 2 * take].decode("utf-16-le", "replace"))
                pos += 2 * take
            else:
                take = min(len(data) - pos, need)
                parts.append(data[pos:pos + take].decode("latin-1"))
                pos += take
            got += take
            if got >= nchars or bi + 1 >= len(blocks):
                break
            bi += 1
            data = blocks[bi]
            options, pos = data[0], 1
        for _r in range(runs):  # rich-text formatting runs, 4 bytes each, may start a new block
            if pos >= len(data) and bi + 1 < len(blocks):
                bi, pos = bi + 1, 0
                data = blocks[bi]
            pos += 4
        pos += phonetic
        while pos > len(data) and bi + 1 < len(blocks):
            pos -= len(data)
            bi += 1
            data = blocks[bi]
        strings.append("".join(parts))
    return strings


def _unicode(data, pos=0):
    nchars, options = struct.unpack_from("<HB", data, pos)
    pos += 3
    if options & 0x08:
        pos += 2
    if options & 0x04:
        pos += 4
    if options & 0x01:
        return data[pos:pos + 2 * nchars].decode("utf-16-le", "replace")
    return data[pos:pos + nchars].decode("latin-1")


def _rk(v):
    num = (v >> 2) - (1 << 30) if v & 0x80000000 else v >> 2
    val = float(num) if v & 0x02 else struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
    return val / 100 if v & 0x01 else val


def read_book(data):
    """(rows of the first worksheet, datemode) — datemode 1 means the 1904 date system."""
    stream = _ole_stream(data)
    sst_blocks, strings, datemode = None, [], 0
    cells, in_sheet, sheet_done, pending_string = {}, False, False, None
    for rtype, rec in _records(stream):
        if sst_blocks is not None:
            if rtype == 0x003C:  # CONTINUE of the shared string table
                sst_blocks.append(rec)
                continue
            strings = _sst(sst_blocks, struct.unpack_from("<I", sst_blocks[0], 4)[0])
            sst_blocks = None
        if rtype == 0x0809:  # BOF
            in_sheet = len(rec) >= 4 and struct.unpack_from("<H", rec, 2)[0] == 0x0010 and not sheet_done
        elif rtype == 0x000A:  # EOF
            if in_sheet:
                in_sheet, sheet_done = False, True
        elif rtype == 0x0022 and len(rec) >= 2:  # DATEMODE
            datemode = struct.unpack_from("<H", rec)[0]
        elif rtype == 0x00FC:  # SST
            sst_blocks = [rec]
        elif not in_sheet:
            continue
        elif rtype == 0x00FD and len(rec) >= 10:  # LABELSST
            r, c, _xf, i = struct.unpack_from("<HHHI", rec)
            cells[(r, c)] = strings[i] if i < len(strings) else ""
        elif rtype == 0x0204 and len(rec) >= 9:  # LABEL
            r, c = struct.unpack_from("<HH", rec)
            cells[(r, c)] = _unicode(rec, 6)
        elif rtype == 0x0203 and len(rec) >= 14:  # NUMBER
            r, c = struct.unpack_from("<HH", rec)
            cells[(r, c)] = struct.unpack_from("<d", rec, 6)[0]
        elif rtype == 0x027E and len(rec) >= 10:  # RK
            r, c, _xf, v = struct.unpack_from("<HHHI", rec)
            cells[(r, c)] = _rk(v)
        elif rtype == 0x00BD and len(rec) >= 6:  # MULRK
            r, c = struct.unpack_from("<HH", rec)
            for k in range((len(rec) - 6) // 6):
                cells[(r, c + k)] = _rk(struct.unpack_from("<I", rec, 4 + 6 * k + 2)[0])
        elif rtype == 0x0205 and len(rec) >= 8:  # BOOLERR
            r, c = struct.unpack_from("<HH", rec)
            cells[(r, c)] = bool(rec[6]) if rec[7] == 0 else None
        elif rtype == 0x0006 and len(rec) >= 14:  # FORMULA: keep the cached result
            r, c = struct.unpack_from("<HH", rec)
            res = rec[6:14]
            if res[6:8] != b"\xff\xff":
                cells[(r, c)] = struct.unpack("<d", res)[0]
            elif res[0] == 0:
                pending_string = (r, c)
            elif res[0] == 1:
                cells[(r, c)] = bool(res[2])
        elif rtype == 0x0207 and pending_string:  # STRING (result of the formula before it)
            cells[pending_string] = _unicode(rec)
            pending_string = None
    if not cells:
        return [], datemode
    nrows = max(r for r, _ in cells) + 1
    ncols = max(c for _, c in cells) + 1
    return [[cells.get((r, c)) for c in range(ncols)] for r in range(nrows)], datemode


def read_rows(data):
    return read_book(data)[0]


def excel_date(value, datemode=0):
    """Excel serial day number → date (None for anything that is not a plausible date)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 1 < value < 2958466:
        return None
    base = date(1904, 1, 1) if datemode else date(1899, 12, 30)
    return base + timedelta(days=int(value))
