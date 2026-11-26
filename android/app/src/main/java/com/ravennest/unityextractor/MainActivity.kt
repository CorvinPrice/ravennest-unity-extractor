package com.ravennest.unityextractor

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var results: TextView
    private var selectedInput: Uri? = null
    private var selectedInputIsTree = false
    private var selectedOutput: Uri? = null
    private val executor = Executors.newSingleThreadExecutor()

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

        root.addView(Button(this).apply {
            text = "Elegir carpeta de salida PNG"
            setOnClickListener {
                startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), REQ_OUTPUT_TREE)
            }
        })

        root.addView(Button(this).apply {
            text = "Listar Texture2D / Sprite"
            setOnClickListener { runEngine(export = false) }
        })

        root.addView(Button(this).apply {
            text = "Exportar PNG"
            setOnClickListener { runEngine(export = true) }
        })

        results = TextView(this).apply {
            text = ""
            textSize = 14f
            setTextColor(Color.rgb(220, 220, 230))
            setPadding(0, 24, 0, 0)
        }
        root.addView(ScrollView(this).apply { addView(results) })

        setContentView(root)
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }

    @Deprecated("MVP uses the framework result API to avoid an AndroidX dependency")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        when (requestCode) {
            REQ_INPUT_TREE -> {
                takePersistable(uri, write = false)
                selectedInput = uri
                selectedInputIsTree = true
                status.text = "Carpeta seleccionada: ${displayName(uri)}"
            }
            REQ_INPUT_FILE -> {
                takePersistable(uri, write = false)
                selectedInput = uri
                selectedInputIsTree = false
                status.text = "Archivo seleccionado: ${displayName(uri)}"
            }
            REQ_OUTPUT_TREE -> {
                takePersistable(uri, write = true)
                selectedOutput = uri
                status.text = "Salida seleccionada: ${displayName(uri)}"
            }
        }
    }

    private fun takePersistable(uri: Uri, write: Boolean) {
        var flags = Intent.FLAG_GRANT_READ_URI_PERMISSION
        if (write) flags = flags or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        try {
            contentResolver.takePersistableUriPermission(uri, flags)
        } catch (_: SecurityException) {
            // Some providers do not offer persistable grants; the current grant still works.
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
        status.text = if (export) "Exportando PNG..." else "Listando assets..."
        results.text = ""

        executor.execute {
            try {
                val copied = copySelectionToCache(input, inputIsTree)
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
                    status.text = "Error"
                    results.text = e.message ?: e.toString()
                }
            }
        }
    }

    private fun showListResult(payload: JSONObject, copied: File) {
        runOnUiThread {
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
                status.text = "No se pudo exportar"
                results.text = payload.optString("error", "Error desconocido")
            }
            return
        }
        val pngs = exportDir.listFiles { file -> file.isFile && file.name.endsWith(".png", ignoreCase = true) }
            ?.sortedBy { it.name }
            ?: emptyList()
        val destination = if (outputTree != null) {
            copyPngsToTree(pngs, outputTree)
            "carpeta de salida elegida"
        } else {
            val fallback = File(getExternalFilesDir(null), "RavenNestUnityExtractor/exports/${exportDir.name}")
            fallback.mkdirs()
            pngs.forEach { it.copyTo(File(fallback, it.name), overwrite = true) }
            fallback.absolutePath
        }
        runOnUiThread {
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

    private fun copySelectionToCache(uri: Uri, isTree: Boolean): File {
        val root = File(cacheDir, "input/session-${System.currentTimeMillis()}").apply { mkdirs() }
        if (isTree) {
            val rootDocId = DocumentsContract.getTreeDocumentId(uri)
            copyTree(uri, rootDocId, root, "")
        } else {
            copyDocument(uri, File(root, safeName(displayName(uri))))
        }
        return root
    }

    private fun copyTree(treeUri: Uri, parentDocId: String, destDir: File, relPath: String) {
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
                    copyTree(treeUri, docId, File(destDir, safeName(name)), childRel)
                } else if (shouldCopyUnityFile(name, childRel)) {
                    val docUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, docId)
                    copyDocument(docUri, File(destDir, safeName(name)))
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
        for (png in pngs) {
            val docUri = DocumentsContract.createDocument(contentResolver, parentUri, "image/png", png.name)
                ?: throw IOException("No se pudo crear ${png.name} en la carpeta de salida")
            val out = contentResolver.openOutputStream(docUri) ?: throw IOException("No se pudo escribir ${png.name}")
            out.use { stream -> png.inputStream().use { it.copyTo(stream) } }
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

    private fun displayName(uri: Uri): String {
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) return cursor.getString(index) ?: uri.toString()
            }
        }
        return uri.lastPathSegment ?: uri.toString()
    }

    private fun safeName(name: String): String {
        val cleaned = name.replace(Regex("[^A-Za-z0-9._-]+"), "_").trim('.', '_', '-')
        return cleaned.ifBlank { "unity_input" }
    }

    companion object {
        private const val REQ_INPUT_TREE = 1001
        private const val REQ_INPUT_FILE = 1002
        private const val REQ_OUTPUT_TREE = 1003
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
