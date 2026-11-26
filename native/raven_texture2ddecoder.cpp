#include "raven_texture2ddecoder.h"

#include <cstdint>
#include <cstdlib>
#include <cstring>

#include "astc.h"
#include "atc.h"
#include "bcn.h"
#include "crunch.h"
#include "etc.h"
#include "pvrtc.h"
#include "unitycrunch.h"

namespace {

bool valid_image_args(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out,
                      uint32_t out_size) {
    if (!data || !out || width <= 0 || height <= 0) return false;
    const uint64_t needed_out = static_cast<uint64_t>(width) * static_cast<uint64_t>(height) * 4u;
    return data_size > 0 && needed_out == out_size;
}

uint32_t blocks_4x4_size(int32_t width, int32_t height, uint32_t bytes_per_block) {
    const uint64_t blocks_x = (static_cast<uint64_t>(width) + 3u) / 4u;
    const uint64_t blocks_y = (static_cast<uint64_t>(height) + 3u) / 4u;
    const uint64_t size = blocks_x * blocks_y * bytes_per_block;
    return size > 0xffffffffull ? 0xffffffffu : static_cast<uint32_t>(size);
}

bool has_block_data(uint32_t data_size, int32_t width, int32_t height, uint32_t bytes_per_block) {
    return data_size >= blocks_4x4_size(width, height, bytes_per_block);
}

uint32_t pvrtc_size(int32_t width, int32_t height, int32_t is2bpp) {
    const uint32_t block_width = is2bpp ? 8u : 4u;
    const uint64_t blocks_x = (static_cast<uint64_t>(width) + block_width - 1u) / block_width;
    const uint64_t blocks_y = (static_cast<uint64_t>(height) + 3u) / 4u;
    const uint64_t size = blocks_x * blocks_y * 8u;
    return size > 0xffffffffull ? 0xffffffffu : static_cast<uint32_t>(size);
}

uint32_t astc_size(int32_t width, int32_t height, int32_t block_width, int32_t block_height) {
    if (block_width <= 0 || block_height <= 0) return 0xffffffffu;
    const uint64_t blocks_x = (static_cast<uint64_t>(width) + static_cast<uint64_t>(block_width) - 1u) / static_cast<uint64_t>(block_width);
    const uint64_t blocks_y = (static_cast<uint64_t>(height) + static_cast<uint64_t>(block_height) - 1u) / static_cast<uint64_t>(block_height);
    const uint64_t size = blocks_x * blocks_y * 16u;
    return size > 0xffffffffull ? 0xffffffffu : static_cast<uint32_t>(size);
}

using DecodeLong = int (*)(const uint8_t *, long, long, uint32_t *);
using DecodeU32 = int (*)(const uint8_t *, uint32_t, uint32_t, uint32_t *);

int decode_long(DecodeLong fn, const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out,
                uint32_t out_size, uint32_t bytes_per_block) {
    if (!valid_image_args(data, data_size, width, height, out, out_size)) return 0;
    if (!has_block_data(data_size, width, height, bytes_per_block)) return 0;
    return fn(data, width, height, reinterpret_cast<uint32_t *>(out)) ? 1 : 0;
}

int decode_u32(DecodeU32 fn, const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out,
               uint32_t out_size, uint32_t bytes_per_block) {
    if (!valid_image_args(data, data_size, width, height, out, out_size)) return 0;
    if (!has_block_data(data_size, width, height, bytes_per_block)) return 0;
    return fn(data, static_cast<uint32_t>(width), static_cast<uint32_t>(height), reinterpret_cast<uint32_t *>(out)) ? 1 : 0;
}

using CrunchFn = bool (*)(const uint8_t *, uint32_t, uint32_t, void **, uint32_t *);

int unpack_crunch_impl(CrunchFn fn, const uint8_t *data, uint32_t data_size, uint32_t level_index, uint8_t **out,
                       uint32_t *out_size) {
    if (!data || data_size == 0 || !out || !out_size) return 0;
    *out = nullptr;
    *out_size = 0;
    void *raw = nullptr;
    uint32_t raw_size = 0;
    if (!fn(data, data_size, level_index, &raw, &raw_size) || !raw || raw_size == 0) {
        if (raw) delete[] static_cast<uint8_t *>(raw);
        return 0;
    }
    uint8_t *copy = static_cast<uint8_t *>(std::malloc(raw_size));
    if (!copy) {
        delete[] static_cast<uint8_t *>(raw);
        return 0;
    }
    std::memcpy(copy, raw, raw_size);
    delete[] static_cast<uint8_t *>(raw);
    *out = copy;
    *out_size = raw_size;
    return 1;
}

}  // namespace

extern "C" {

int raven_decode_bc1(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_bc1, data, data_size, width, height, out, out_size, 8);
}

int raven_decode_bc3(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_bc3, data, data_size, width, height, out, out_size, 16);
}

int raven_decode_bc4(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_u32(decode_bc4, data, data_size, width, height, out, out_size, 8);
}

int raven_decode_bc5(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_u32(decode_bc5, data, data_size, width, height, out, out_size, 16);
}

int raven_decode_bc6(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_u32(decode_bc6, data, data_size, width, height, out, out_size, 16);
}

int raven_decode_bc7(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_u32(decode_bc7, data, data_size, width, height, out, out_size, 16);
}

int raven_decode_atc_rgb4(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_u32(decode_atc_rgb4, data, data_size, width, height, out, out_size, 8);
}

int raven_decode_atc_rgba8(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_u32(decode_atc_rgba8, data, data_size, width, height, out, out_size, 16);
}

int raven_decode_etc1(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_etc1, data, data_size, width, height, out, out_size, 8);
}

int raven_decode_etc2(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_etc2, data, data_size, width, height, out, out_size, 8);
}

int raven_decode_etc2a1(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_etc2a1, data, data_size, width, height, out, out_size, 8);
}

int raven_decode_etc2a8(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_etc2a8, data, data_size, width, height, out, out_size, 16);
}

int raven_decode_eacr(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_eacr, data, data_size, width, height, out, out_size, 8);
}

int raven_decode_eacr_signed(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_eacr_signed, data, data_size, width, height, out, out_size, 8);
}

int raven_decode_eacrg(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_eacrg, data, data_size, width, height, out, out_size, 16);
}

int raven_decode_eacrg_signed(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size) {
    return decode_long(decode_eacrg_signed, data, data_size, width, height, out, out_size, 16);
}

int raven_decode_pvrtc(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, int32_t is2bpp, uint8_t *out, uint32_t out_size) {
    if (!valid_image_args(data, data_size, width, height, out, out_size)) return 0;
    if (data_size < pvrtc_size(width, height, is2bpp)) return 0;
    return decode_pvrtc(data, width, height, reinterpret_cast<uint32_t *>(out), is2bpp ? 1 : 0) ? 1 : 0;
}

int raven_decode_astc(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, int32_t block_width, int32_t block_height, uint8_t *out, uint32_t out_size) {
    if (!valid_image_args(data, data_size, width, height, out, out_size)) return 0;
    if (data_size < astc_size(width, height, block_width, block_height)) return 0;
    return decode_astc(data, width, height, block_width, block_height, reinterpret_cast<uint32_t *>(out)) ? 1 : 0;
}

int raven_unpack_crunch(const uint8_t *data, uint32_t data_size, uint32_t level_index, uint8_t **out, uint32_t *out_size) {
    return unpack_crunch_impl(crunch_unpack_level, data, data_size, level_index, out, out_size);
}

int raven_unpack_unity_crunch(const uint8_t *data, uint32_t data_size, uint32_t level_index, uint8_t **out, uint32_t *out_size) {
    return unpack_crunch_impl(unity_crunch_unpack_level, data, data_size, level_index, out, out_size);
}

void raven_free(uint8_t *ptr) {
    std::free(ptr);
}

}  // extern "C"
