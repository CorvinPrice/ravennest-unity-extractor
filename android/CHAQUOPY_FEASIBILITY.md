# Chaquopy feasibility — RavenNest Unity Extractor

Fecha: 2026-11-26. Alcance: empaquetar el motor UnityPy en Android para builds Unity propios. No se usaron assets de Almastriga.

## Veredicto corto

Chaquopy es viable como ruta de empaquetado para una primera versión limitada, pero no para prometer todavía exportación PNG completa de texturas Unity comprimidas.

- Listar `Texture2D`/`Sprite`: plausible con UnityPy en modo `--no-deps`, dependencias puras y wheels Chaquopy de Pillow/lz4/brotli.
- Exportar PNG de texturas no comprimidas: plausible si se parchea el import superior de decodificadores nativos en `Texture2DConverter`.
- Exportar PNG de texturas comprimidas BC/ETC/PVRTC/ASTC/Crunch: bloqueado hasta compilar wheels Android de `texture2ddecoder` y `astc-encoder-py`.
- APK final: no construido ni validado localmente en esta sesión.

## Evidencia local

- Motor: `engine/unity_extract.py` compila y sus 3 tests unitarios pasan.
- CLI sin entradas Unity devuelve error controlado: `No Unity serialized files or bundles found under: /tmp`.
- Esqueleto Android: `MainActivity.kt` compila contra `android-34` con el `kotlinc` local.
- Python de escritorio: UnityPy 1.25.4 importa y declara dependencias `lz4`, `brotli`, `Pillow`, `texture2ddecoder>=1.0.5`, `etcpak`, `astc-encoder-py>=0.1.12`, `fmod_toolkit`, `fsspec`, `attrs` y `tpk_ar`.
- Con `astc_encoder`, `texture2ddecoder`, `etcpak`, `fmod_toolkit`, `pyfmodex` y `UnityPyBoost` bloqueados, `import UnityPy` siguió funcionando en escritorio. Eso apoya una ruta de listado con dependencias recortadas, pero no prueba exportación de imágenes.

## Evidencia Chaquopy

- Chaquopy se distribuye como plugin Gradle para Android; exige `minSdk` 24 o mayor y `abiFilters` por ser un componente nativo.
- Su bloque `pip` puede instalar paquetes puros y una selección de paquetes nativos ya construidos.
- En el repositorio nativo de Chaquopy aparecen `brotli`, `lz4`, `numpy` y `pillow` con wheels Android.
- En ese índice no aparecen `texture2ddecoder`, `etcpak`, `astc-encoder-py` ni `UnityPy` como paquetes nativos listos.

Fuentes: documentación Chaquopy 17.2 y su índice `pypi-13.1`.

## Intento Gradle local

Entorno local disponible: Gradle 8.7, JDK 17 y SDK Android 34.

Se creó un proyecto mínimo de prueba con AGP 8.5.2 y Chaquopy 17.2.0. La resolución de plugins falló en este sandbox antes de llegar a instalar UnityPy:

- Primer fallo: el daemon de Gradle no completó la comunicación; se evitó igualando `GRADLE_OPTS` con las opciones del daemon.
- Fallo restante: Gradle no pudo resolver artefactos desde Google Maven/Maven Central por `SSLException: Unsupported or unrecognized SSL message`, incluso tras preparar truststore y pasar proxy por propiedades del sistema.

Por tanto, el bloqueo local inmediato es de red/SSL del sandbox para Gradle, no una prueba de que Chaquopy sea imposible en un entorno normal.

## Dependencias y bloqueos reales

Disponibles o probablemente cubiertas por Chaquopy/PyPI:

- `Pillow`: wheel Android en Chaquopy.
- `lz4`: wheel Android en Chaquopy.
- `brotli`: wheel Android en Chaquopy.
- `fsspec`, `attrs`, `tpk_ar`: puras o instalables como Python puro.

Bloqueos para exportación completa:

- `texture2ddecoder`: decodifica BC/ETC/PVRTC/ATC/Crunch; no está en el repo nativo de Chaquopy.
- `astc-encoder-py`: decodifica ASTC; no está en el repo nativo de Chaquopy.
- `etcpak`: se usa sobre todo para comprimir; para extracción se puede omitir o parchear fuera del camino de lectura.
- `fmod_toolkit`: audio/FMOD; fuera del alcance Texture2D/Sprite, se puede omitir.
- `UnityPyBoost`: acelerador nativo de UnityPy; el código tiene fallback Python para typetree, pero el wheel de escritorio no sirve para Android.

## Ruta recomendada

1. Crear el proyecto Gradle/Chaquopy en un entorno donde Gradle sí resuelva Google Maven y Maven Central.
2. Usar Python 3.12, `minSdk 24`, ABIs `arm64-v8a` y `x86_64`.
3. Instalar UnityPy 1.7.43 con `--no-deps` para Android; añadir `Pillow`, `chaquopy-libjpeg`, `chaquopy-freetype`, `lz4`, `brotli` y `tabulate`, reemplazando `texture2ddecoder`/`etcpak` por el decodificador Raven/stubs. Las dependencias nativas de Pillow deben listarse a mano porque `--no-deps` las omite.
4. Parchear los imports superiores de `astc_encoder` y `texture2ddecoder` para que sean perezosos; así el listado y las texturas no comprimidas no caen por decodificadores ausentes.
5. Probar primero listado con un build Unity propio pequeño.
6. Compilar wheels Android de `texture2ddecoder` y `astc-encoder-py` con recetas Chaquopy/NDK; recién entonces prometer exportación PNG de texturas comprimidas.

## Fallbacks

- Termux en la tablet: prueba rápida del motor antes de empaquetar APK.
- python-for-android/BeeWare: misma necesidad de recetas nativas para decodificadores.
- Puerto nativo Kotlin/NDK: más trabajo, pero evita depender de wheels Python para decodificación de texturas.

## Actualización 2026-11-26: decodificador nativo

La ruta recomendada cambió de wheels Python a una librería nativa C ABI:

- Se vendorizaron las fuentes MIT de Texture2DDecoder 1.0.6 en `native/third_party/texture2ddecoder/`.
- `native/raven_texture2ddecoder.cpp` expone `raven_decode_*`, `raven_unpack_crunch` y `raven_unpack_unity_crunch` para ctypes.
- `engine/native_texture2ddecoder.py` presenta la misma superficie que UnityPy espera de `texture2ddecoder`.
- `engine/unitypy_patch.py` inyecta stubs de `astc_encoder`/`fmod_toolkit` y redirige ASTC a `decode_astc` del decodificador nativo; ya no hace falta `astc-encoder-py` para exportar.
- `engine/pure_texture_decoders.py` cubre ETC/EAC/ATC en Python puro como fallback; PVRTC, ASTC y Crunch quedan nativos.
- NDK r26d compiló `libraven_texture2ddecoder.so` para `arm64-v8a` y `x86_64`; las copias stripped quedaron en `android/app/src/main/jniLibs/`.
- Verificación local: tests unitarios OK; en una simulación con `texture2ddecoder`, `astc_encoder`, `etcpak`, `fmod_toolkit` y `UnityPyBoost` bloqueados, UnityPy exportó DXT1, DXT5, BC7, ETC2_RGBA8, ASTC_RGBA_4x4 y PVRTC_RGBA4 con el puente nativo. Con fallback puro exportaron DXT1, DXT5, BC7 y ETC2_RGBA8; ASTC/PVRTC fallaron con error claro por requerir la `.so`.
- Crunch: la librería incluye unpack de Crunch/Unity Crunch y un stream inválido devuelve error controlado; no hubo muestra Crunch válida local para probar un PNG cruncheado real.
- APK: Gradle sigue sin completar `assembleDebug` en este sandbox por fallo de comunicación del daemon antes de validar Chaquopy. No hay APK final validado.

## Actualización 2026-11-26: URI Android conectada

- `MainActivity.kt` ya usa SAF: carpeta `*_Data`, archivo/bundle y carpeta de salida PNG.
- La selección se copia a caché privada preservando estructura relativa para `level*`, `*.assets`, `.resS`, `.resource`, bundles y todo `StreamingAssets`.
- `engine/android_bridge.py` expone `list_assets_json`, `export_assets_json`, `health_json` y `set_native_lib_dir`; Kotlin parsea el JSON y copia los PNG a la carpeta SAF elegida o a `Android/data/com.ravennest.unityextractor/files/RavenNestUnityExtractor/exports/`.
- El icono Android se generó desde `assets/logo.png`.
- Verificación local: 9 tests Python OK con UnityPy en venv, incluido el test sintético de formatos comprimidos; `MainActivity.kt` compila contra `android-34` usando stubs Chaquopy.
- Bloqueo APK: Gradle 8.7 y 8.14.3 fallan en este sandbox antes de resolver plugins: `Could not receive a message from the daemon`, causado por `Unexpected type tag 109` al leer la conexión loopback cliente-daemon. Replicar Chaquopy a mano exigiría reproducir la generación de assets del plugin (`build.json`, `bootstrap/stdlib/app/requirements .imy`, librerías nativas renombradas) sin validación en dispositivo; no se produjo un APK manual no verificado.
- Hardware pendiente: construir en entorno Gradle funcional/CI, instalar en la tablet, elegir un build Unity propio pequeño, listar assets, exportar PNG y revisar Logcat si Chaquopy/UnityPy falla al cargar dependencias.

## Actualización 2026-11-26: pin Android compatible con Chaquopy

- CI falló en `installDebugPythonRequirements`: Chaquopy no encontró `UnityPy==1.25.4` para Android y listó candidatos hasta `1.7.43`.
- La corrección local fija Android en `UnityPy==1.7.43`, cuyo wheel es `py3-none-any`; la API principal que usa el motor (`UnityPy.load`, `env.objects`, `obj.type.name`, `obj.read()`, `data.image`) está presente en esa versión.
- Dependencias Android recortadas a `Pillow`, `chaquopy-libjpeg`, `chaquopy-freetype`, `lz4`, `brotli` y `tabulate`; `texture2ddecoder` y `etcpak` quedan reemplazados por el decodificador Raven/stubs, y se retiraron `fsspec`, `attrs` y `tpk_ar` por ser dependencias de UnityPy moderno.
- `unitypy_patch.py` ahora instala el parche antes de importar UnityPy, añade stub de `etcpak`, aliases `decode_dxt1`/`decode_dxt5` y tolera conversores sin `calculate_astc_compressed_size` o con `CONV_TABLE` de forma distinta. También instala un stub de `tkinter.messagebox`: UnityPy 1.7.43 importa `NO` desde ahí en `classes/GameObject.py`, y Chaquopy/Android no trae tkinter; sin ese stub, `import UnityPy` falla aunque el wheel esté instalado.
- Pendiente tras levantar el límite de GitHub: empujar estos cambios, rerun de Actions y prueba en tablet con un build Unity propio pequeño.

## Actualización 2026-11-26: daemon corregido, red Java bloqueada en sandbox

- El fallo `Unexpected type tag 109` venía de la conexión loopback cliente-daemon interceptada en este sandbox. Con `GRADLE_OPTS='-Xms256m -Xmx512m -Dfile.encoding=US-ASCII -Duser.country=US -Duser.language=en -Duser.variant'`, Gradle 8.7 ya no forka el daemon de un solo uso y llega a resolver plugins.
- `settings.gradle.kts` ahora mapea los plugins a módulos directos (`com.android.tools.build:gradle`, `org.jetbrains.kotlin:kotlin-gradle-plugin`, `com.chaquo.python:gradle`) y usa `https://repo1.maven.org/maven2` como Maven Central.
- Comando probado: `GRADLE_USER_HOME=/tmp/gradle-unity-extractor-final3 ./build-apk.sh`. Resultado: `BUILD FAILED in 46s` en resolución de `com.android.tools.build:gradle:8.5.2`; no se generó APK.
- Evidencia del bloqueo restante: curl/Python sí llegan por el proxy a Google Maven/Maven Central, pero un socket Java directo recibe el aviso del sandbox de que otras conexiones TCP están desactivadas; Gradle/Java recibe `Connection reset` al abrir TLS hacia los repositorios. Es un bloqueo de red del entorno local, no del proyecto.
- Ruta reproducible añadida: `android/build-apk.sh` y `.github/workflows/build-apk.yml` (JDK 17, Python 3.12, Android SDK, Gradle 8.7) para construir y subir `app-debug.apk` en CI. En CI no se necesita el proxy del sandbox.

## Actualización 2026-11-26: Pillow necesita sus librerías Chaquopy

- En hardware, tras corregir el stub de tkinter, el listado llegó a copiar archivos y falló al importar UnityPy: `dlopen failed: library "libjpeg_chaquopy.so" not found: needed by .../PIL/_imaging.so`.
- Causa: el bloque Chaquopy usa `--no-deps` para omitir `texture2ddecoder`/`etcpak`, pero eso también omite las dependencias nativas que el wheel Chaquopy de Pillow declara para sus módulos C. `PIL/_imaging.so` necesita `libjpeg_chaquopy.so`; el módulo de fuentes de Pillow usa FreeType.
- Corrección de empaquetado: declarar explícitamente `chaquopy-libjpeg>=1.5.3` y `chaquopy-freetype>=2.9.1` junto a `Pillow` en `build.gradle.kts` y `engine/requirements-android.txt`. No hace falta cambiar el workflow: el mismo `installDebugPythonRequirements` de Chaquopy debe instalar ahora esas librerías para `arm64-v8a` y `x86_64`.

## Actualización 2026-11-26: autoactualización y firma estable

- La app sube a `versionCode 2` / `versionName 0.1.1` y añade botón **Buscar actualización** más comprobación al abrir. Lee `version-extractor.json` desde `main`, compara `versionCode`, descarga `apk_url` a caché y abre el instalador Android con `FileProvider`. Si el manifiesto o el asset de Release todavía no existen, la comprobación automática falla en silencio y la manual muestra el error sin cerrar la app.
- `version-extractor.json` apunta a `https://github.com/CorvinPrice/ravennest-unity-extractor/releases/latest/download/app-debug.apk`. La autoactualización queda viva cuando exista una GitHub Release con un asset llamado exactamente `app-debug.apk` y el manifiesto anuncie un `versionCode` mayor que el instalado.
- Para actualizar sin desinstalar no basta con subir `versionCode`: Android exige el mismo certificado de firma. `build.gradle.kts` ahora acepta una firma estable por variables de entorno (`EXTRACTOR_KEYSTORE_PATH`, `EXTRACTOR_KEYSTORE_PASSWORD`, `EXTRACTOR_KEY_ALIAS`, `EXTRACTOR_KEY_PASSWORD`) y la aplica a `debug`/`release` cuando están completas. Sin esas variables, CI sigue produciendo un APK debug firmado con certificado debug; con variables incompletas, Gradle falla en vez de caer silenciosamente a debug.
- Pendiente manual en GitHub: crear una keystore dedicada fuera del repo, guardar `EXTRACTOR_KEYSTORE_BASE64`, `EXTRACTOR_KEYSTORE_PASSWORD`, `EXTRACTOR_KEY_ALIAS` y `EXTRACTOR_KEY_PASSWORD` como Secrets, editar el workflow para decodificar la keystore a un archivo temporal y exportar `EXTRACTOR_KEYSTORE_PATH` antes de compilar, y publicar el APK como asset `app-debug.apk` en una Release. Hasta completar eso, no se debe prometer actualización sin desinstalar; al pasar del APK debug actual a la línea firmada estable puede hacer falta una última desinstalación.
