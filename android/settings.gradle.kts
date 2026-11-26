pluginManagement {
    repositories {
        google()
        maven {
            name = "MavenCentralRepo1"
            url = uri("https://repo1.maven.org/maven2")
        }
        gradlePluginPortal()
    }
    resolutionStrategy {
        eachPlugin {
            when (requested.id.id) {
                "com.android.application" -> useModule("com.android.tools.build:gradle:${requested.version}")
                "org.jetbrains.kotlin.android" -> useModule("org.jetbrains.kotlin:kotlin-gradle-plugin:${requested.version}")
                "com.chaquo.python" -> useModule("com.chaquo.python:gradle:${requested.version}")
            }
        }
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        maven {
            name = "MavenCentralRepo1"
            url = uri("https://repo1.maven.org/maven2")
        }
    }
}

rootProject.name = "RavenNestUnityExtractor"
include(":app")
