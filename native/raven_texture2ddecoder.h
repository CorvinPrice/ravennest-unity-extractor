#pragma once

#include <stdint.h>

#if defined(_WIN32)
#define RAVEN_API __declspec(dllexport)
#else
#define RAVEN_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Return 1 on success, 0 on failure. Output is BGRA8888, width*height*4 bytes. */
RAVEN_API int raven_decode_bc1(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_bc3(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_bc4(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_bc5(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_bc6(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_bc7(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_atc_rgb4(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_atc_rgba8(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_etc1(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_etc2(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_etc2a1(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_etc2a8(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_eacr(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_eacr_signed(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_eacrg(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_eacrg_signed(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_pvrtc(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, int32_t is2bpp, uint8_t *out, uint32_t out_size);
RAVEN_API int raven_decode_astc(const uint8_t *data, uint32_t data_size, int32_t width, int32_t height, int32_t block_width, int32_t block_height, uint8_t *out, uint32_t out_size);

/* Crunch outputs are allocated by the library and must be released with raven_free. */
RAVEN_API int raven_unpack_crunch(const uint8_t *data, uint32_t data_size, uint32_t level_index, uint8_t **out, uint32_t *out_size);
RAVEN_API int raven_unpack_unity_crunch(const uint8_t *data, uint32_t data_size, uint32_t level_index, uint8_t **out, uint32_t *out_size);
RAVEN_API void raven_free(uint8_t *ptr);

#ifdef __cplusplus
}
#endif
