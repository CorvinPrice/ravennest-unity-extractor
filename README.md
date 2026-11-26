# RavenNest Unity Extractor

MVP para inspeccionar builds Unity propios: listar `Texture2D` y `Sprite`, y exportarlos como PNG.

## Estado

- Motor Python en `engine/unity_extract.py`, basado en UnityPy.
- Parche de texturas en `engine/unitypy_patch.py`: UnityPy ya no depende de `astc-encoder-py` ni de `fmod_toolkit` para exportar texturas.
- Decodificador nativo C ABI en `native/`, compilado para Android `arm64-v8a` y `x86_64` en `android/app/src/main/jniLibs/`.
- Fallback Python puro para ETC/EAC/ATC en `engine/pure_texture_decoders.py`.
- Pruebas unitarias en `engine/test_unity_extract.py` y `engine/test_texture_decoders.py`.
- Esqueleto Android ligero en `android/`.
- Logo en `assets/logo.png`.

## Uso del motor

Instalar dependencias:

```bash
pip install -r engine/requirements.txt
```

Listar assets:

```bash
python3 engine/unity_extract.py list /ruta/a/TuJuego_Data
```

Exportar PNG:

```bash
python3 engine/unity_extract.py export /ruta/a/TuJuego_Data ./salida-png
```

## Alcance del MVP

- Lee archivos serializados Unity y bundles mediante UnityPy.
- En carpetas busca `level*`, `sharedassets*.assets`, `*.assets`, `*.bundle` y `*.unity3d`.
- Filtra solo `Texture2D` y `Sprite`.
- Exporta PNG con nombres seguros y sin sobrescribir duplicados.

## Bloqueos / siguiente paso

- El bloqueo de decodificadores nativos quedó resuelto a nivel de librería: `libraven_texture2ddecoder.so` compila para `arm64-v8a` y `x86_64`, y UnityPy exporta DXT/BC7/ETC2/ASTC/PVRTC en la simulación sin wheels de escritorio.
- Chaquopy queda configurado en `android/app/build.gradle.kts` con UnityPy 1.7.43 `--no-deps` y dependencias recortadas (`Pillow`, `lz4`, `brotli`, `tabulate`); el decodificador entra como `.so` en `jniLibs`, no como wheel Python. UnityPy 1.25.4 no sirve para Chaquopy porque no ofrece una distribución instalable para Android en ese índice; 1.7.43 sí publica wheel `py3-none-any` y mantiene la API que usa el motor (`UnityPy.load`, `env.objects`, `obj.type.name`, `obj.read()`, `data.image`).
- La URI Android ya está conectada: `MainActivity.kt` usa SAF para carpeta/archivo y carpeta de salida, copia la selección a caché privada preservando `level*`, `*.assets`, `.resS`, bundles y `StreamingAssets`, y llama `engine/android_bridge.py` por Chaquopy para listar/exportar JSON.
- El icono Android sale de `assets/logo.png` (`res/drawable-nodpi/ic_launcher.png`).
- En este sandbox Gradle todavía no construyó el APK Chaquopy: Gradle 8.7 y 8.14.3 fallan antes de resolver plugins con `Could not receive a message from the daemon` / `Unexpected type tag 109` en la conexión cliente-daemon por loopback. No hay APK final validado.
- Falta probar extracción real con un build Unity propio pequeño en hardware; no se usaron assets de Almastriga.
