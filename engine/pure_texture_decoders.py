"""Pure-Python fallback decoders for the ETC/EAC/ATC family.

These mirror the block layout used by texture2ddecoder and return BGRA8888
bytes, which is what UnityPy's Texture2DConverter expects from
``texture2ddecoder``.  PVRTC, ASTC and Crunch intentionally remain native-only:
their decoders are large and the Raven native library covers them.
"""

from __future__ import annotations

from types import ModuleType

__version__ = "raven-pure-1"

_WRITE_ORDER = (0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15)
_WRITE_ORDER_REV = (15, 11, 7, 3, 14, 10, 6, 2, 13, 9, 5, 1, 12, 8, 4, 0)
_ETC1_MODIFIER = ((2, 8), (5, 17), (9, 29), (13, 42), (18, 60), (24, 80), (33, 106), (47, 183))
_ETC2A_MODIFIER = (
    ((0, 8), (0, 17), (0, 29), (0, 42), (0, 60), (0, 80), (0, 106), (0, 183)),
    _ETC1_MODIFIER,
)
_ETC1_SUBBLOCK = (
    (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1),
    (0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1),
)
_ETC2_DISTANCE = (3, 6, 11, 16, 23, 32, 41, 64)
_ETC2_ALPHA_MOD = (
    (-3, -6, -9, -15, 2, 5, 8, 14),
    (-3, -7, -10, -13, 2, 6, 9, 12),
    (-2, -5, -8, -13, 1, 4, 7, 12),
    (-2, -4, -6, -13, 1, 3, 5, 12),
    (-3, -6, -8, -12, 2, 5, 7, 11),
    (-3, -7, -9, -11, 2, 6, 8, 10),
    (-4, -7, -8, -11, 3, 6, 7, 10),
    (-3, -5, -8, -11, 2, 4, 7, 10),
    (-2, -6, -8, -10, 1, 5, 7, 9),
    (-2, -5, -8, -10, 1, 4, 7, 9),
    (-2, -4, -8, -10, 1, 3, 7, 9),
    (-2, -5, -7, -10, 1, 4, 6, 9),
    (-3, -4, -7, -10, 2, 3, 6, 9),
    (-1, -2, -3, -10, 0, 1, 2, 9),
    (-4, -6, -8, -9, 3, 5, 7, 8),
    (-3, -5, -7, -9, 2, 4, 6, 8),
)


def _clamp(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def _px(r: int, g: int, b: int, a: int = 255) -> bytearray:
    return bytearray((b & 0xFF, g & 0xFF, r & 0xFF, a & 0xFF))


def _apply(c, m: int, transparent: bool = False) -> bytearray:
    return _px(_clamp(c[0] + m), _clamp(c[1] + m), _clamp(c[2] + m), 0 if transparent else 255)


def _decode_image(data, width: int, height: int, block_bytes: int, block_fn) -> bytes:
    raw = bytes(data)
    if width <= 0 or height <= 0:
        raise ValueError("texture dimensions must be positive")
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    needed = blocks_x * blocks_y * block_bytes
    if len(raw) < needed:
        raise ValueError(f"texture data too short: {len(raw)} < {needed}")
    out = bytearray(width * height * 4)
    offset = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            block = block_fn(raw[offset : offset + block_bytes])
            offset += block_bytes
            for y in range(4):
                yy = by * 4 + y
                if yy >= height:
                    break
                for x in range(4):
                    xx = bx * 4 + x
                    if xx >= width:
                        break
                    src = block[y * 4 + x]
                    dst = (yy * width + xx) * 4
                    out[dst : dst + 4] = src
    return bytes(out)


def _etc1_block(data: bytes):
    code = (data[3] >> 5, (data[3] >> 2) & 7)
    table = _ETC1_SUBBLOCK[data[3] & 1]
    c = [[0, 0, 0], [0, 0, 0]]
    if data[3] & 2:
        for i in range(3):
            base = data[i] & 0xF8
            delta = ((data[i] << 3) & 0x18) - ((data[i] << 3) & 0x20)
            c[0][i] = base | (base >> 5)
            second = (base + delta) & 0xFF
            c[1][i] = second | (second >> 5)
    else:
        for i in range(3):
            c[0][i] = (data[i] & 0xF0) | (data[i] >> 4)
            c[1][i] = (data[i] & 0x0F) | ((data[i] << 4) & 0xFF)
    out = [None] * 16
    j = (data[6] << 8) | data[7]
    k = (data[4] << 8) | data[5]
    for i in range(16):
        s = table[i]
        m = _ETC1_MODIFIER[code[s]][j & 1]
        out[_WRITE_ORDER[i]] = _apply(c[s], -m if (k & 1) else m)
        j >>= 1
        k >>= 1
    return out


def _etc2_t_block(data: bytes, punchthrough: bool = False):
    c0 = [
        ((data[0] << 3) & 0xC0) | ((data[0] << 4) & 0x30) | ((data[0] >> 1) & 0x0C) | (data[0] & 3),
        (data[1] & 0xF0) | (data[1] >> 4),
        (data[1] & 0x0F) | ((data[1] << 4) & 0xFF),
    ]
    c1 = [
        (data[2] & 0xF0) | (data[2] >> 4),
        (data[2] & 0x0F) | ((data[2] << 4) & 0xFF),
        (data[3] & 0xF0) | (data[3] >> 4),
    ]
    d = _ETC2_DISTANCE[((data[3] >> 1) & 6) | (data[3] & 1)]
    color_set = [_apply(c0, 0), _apply(c1, d), _apply(c1, 0), _apply(c1, -d)]
    out = [None] * 16
    j = (data[6] << 8) | data[7]
    k = ((data[4] << 8) | data[5]) << 1
    for i in range(16):
        index = (k & 2) | (j & 1)
        px = bytearray(color_set[index])
        if punchthrough and index == 2:
            px[3] = 0
        out[_WRITE_ORDER[i]] = px
        j >>= 1
        k >>= 1
    return out


def _etc2_h_block(data: bytes, punchthrough: bool = False):
    c0 = [0, 0, 0]
    c1 = [0, 0, 0]
    c0[0] = ((data[0] << 1) & 0xF0) | ((data[0] >> 3) & 0x0F)
    c0[1] = ((data[0] << 5) & 0xE0) | (data[1] & 0x10)
    c0[1] |= c0[1] >> 4
    c0[2] = (data[1] & 8) | ((data[1] << 1) & 6) | (data[2] >> 7)
    c0[2] = (c0[2] | ((c0[2] << 4) & 0xFF)) & 0xFF
    c1[0] = ((data[2] << 1) & 0xF0) | ((data[2] >> 3) & 0x0F)
    c1[1] = ((data[2] << 5) & 0xE0) | ((data[3] >> 3) & 0x10)
    c1[1] |= c1[1] >> 4
    c1[2] = ((data[3] << 1) & 0xF0) | ((data[3] >> 3) & 0x0F)
    d = (data[3] & 4) | ((data[3] << 1) & 2)
    if c0[0] > c1[0] or (c0[0] == c1[0] and (c0[1] > c1[1] or (c0[1] == c1[1] and c0[2] >= c1[2]))):
        d += 1
    d = _ETC2_DISTANCE[d]
    color_set = [_apply(c0, d), _apply(c0, -d), _apply(c1, d), _apply(c1, -d)]
    out = [None] * 16
    j = (data[6] << 8) | data[7]
    k = ((data[4] << 8) | data[5]) << 1
    for i in range(16):
        index = (k & 2) | (j & 1)
        px = bytearray(color_set[index])
        if punchthrough and index == 2:
            px[3] = 0
        out[_WRITE_ORDER[i]] = px
        j >>= 1
        k >>= 1
    return out


def _etc2_planar_block(data: bytes):
    c = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    c[0][0] = ((data[0] << 1) & 0xFC) | ((data[0] >> 5) & 3)
    c[0][1] = ((data[0] << 7) & 0x80) | (data[1] & 0x7E) | (data[0] & 1)
    c[0][2] = ((data[1] << 7) & 0x80) | ((data[2] << 2) & 0x60) | ((data[2] << 3) & 0x18) | ((data[3] >> 5) & 4)
    c[0][2] |= c[0][2] >> 6
    c[1][0] = ((data[3] << 1) & 0xF8) | ((data[3] << 2) & 4) | ((data[3] >> 5) & 3)
    c[1][1] = (data[4] & 0xFE) | (data[4] >> 7)
    c[1][2] = ((data[4] << 7) & 0x80) | ((data[5] >> 1) & 0x7C)
    c[1][2] |= c[1][2] >> 6
    c[2][0] = ((data[5] << 5) & 0xE0) | ((data[6] >> 3) & 0x1C) | ((data[5] >> 1) & 3)
    c[2][1] = ((data[6] << 3) & 0xF8) | ((data[7] >> 5) & 6) | ((data[6] >> 4) & 1)
    c[2][2] = ((data[7] << 2) | ((data[7] >> 4) & 3)) & 0xFF
    out = [None] * 16
    i = 0
    for y in range(4):
        for x in range(4):
            r = _clamp((x * (c[1][0] - c[0][0]) + y * (c[2][0] - c[0][0]) + 4 * c[0][0] + 2) >> 2)
            g = _clamp((x * (c[1][1] - c[0][1]) + y * (c[2][1] - c[0][1]) + 4 * c[0][1] + 2) >> 2)
            b = _clamp((x * (c[1][2] - c[0][2]) + y * (c[2][2] - c[0][2]) + 4 * c[0][2] + 2) >> 2)
            out[i] = _px(r, g, b, 255)
            i += 1
    return out


def _etc2_differential_block(data: bytes, punchthrough: bool = False):
    code = (data[3] >> 5, (data[3] >> 2) & 7)
    table = _ETC1_SUBBLOCK[data[3] & 1]
    c = [[0, 0, 0], [0, 0, 0]]
    for i in range(3):
        base = data[i] & 0xF8
        delta = ((data[i] << 3) & 0x18) - ((data[i] << 3) & 0x20)
        c[0][i] = base | (base >> 5)
        second = base + delta
        c[1][i] = second | (second >> 5)
    out = [None] * 16
    j = (data[6] << 8) | data[7]
    k = (data[4] << 8) | data[5]
    obaq = (data[3] >> 1) & 1
    for i in range(16):
        s = table[i]
        if punchthrough:
            m = _ETC2A_MODIFIER[obaq][code[s]][j & 1]
            transparent = (not obaq) and (k & 1) and not (j & 1)
        else:
            m = _ETC1_MODIFIER[code[s]][j & 1]
            transparent = False
        out[_WRITE_ORDER[i]] = _apply(c[s], -m if (k & 1) else m, transparent)
        j >>= 1
        k >>= 1
    return out


def _etc2_individual_block(data: bytes):
    code = (data[3] >> 5, (data[3] >> 2) & 7)
    table = _ETC1_SUBBLOCK[data[3] & 1]
    c = [[0, 0, 0], [0, 0, 0]]
    for i in range(3):
        c[0][i] = (data[i] & 0xF0) | (data[i] >> 4)
        c[1][i] = (data[i] & 0x0F) | ((data[i] << 4) & 0xFF)
    out = [None] * 16
    j = (data[6] << 8) | data[7]
    k = (data[4] << 8) | data[5]
    for i in range(16):
        s = table[i]
        m = _ETC1_MODIFIER[code[s]][j & 1]
        out[_WRITE_ORDER[i]] = _apply(c[s], -m if (k & 1) else m)
        j >>= 1
        k >>= 1
    return out


def _etc2_block(data: bytes, punchthrough: bool = False):
    if not punchthrough and not (data[3] & 2):
        return _etc2_individual_block(data)
    r = data[0] & 0xF8
    dr = ((data[0] << 3) & 0x18) - ((data[0] << 3) & 0x20)
    g = data[1] & 0xF8
    dg = ((data[1] << 3) & 0x18) - ((data[1] << 3) & 0x20)
    b = data[2] & 0xF8
    db = ((data[2] << 3) & 0x18) - ((data[2] << 3) & 0x20)
    if r + dr < 0 or r + dr > 255:
        return _etc2_t_block(data, punchthrough and not ((data[3] >> 1) & 1))
    if g + dg < 0 or g + dg > 255:
        return _etc2_h_block(data, punchthrough and not ((data[3] >> 1) & 1))
    if b + db < 0 or b + db > 255:
        return _etc2_planar_block(data)
    return _etc2_differential_block(data, punchthrough)


def _etc2a8_block(data: bytes):
    out = _etc2_block(data[8:16], punchthrough=False)
    if data[1] & 0xF0:
        multiplier = data[1] >> 4
        table = _ETC2_ALPHA_MOD[data[1] & 0x0F]
        l = int.from_bytes(data[0:8], "big")
        for i in range(16):
            out[_WRITE_ORDER_REV[i]][3] = _clamp(data[0] + multiplier * table[l & 7])
            l >>= 3
    else:
        for px in out:
            px[3] = data[0]
    return out


def _eac_channel_block(data: bytes, channel: int, signed: bool, out):
    multiplier = (data[1] >> 1) & 0x78
    if multiplier == 0:
        multiplier = 1
    table = _ETC2_ALPHA_MOD[data[1] & 0x0F]
    l = int.from_bytes(data[0:8], "big")
    base = data[0] - 256 if signed and data[0] >= 128 else data[0]
    for i in range(16):
        if signed:
            val = base * 8 + multiplier * table[l & 7] + 1023
        else:
            val = data[0] * 8 + multiplier * table[l & 7] + 4
        out[_WRITE_ORDER_REV[i]][channel] = 0 if val < 0 else 255 if val >= 2048 else val >> 3
        l >>= 3
    return out


def _eac_block(data: bytes, signed: bool, rg: bool):
    out = [_px(0, 0, 0, 255) for _ in range(16)]
    _eac_channel_block(data[0:8], 2, signed, out)
    if rg:
        _eac_channel_block(data[8:16], 1, signed, out)
    return out


def _expand_quantized(v: int, bits: int) -> int:
    v = (v << (8 - bits)) & 0xFF
    return v | (v >> bits)


def _bc3_alpha(data: bytes, out, channel: int):
    a = [data[0], data[1], 0, 0, 0, 0, 0, 0]
    if a[0] > a[1]:
        a[2] = (a[0] * 6 + a[1]) // 7
        a[3] = (a[0] * 5 + a[1] * 2) // 7
        a[4] = (a[0] * 4 + a[1] * 3) // 7
        a[5] = (a[0] * 3 + a[1] * 4) // 7
        a[6] = (a[0] * 2 + a[1] * 5) // 7
        a[7] = (a[0] + a[1] * 6) // 7
    else:
        a[2] = (a[0] * 4 + a[1]) // 5
        a[3] = (a[0] * 3 + a[1] * 2) // 5
        a[4] = (a[0] * 2 + a[1] * 3) // 5
        a[5] = (a[0] + a[1] * 4) // 5
        a[6] = 0
        a[7] = 255
    d = int.from_bytes(data[0:8], "little") >> 16
    for i in range(16):
        out[i][channel] = a[d & 7]
        d >>= 3
    return out


def _atc_block(src: bytes):
    colors = [0] * 16
    c0 = src[0] | (src[1] << 8)
    c1 = src[2] | (src[3] << 8)
    if (c0 & 0x8000) == 0:
        colors[0] = _expand_quantized((c0 >> 0) & 0x1F, 5)
        colors[1] = _expand_quantized((c0 >> 5) & 0x1F, 5)
        colors[2] = _expand_quantized((c0 >> 10) & 0x1F, 5)
        colors[12] = _expand_quantized((c1 >> 0) & 0x1F, 5)
        colors[13] = _expand_quantized((c1 >> 5) & 0x3F, 6)
        colors[14] = _expand_quantized((c1 >> 11) & 0x1F, 5)
        for i in range(3):
            colors[4 + i] = (5 * colors[i] + 3 * colors[12 + i]) // 8
            colors[8 + i] = (3 * colors[i] + 5 * colors[12 + i]) // 8
    else:
        colors[8] = _expand_quantized((c0 >> 0) & 0x1F, 5)
        colors[9] = _expand_quantized((c0 >> 5) & 0x1F, 5)
        colors[10] = _expand_quantized((c0 >> 10) & 0x1F, 5)
        colors[12] = _expand_quantized((c1 >> 0) & 0x1F, 5)
        colors[13] = _expand_quantized((c1 >> 5) & 0x3F, 6)
        colors[14] = _expand_quantized((c1 >> 11) & 0x1F, 5)
        for i in range(3):
            colors[4 + i] = max(0, colors[8 + i] - colors[12 + i] // 4)
    out = [None] * 16
    for i in range(16):
        bitpos = 32 + i * 2
        idx = ((src[bitpos >> 3] >> (bitpos & 7)) & 3) * 4
        out[i] = _px(colors[idx + 2], colors[idx + 1], colors[idx + 0], 255)
    return out


def _atc_rgba8_block(data: bytes):
    out = _atc_block(data[8:16])
    return _bc3_alpha(data[0:8], out, 3)


def decode_etc1(data, width, height):
    return _decode_image(data, width, height, 8, _etc1_block)


def decode_etc2(data, width, height):
    return _decode_image(data, width, height, 8, lambda b: _etc2_block(b, False))


def decode_etc2a1(data, width, height):
    return _decode_image(data, width, height, 8, lambda b: _etc2_block(b, True))


def decode_etc2a8(data, width, height):
    return _decode_image(data, width, height, 16, _etc2a8_block)


def decode_eacr(data, width, height):
    return _decode_image(data, width, height, 8, lambda b: _eac_block(b, False, False))


def decode_eacr_signed(data, width, height):
    return _decode_image(data, width, height, 8, lambda b: _eac_block(b, True, False))


def decode_eacrg(data, width, height):
    return _decode_image(data, width, height, 16, lambda b: _eac_block(b, False, True))


def decode_eacrg_signed(data, width, height):
    return _decode_image(data, width, height, 16, lambda b: _eac_block(b, True, True))


def decode_atc_rgb4(data, width, height):
    return _decode_image(data, width, height, 8, _atc_block)


def decode_atc_rgba8(data, width, height):
    return _decode_image(data, width, height, 16, _atc_rgba8_block)


def _native_only(name: str):
    def _raise(*args, **kwargs):
        raise RuntimeError(f"{name} requires libraven_texture2ddecoder.so")

    return _raise


decode_bc1 = _native_only("decode_bc1")
decode_bc3 = _native_only("decode_bc3")
decode_bc4 = _native_only("decode_bc4")
decode_bc5 = _native_only("decode_bc5")
decode_bc6 = _native_only("decode_bc6")
decode_bc7 = _native_only("decode_bc7")
decode_pvrtc = _native_only("decode_pvrtc")
decode_astc = _native_only("decode_astc")
unpack_crunch = _native_only("unpack_crunch")
unpack_unity_crunch = _native_only("unpack_unity_crunch")


def as_module() -> ModuleType:
    module = ModuleType("texture2ddecoder")
    module.__version__ = __version__
    for name in (
        "decode_bc1",
        "decode_bc3",
        "decode_bc4",
        "decode_bc5",
        "decode_bc6",
        "decode_bc7",
        "decode_atc_rgb4",
        "decode_atc_rgba8",
        "decode_etc1",
        "decode_etc2",
        "decode_etc2a1",
        "decode_etc2a8",
        "decode_eacr",
        "decode_eacr_signed",
        "decode_eacrg",
        "decode_eacrg_signed",
        "decode_astc",
        "decode_pvrtc",
        "unpack_crunch",
        "unpack_unity_crunch",
    ):
        setattr(module, name, globals()[name])
    return module
