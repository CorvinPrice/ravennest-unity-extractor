#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Local RavenNest tooling, when present. CI provides its own JDK/Android SDK.
if [ -z "${JAVA_HOME:-}" ] && [ -d "$HOME/workspace/tools/android/jdk-17" ]; then
  export JAVA_HOME="$HOME/workspace/tools/android/jdk-17"
fi
if [ -z "${ANDROID_HOME:-}" ] && [ -d "$HOME/workspace/tools/android/sdk" ]; then
  export ANDROID_HOME="$HOME/workspace/tools/android/sdk"
  export ANDROID_SDK_ROOT="$ANDROID_HOME"
fi
if [ -n "${JAVA_HOME:-}" ]; then
  export PATH="$JAVA_HOME/bin:$PATH"
fi
if [ -d "$HOME/workspace/tools/android/gradle-8.7/bin" ]; then
  export PATH="$HOME/workspace/tools/android/gradle-8.7/bin:$PATH"
fi

# Match the client JVM to Gradle's default build JVM in restricted loopback
# environments; this avoids a single-use daemon fork solely for JVM settings.
if [ -z "${GRADLE_OPTS:-}" ]; then
  if [ "${CI:-}" = "true" ]; then
    export GRADLE_OPTS="-Xms256m -Xmx2g"
  else
    export GRADLE_OPTS="-Xms256m -Xmx512m -Dfile.encoding=US-ASCII -Duser.country=US -Duser.language=en -Duser.variant"
  fi
fi

if [ -x ./gradlew ]; then
  ./gradlew --no-daemon :app:assembleDebug "$@"
else
  gradle --no-daemon :app:assembleDebug "$@"
fi

find app/build/outputs/apk -name '*.apk' -print
