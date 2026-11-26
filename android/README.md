# Android app

App ligera RavenNest Unity Extractor.

- Paquete: `com.ravennest.unityextractor`
- Pantalla principal: selección SAF de carpeta `*_Data`, archivo/bundle y carpeta de salida PNG.
- Flujo conectado: la selección se copia a caché privada preservando `level*`, `*.assets`, `.resS`, bundles y `StreamingAssets`; Chaquopy llama `engine/android_bridge.py`, que devuelve JSON para listar/exportar.
- Salida: si el usuario elige carpeta de salida, los PNG se copian ahí por SAF; si no, quedan en `Android/data/com.ravennest.unityextractor/files/RavenNestUnityExtractor/exports/`.
- `EngineBridge` carga `libraven_texture2ddecoder.so`, arranca Chaquopy y pasa `nativeLibraryDir` al puente Python.
- Logo fuente: `../assets/logo.png`; icono compilado en `app/src/main/res/drawable-nodpi/ic_launcher.png`.
- Librerías nativas: `app/src/main/jniLibs/arm64-v8a/` y `app/src/main/jniLibs/x86_64/`.
- Chaquopy: `app/build.gradle.kts` usa Python 3.12, UnityPy `--no-deps` y dependencias recortadas.

Bloqueo local: en este sandbox Gradle 8.7 y 8.14.3 no completan `help`/`assembleDebug`; el cliente Gradle falla al leer mensajes del daemon por loopback (`Unexpected type tag 109`) antes de resolver AGP/Chaquopy. El Kotlin compila contra `android-34` con stubs Chaquopy y los tests Python/sintéticos pasan. Siguiente paso: construir en un entorno Gradle funcional o CI, instalar en la tablet y probar con un build Unity propio pequeño.
