#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
if [[ -z "$NDK" ]]; then
  for candidate in "$HOME/workspace/tools/android/sdk/ndk/"* /tmp/android-ndk-* "$HOME/Android/Sdk/ndk/"*; do
    if [[ -f "$candidate/build/cmake/android.toolchain.cmake" ]]; then
      NDK="$candidate"
      break
    fi
  done
fi
if [[ -z "$NDK" || ! -f "$NDK/build/cmake/android.toolchain.cmake" ]]; then
  echo "Android NDK not found. Set ANDROID_NDK_HOME to an NDK with build/cmake/android.toolchain.cmake." >&2
  exit 2
fi

for ABI in arm64-v8a x86_64; do
  BUILD_DIR="$ROOT/native/build/android-$ABI"
  OUT_DIR="$ROOT/android/app/src/main/jniLibs/$ABI"
  mkdir -p "$OUT_DIR"
  cmake -S "$ROOT/native" -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI="$ABI" \
    -DANDROID_PLATFORM=android-24 \
    -DANDROID_STL=c++_static
  cmake --build "$BUILD_DIR" -j"$(nproc)"
  cp "$BUILD_DIR/libraven_texture2ddecoder.so" "$OUT_DIR/libraven_texture2ddecoder.so"
  "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" "$OUT_DIR/libraven_texture2ddecoder.so"
  echo "$OUT_DIR/libraven_texture2ddecoder.so"
done
