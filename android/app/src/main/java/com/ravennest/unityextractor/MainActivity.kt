package com.ravennest.unityextractor

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.FileProvider
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var inputSelection: TextView
    private lateinit var outputSelection: TextView
    private lateinit var results: TextView
    private var selectedInput: Uri? = null
    private var selectedInputIsTree = false
    private var selectedOutput: Uri? = null
    private val executor = Executors.newSingleThreadExecutor()
    private val uiHandler = Handler(Looper.getMainLooper())
    private var progressRunning = false
    private var progressStartedAtMs = 0L
    private var progressBase = ""
    private var progressDetail = ""
    private var progressProcessed = 0
    private var progressTotal = 0
    private var progressCopiedFiles = 0
    private val progressTicker = object : Runnable {
        override fun run() {
            if (!progressRunning) return
            updateProgressStatus()
            uiHandler.postDelayed(this, 1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        EngineBridge.loadNativeDecoder()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
            setBackgroundColor(Color.rgb(18, 12, 28))
        }

        root.addView(TextView(this).apply {
            text = "RavenNest Unity Extractor"
            textSize = 24f
            setTextColor(Color.rgb(0, 255, 170))
        })

        status = TextView(this).apply {
            text = "Elige una carpeta *_Data o un archivo Unity de tu propio proyecto."
            textSize = 16f
            setTextColor(Color.WHITE)
            setPadding(0, 32, 0, 16)
        }
        root.addView(status)

        root.addView(Button(this).apply {
            text = "Elegir carpeta *_Data"
            setOnClickListener {
                startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), REQ_INPUT_TREE)
            }
        })

        root.addView(Button(this).apply {
            text = "Elegir archivo / bundle"
            setOnClickListener {
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                }
                startActivityForResult(intent, REQ_INPUT_FILE)
            }
        })

        inputSelection = TextView(this).apply {
            text = "Entrada: sin seleccionar"
            textSize = 14f
            setTextColor(Color.rgb(190, 220, 255))
            setPadding(0, 12, 0, 12)
        }
        root.addView(inputSelection)

        root.addView(Button(this).apply {
            text = "Elegir carpeta de salida PNG"
            setOnClickListener {
                startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), REQ_OUTPUT_TREE)
            }
        })

        outputSelection = TextView(this).apply {
            text = "Salida: carpeta por defecto de la app"
            textSize = 14f
            setTextColor(Color.rgb(190, 255, 220))
            setPadding(0, 12, 0, 12)
        }
        root.addView(outputSelection)

        root.addView(Button(this).apply {
            text = "Listar Texture2D / Sprite"
            setOnClickListener { runEngine(export = false) }
        })

        root.addView(Button(this).apply {
            text = "Exportar PNG"
            setOnClickListener { runEngine(export = true) }
        })

        root.addView(Button(this).apply {
            text = "Buscar actualización"
            setOnClickListener { checkForUpdates(manual = true) }
        })

        results = TextView(this).apply {
            text = ""
            textSize = 14f
            setTextColor(Color.rgb(220, 220, 230))
            setPadding(0, 24, 0, 0)
        }
        root.addView(ScrollView(this).apply { addView(results) })

        setContentView(root)
        checkForUpdates(manual = false)
    }

    override fun onDestroy() {
        stopProgress()
        executor.shutdownNow()
        super.onDestroy()
    }

    @Deprecated("MVP uses the framework result API to avoid an AndroidX dependency")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        try {
            when (requestCode) {
                REQ_INPUT_TREE -> {
                    selectedInput = uri
                    selectedInputIsTree = true
                    takePersistable(uri, write = false)
                    inputSelection.text = "Entrada: ${displayName(uri, isTree = true)}"
                    status.text = "Entrada lista. Elige salida o lista los assets."
                }
                REQ_INPUT_FILE -> {
                    selectedInput = uri
                    selectedInputIsTree = false
                    takePersistable(uri, write = false)
                    inputSelection.text = "Entrada: ${displayName(uri, isTree = false)}"
                    status.text = "Entrada lista. Elige salida o lista los assets."
                }
                REQ_OUTPUT_TREE -> {
                    selectedOutput = uri
                    takePersistable(uri, write = true)
                    outputSelection.text = "Salida: ${displayName(uri, isTree = true)}"
                    status.text = "Salida lista. La entrada se mantiene."
                }
            }
        } catch (e: Exception) {
            status.text = "Selección guardada, pero no se pudo leer el nombre."
            results.text = e.message ?: e.toString()
        }
    }

    private fun takePersistable(uri: Uri, write: Boolean) {
        var flags = Intent.FLAG_GRANT_READ_URI_PERMISSION
        if (write) flags = flags or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        try {
            contentResolver.takePersistableUriPermission(uri, flags)
        } catch (_: Exception) {
            // Some providers do not offer persistable grants; the current grant still works.
        }
    }

    private fun checkForUpdates(manual: Boolean) {
        Thread {
            try {
                val manifest = JSONObject(fetchText(UPDATE_MANIFEST_URL))
                val remoteCode = manifest.optLong("versionCode", -1L)
                val remoteName = manifest.optString("versionName", remoteCode.toString())
                val apkUrl = manifest.optString("apk_url", manifest.optString("apkUrl", ""))
                val currentCode = currentVersionCode()
                if (remoteCode <= currentCode) {
                    if (manual) {
                        runOnUiThread {
                            status.text = "Ya tienes la última versión ($currentCode)."
                            results.text = "Versión instalada: $currentCode\nVersión publicada: $remoteName ($remoteCode)"
                        }
                    }
                    return@Thread
                }
                if (apkUrl.isBlank()) {
                    if (manual) {
                        runOnUiThread {
                            status.text = "Hay una versión nueva, pero falta la URL de descarga."
                            results.text = "Versión publicada: $remoteName ($remoteCode)"
                        }
                    }
                    return@Thread
                }
                runOnUiThread {
                    status.text = "Actualización disponible: $remoteName ($remoteCode). Descargando..."
                    results.text = ""
                }
                val apk = downloadUpdateApk(apkUrl, remoteCode)
                runOnUiThread {
                    status.text = "Actualización descargada. Abriendo instalador..."
                    launchInstaller(apk)
                }
            } catch (e: Exception) {
                if (manual) {
                    runOnUiThread {
                        status.text = "No se pudo buscar actualización todavía."
                        results.text = e.message ?: e.toString()
                    }
                }
            }
        }.start()
    }

    private fun currentVersionCode(): Long {
        val info = packageManager.getPackageInfo(packageName, 0)
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            info.longVersionCode
        } else {
            @Suppress("DEPRECATION")
            info.versionCode.toLong()
        }
    }

    private fun fetchText(url: String): String {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 10000
            readTimeout = 15000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "RavenNestUnityExtractor")
        }
        try {
            val code = connection.responseCode
            if (code !in 200..299) throw IOException("HTTP $code al leer $url")
            return connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    private fun downloadUpdateApk(url: String, remoteCode: Long): File {
        val dir = File(cacheDir, "updates").apply { mkdirs() }
        val target = File(dir, "RavenNestUnityExtractor-$remoteCode.apk")
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15000
            readTimeout = 30000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "RavenNestUnityExtractor")
        }
        try {
            val code = connection.responseCode
            if (code !in 200..299) throw IOException("HTTP $code al descargar la actualización")
            val total = connection.contentLengthLong
            var copied = 0L
            var lastReportedPercent = -1
            connection.inputStream.use { input ->
                FileOutputStream(target).use { out ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val read = input.read(buffer)
                        if (read <= 0) break
                        out.write(buffer, 0, read)
                        copied += read
                        if (total > 0) {
                            val percent = ((copied * 100) / total).toInt()
                            if (percent != lastReportedPercent) {
                                lastReportedPercent = percent
                                runOnUiThread { status.text = "Descargando actualización... $percent%" }
                            }
                        }
                    }
                }
            }
        } finally {
            connection.disconnect()
        }
        if (!target.isFile || target.length() <= 0L) throw IOException("La descarga de actualización quedó vacía")
        return target
    }

    private fun launchInstaller(apk: File) {
        try {
            val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", apk)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(intent)
        } catch (e: Exception) {
            status.text = "Actualización descargada, pero no se pudo abrir el instalador."
            results.text = "APK: ${apk.absolutePath}\n${e.message ?: e.toString()}"
        }
    }

    private fun runEngine(export: Boolean) {
        val input = selectedInput
        if (input == null) {
            status.text = "Primero elige una carpeta o archivo."
            return
        }
        val inputIsTree = selectedInputIsTree
        val output = selectedOutput
        startProgress(if (export) "Exportando PNG" else "Listando assets")
        results.text = ""

        executor.execute {
            try {
                val copied = copySelectionToCache(input, inputIsTree)
                setProgressDetail("procesando", processed = 0, total = 0, copiedFiles = progressCopiedFiles)
                val bridge = EngineBridge.python(this)
                if (!export) {
                    val payload = JSONObject(bridge.callAttr("list_assets_json", copied.absolutePath).toString())
                    showListResult(payload, copied)
                } else {
                    val exportDir = File(cacheDir, "exports/session-${System.currentTimeMillis()}").apply { mkdirs() }
                    val payload = JSONObject(
                        bridge.callAttr("export_assets_json", copied.absolutePath, exportDir.absolutePath).toString()
                    )
                    showExportResult(payload, exportDir, output)
                }
            } catch (e: Exception) {
                runOnUiThread {
                    stopProgress()
                    status.text = "Error"
                    results.text = e.message ?: e.toString()
                }
            }
        }
    }

    private fun startProgress(base: String) {
        progressRunning = true
        progressStartedAtMs = SystemClock.elapsedRealtime()
        progressBase = base
        progressDetail = "preparando"
        progressProcessed = 0
        progressTotal = 0
        progressCopiedFiles = 0
        uiHandler.removeCallbacks(progressTicker)
        updateProgressStatus()
        uiHandler.postDelayed(progressTicker, 1000)
    }

    private fun stopProgress() {
        progressRunning = false
        uiHandler.removeCallbacks(progressTicker)
    }

    private fun setProgressDetail(detail: String, processed: Int, total: Int, copiedFiles: Int) {
        progressDetail = detail
        progressProcessed = processed
        progressTotal = total
        progressCopiedFiles = copiedFiles
        runOnUiThread { updateProgressStatus() }
    }

    private fun updateProgressStatus() {
        if (!progressRunning || isFinishing || isDestroyed) return
        val elapsedSeconds = ((SystemClock.elapsedRealtime() - progressStartedAtMs) / 1000).coerceAtLeast(0)
        val detailText = when {
            progressTotal > 0 -> "$progressDetail $progressProcessed/$progressTotal archivos"
            progressCopiedFiles > 0 -> "$progressDetail $progressCopiedFiles archivos"
            else -> progressDetail
        }
        status.text = "$progressBase · $detailText · ${elapsedSeconds}s"
    }

    private fun showListResult(payload: JSONObject, copied: File) {
        runOnUiThread {
            stopProgress()
            if (!payload.optBoolean("ok")) {
                status.text = "No se pudo listar"
                results.text = payload.optString("error", "Error desconocido")
                return@runOnUiThread
            }
            val assets = payload.optJSONArray("assets")
            val count = payload.optInt("count", assets?.length() ?: 0)
            status.text = "Assets encontrados: $count"
            val lines = StringBuilder()
            lines.append("Entrada copiada a: ${copied.absolutePath}\n\n")
            if (assets != null) {
                val shown = minOf(assets.length(), 200)
                for (i in 0 until shown) {
                    val row = assets.optJSONObject(i) ?: continue
                    lines.append(row.optString("name"))
                        .append("  ·  ")
                        .append(row.optString("type"))
                        .append("  ·  ")
                        .append(row.optString("path_id"))
                        .append('\n')
                }
                if (assets.length() > shown) lines.append("\n... y ${assets.length() - shown} más")
            }
            results.text = lines.toString()
        }
    }

    private fun showExportResult(payload: JSONObject, exportDir: File, outputTree: Uri?) {
        if (!payload.optBoolean("ok")) {
            runOnUiThread {
                stopProgress()
                status.text = "No se pudo exportar"
                results.text = payload.optString("error", "Error desconocido")
            }
            return
        }
        val pngs = exportDir.listFiles { file -> file.isFile && file.name.endsWith(".png", ignoreCase = true) }
            ?.sortedBy { it.name }
            ?: emptyList()
        setProgressDetail("guardando PNG", processed = 0, total = pngs.size, copiedFiles = progressCopiedFiles)
        val destination = if (outputTree != null) {
            copyPngsToTree(pngs, outputTree)
            "carpeta de salida elegida"
        } else {
            val fallback = File(getExternalFilesDir(null), "RavenNestUnityExtractor/exports/${exportDir.name}")
            fallback.mkdirs()
            pngs.forEachIndexed { index, png ->
                png.copyTo(File(fallback, png.name), overwrite = true)
                setProgressDetail("guardando PNG", processed = index + 1, total = pngs.size, copiedFiles = progressCopiedFiles)
            }
            fallback.absolutePath
        }
        runOnUiThread {
            stopProgress()
            status.text = "Exportados: ${payload.optInt("exported_count")}  ·  Omitidos: ${payload.optInt("skipped_count")}"
            val lines = StringBuilder()
            lines.append("PNG en: $destination\n\n")
            pngs.take(200).forEach { lines.append(it.name).append('\n') }
            val skipped = payload.optJSONArray("skipped")
            if (skipped != null && skipped.length() > 0) {
                lines.append("\nOmitidos:\n")
                for (i in 0 until minOf(skipped.length(), 50)) {
                    val row = skipped.optJSONObject(i) ?: continue
                    lines.append(row.optString("name")).append(": ").append(row.optString("reason")).append('\n')
                }
            }
            results.text = lines.toString()
        }
    }

    private data class CopyItem(val uri: Uri, val dest: File)

    private fun copySelectionToCache(uri: Uri, isTree: Boolean): File {
        val root = File(cacheDir, "input/session-${System.currentTimeMillis()}").apply { mkdirs() }
        if (isTree) {
            val rootDocId = DocumentsContract.getTreeDocumentId(uri)
            setProgressDetail("buscando", processed = 0, total = 0, copiedFiles = 0)
            val items = mutableListOf<CopyItem>()
            collectTree(uri, rootDocId, root, "", items)
            progressCopiedFiles = items.size
            setProgressDetail("copiando", processed = 0, total = items.size, copiedFiles = items.size)
            items.forEachIndexed { index, item ->
                copyDocument(item.uri, item.dest)
                setProgressDetail("copiando", processed = index + 1, total = items.size, copiedFiles = items.size)
            }
        } else {
            setProgressDetail("copiando", processed = 0, total = 1, copiedFiles = 1)
            copyDocument(uri, File(root, safeName(displayName(uri, isTree = false))))
            progressCopiedFiles = 1
            setProgressDetail("copiando", processed = 1, total = 1, copiedFiles = 1)
        }
        return root
    }

    private fun collectTree(treeUri: Uri, parentDocId: String, destDir: File, relPath: String, items: MutableList<CopyItem>) {
        destDir.mkdirs()
        val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentDocId)
        val projection = arrayOf(
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE,
        )
        contentResolver.query(childrenUri, projection, null, null, null)?.use { cursor ->
            val idIndex = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DOCUMENT_ID)
            val nameIndex = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DISPLAY_NAME)
            val mimeIndex = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_MIME_TYPE)
            while (cursor.moveToNext()) {
                val docId = cursor.getString(idIndex) ?: continue
                val name = cursor.getString(nameIndex) ?: docId
                val mime = cursor.getString(mimeIndex) ?: ""
                val childRel = if (relPath.isBlank()) name else "$relPath/$name"
                if (mime == DocumentsContract.Document.MIME_TYPE_DIR) {
                    collectTree(treeUri, docId, File(destDir, safeName(name)), childRel, items)
                } else if (shouldCopyUnityFile(name, childRel)) {
                    val docUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, docId)
                    items.add(CopyItem(docUri, File(destDir, safeName(name))))
                    progressCopiedFiles = items.size
                }
            }
        } ?: throw IOException("No se pudo leer la carpeta seleccionada")
    }

    private fun copyDocument(uri: Uri, dest: File) {
        dest.parentFile?.mkdirs()
        val input = contentResolver.openInputStream(uri) ?: throw IOException("No se pudo abrir: $uri")
        input.use { stream -> FileOutputStream(dest).use { out -> stream.copyTo(out) } }
    }

    private fun copyPngsToTree(pngs: List<File>, treeUri: Uri) {
        val parentDocId = DocumentsContract.getTreeDocumentId(treeUri)
        val parentUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, parentDocId)
        pngs.forEachIndexed { index, png ->
            val docUri = DocumentsContract.createDocument(contentResolver, parentUri, "image/png", png.name)
                ?: throw IOException("No se pudo crear ${png.name} en la carpeta de salida")
            val out = contentResolver.openOutputStream(docUri) ?: throw IOException("No se pudo escribir ${png.name}")
            out.use { stream -> png.inputStream().use { it.copyTo(stream) } }
            setProgressDetail("guardando PNG", processed = index + 1, total = pngs.size, copiedFiles = progressCopiedFiles)
        }
    }

    private fun shouldCopyUnityFile(name: String, relPath: String): Boolean {
        val lower = name.lowercase()
        val lowerPath = relPath.lowercase()
        return lowerPath.contains("streamingassets/") ||
            lower.matches(Regex("level\\d+")) ||
            lower.endsWith(".assets") ||
            lower.endsWith(".assets.ress") ||
            lower.endsWith(".ress") ||
            lower.endsWith(".resource") ||
            lower.endsWith(".bundle") ||
            lower.endsWith(".unity3d") ||
            lower == "globalgamemanagers" ||
            lower.startsWith("globalgamemanagers.")
    }

    private fun displayName(uri: Uri, isTree: Boolean): String {
        return try {
            val queryUri = if (isTree) {
                val docId = DocumentsContract.getTreeDocumentId(uri)
                DocumentsContract.buildDocumentUriUsingTree(uri, docId)
            } else {
                uri
            }
            queryDisplayName(queryUri) ?: fallbackDisplayName(uri, isTree)
        } catch (_: Exception) {
            fallbackDisplayName(uri, isTree)
        }
    }

    private fun queryDisplayName(uri: Uri): String? {
        return try {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (index >= 0) cursor.getString(index)?.takeIf { it.isNotBlank() } else null
                } else {
                    null
                }
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun fallbackDisplayName(uri: Uri, isTree: Boolean): String {
        return try {
            if (isTree) {
                val docId = DocumentsContract.getTreeDocumentId(uri)
                docId.substringAfter(':', docId).substringAfterLast('/').ifBlank { "carpeta" }
            } else {
                uri.lastPathSegment?.substringAfterLast('/')?.ifBlank { "archivo" } ?: "archivo"
            }
        } catch (_: Exception) {
            if (isTree) "carpeta" else "archivo"
        }
    }

    private fun safeName(name: String): String {
        val cleaned = name.replace(Regex("[^A-Za-z0-9._-]+"), "_").trim('.', '_', '-')
        return cleaned.ifBlank { "unity_input" }
    }

    companion object {
        private const val REQ_INPUT_TREE = 1001
        private const val REQ_INPUT_FILE = 1002
        private const val REQ_OUTPUT_TREE = 1003
        private const val UPDATE_MANIFEST_URL =
            "https://raw.githubusercontent.com/CorvinPrice/ravennest-unity-extractor/main/version-extractor.json"
    }
}

object EngineBridge {
    private var nativeDecoderLoaded = false

    fun loadNativeDecoder() {
        if (nativeDecoderLoaded) return
        try {
            System.loadLibrary("raven_texture2ddecoder")
            nativeDecoderLoaded = true
        } catch (_: UnsatisfiedLinkError) {
            nativeDecoderLoaded = false
        }
    }

    fun python(activity: Activity): com.chaquo.python.PyObject {
        loadNativeDecoder()
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(activity))
        }
        val bridge = Python.getInstance().getModule("android_bridge")
        bridge.callAttr("set_native_lib_dir", activity.applicationInfo.nativeLibraryDir)
        return bridge
    }
}
