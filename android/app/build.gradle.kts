plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.ravennest.unityextractor"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.ravennest.unityextractor"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
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
            options("--no-deps")
            install("UnityPy==1.7.43")
            install("Pillow")
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
