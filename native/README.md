# Native texture decoder

`libraven_texture2ddecoder.so` is RavenNest's small C ABI bridge over the
MIT-licensed Texture2DDecoder sources vendored in
`third_party/texture2ddecoder/`.  Python calls it through
`engine/native_texture2ddecoder.py` with ctypes, so Chaquopy does not need a
Python C-extension wheel for `texture2ddecoder` or `astc-encoder-py`.

Covered by the native library:

- BC1/BC3/BC4/BC5/BC6/BC7
- ATC RGB4/RGBA8
- ETC1, ETC2 RGB/RGBA1/RGBA8, EAC R/RG signed and unsigned
- PVRTC 2bpp/4bpp
- ASTC decode through Texture2DDecoder's `decode_astc`
- Crunch and Unity Crunch unpacking

UnityPy still decodes DXT/BC through Pillow's `bcn` codec for the non-crunched
BC formats.  The native library is the path for ETC/EAC/PVRTC/ATC/ASTC and for
Crunch unpacking before BC/ETC decoding.

Build host proof:

```bash
native/build_host.sh
```

Build Android libraries:

```bash
ANDROID_NDK_HOME=/path/to/android-ndk native/build_android.sh
```

The Android build writes stripped libraries to:

- `android/app/src/main/jniLibs/arm64-v8a/libraven_texture2ddecoder.so`
- `android/app/src/main/jniLibs/x86_64/libraven_texture2ddecoder.so`

Licenses for the vendored decoder sources are kept in
`third_party/texture2ddecoder/LICENSE` and
`third_party/texture2ddecoder/README.upstream.md`.
