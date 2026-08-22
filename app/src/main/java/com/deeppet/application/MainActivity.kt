package com.deeppet.application

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

class MainActivity : ComponentActivity() {

    // 权限请求 launcher
    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { _ ->
        if (Settings.canDrawOverlays(this)) {
            // 使用默认参数启动（或从存储读取，这里简单处理）
            startFloatingService(100, 60)
        } else {
            Toast.makeText(this, "需要悬浮窗权限才能运行", Toast.LENGTH_SHORT).show()
        }
    }

    // 保存用户设置的参数，以便权限回调后启动
    private var pendingPrepareAdvance: Long = 100
    private var pendingOverlapDelay: Long = 60

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    MainScreen(
                        onStartFloating = { prepare, overlap ->
                            // 保存参数，然后检查权限
                            pendingPrepareAdvance = prepare
                            pendingOverlapDelay = overlap
                            handleStartFloating()
                        },
                        onStopFloating = { handleStopFloating() }
                    )
                }
            }
        }
    }

    private fun handleStartFloating() {
        if (Settings.canDrawOverlays(this)) {
            startFloatingService(pendingPrepareAdvance, pendingOverlapDelay)
        } else {
            requestOverlayPermission()
        }
    }

    private fun handleStopFloating() {
        stopService(Intent(this, FloatingWindowService::class.java))
        Toast.makeText(this, "已停止悬浮窗", Toast.LENGTH_SHORT).show()
    }

    private fun startFloatingService(prepareAdvance: Long, overlapDelay: Long) {
        val intent = Intent(this, FloatingWindowService::class.java).apply {
            putExtra("prepare_advance", prepareAdvance)
            putExtra("overlap_delay", overlapDelay)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        Toast.makeText(this, "悬浮窗已启动（参数：提前${prepareAdvance}ms，重叠${overlapDelay}ms）", Toast.LENGTH_SHORT).show()
    }

    private fun requestOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:${packageName}")
            )
            permissionLauncher.launch(intent)
        } else {
            startFloatingService(pendingPrepareAdvance, pendingOverlapDelay)
        }
    }
}