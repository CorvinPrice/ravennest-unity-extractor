plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// Stable signing is opt-in through environment variables so no keystore or
// password is committed. CI provides these from GitHub Secrets after decoding
// EXTRACTOR_KEYSTORE_BASE64 to a temporary file. If none are set, local/CI
// builds keep Android's debug signing; if only some are set, fail loudly so a
// supposedly stable-signed build cannot silently fall back to a changing
// debug certificate.
val extractorKeystorePath = System.getenv("EXTRACTOR_KEYSTORE_PATH")
val extractorKeystorePassword = System.getenv("EXTRACTOR_KEYSTORE_PASSWORD")
val extractorKeyAlias = System.getenv("EXTRACTOR_KEY_ALIAS")
val extractorKeyPassword = System.getenv("EXTRACTOR_KEY_PASSWORD")
val extractorKeystoreFile = extractorKeystorePath
    ?.takeIf { it.isNotBlank() }
    ?.let { file(it) }
val stableSigningEnvPresent = listOf(
    extractorKeystorePath,
    extractorKeystorePassword,
    extractorKeyAlias,
    extractorKeyPassword,
).any { !it.isNullOrBlank() }
val hasStableSigning = extractorKeystoreFile?.isFile == true &&
    !extractorKeystorePassword.isNullOrBlank() &&
    !extractorKeyAlias.isNullOrBlank() &&
    !extractorKeyPassword.isNullOrBlank()
if (stableSigningEnvPresent && !hasStableSigning) {
    error(
        "Incomplete stable signing configuration: set EXTRACTOR_KEYSTORE_PATH to an existing keystore and provide EXTRACTOR_KEYSTORE_PASSWORD, EXTRACTOR_KEY_ALIAS and EXTRACTOR_KEY_PASSWORD."
    )
}

android {
    namespace = "com.ravennest.unityextractor"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.ravennest.unityextractor"
        minSdk = 24
        targetSdk = 34
        versionCode = 2
        versionName = "0.1.1"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    signingConfigs {
        create("stable") {
            if (hasStableSigning) {
                storeFile = requireNotNull(extractorKeystoreFile)
                storePassword = requireNotNull(extractorKeystorePassword)
                keyAlias = requireNotNull(extractorKeyAlias)
                keyPassword = requireNotNull(extractorKeyPassword)
            }
        }
    }

    buildTypes {
        debug {
            // The distributed CI artifact is still app-debug.apk; when the
            // stable-signing env vars are present, sign that artifact with
            // the dedicated certificate so Android can update in place.
            if (hasStableSigning) {
                signingConfig = signingConfigs.getByName("stable")
            }
        }
        release {
            if (hasStableSigning) {
                signingConfig = signingConfigs.getByName("stable")
            }
            isMinifyEnabled = false
        }
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.12"
        buildPython("python3")

        pip {
            // UnityPy 1.7.43 metadata also requires texture2ddecoder/etcpak,
            // which have no Chaquopy wheels.  --no-deps intentionally omits
            // them: unitypy_patch.py installs Raven's texture2ddecoder bridge,
            // an etcpak stub, and a tkinter stub for UnityPy 1.7.43's stray
            // desktop-only GameObject import.  Because --no-deps also omits
            // Pillow's Chaquopy native-library dependencies, list them
            // explicitly; without chaquopy-libjpeg, PIL/_imaging.so fails at
            // runtime with dlopen libjpeg_chaquopy.so not found.
            options("--no-deps")
            install("UnityPy==1.7.43")
            install("Pillow")
            install("chaquopy-libjpeg>=1.5.3")
            install("chaquopy-freetype>=2.9.1")
            install("lz4")
            install("brotli")
            install("tabulate")
        }
    }

    sourceSets {
        getByName("main") {
            srcDir("../../engine")
        }
    }
}

dependencies {
    implementation("androidx.core:core:1.13.1")
}
