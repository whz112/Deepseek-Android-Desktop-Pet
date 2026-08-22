package com.deeppet.application

import android.animation.ValueAnimator
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.animation.AccelerateDecelerateInterpolator
import android.view.animation.Interpolator
import android.view.animation.LinearInterpolator
import android.widget.Toast
import androidx.core.app.NotificationCompat
import com.deeppet.application.pet.manager.PetBehaviorManager
import com.deeppet.application.pet.model.PetAction
import com.deeppet.application.pet.player.PetVideoPlayer

class FloatingWindowService : Service(), PetVideoPlayer.OnActionChangeListener {

    private lateinit var windowManager: WindowManager
    private lateinit var manager: PetBehaviorManager
    private var player: PetVideoPlayer? = null

    // ---------- 边距（像素值） ----------
    private val edgePaddingPx = 20   // 左右边距
    private val edgePaddingPy = 40   // 上下边距

    private val layoutParams = WindowManager.LayoutParams(
        400, 400,
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        },
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
        PixelFormat.TRANSLUCENT
    ).apply {
        gravity = Gravity.TOP or Gravity.START
        x = edgePaddingPx
        y = edgePaddingPy
    }

    // ---------- 移动参数 ----------
    private data class MoveParams(
        val distance: Int,
        val startDelay: Long,
        val duration: Long,
        val interpolator: Interpolator
    )

    private val actionMoveParams = mapOf(
        "walking-left" to MoveParams(
            distance = -100,
            startDelay = 1600,
            duration = 4000,
            interpolator = AccelerateDecelerateInterpolator()
        ),
        "walking-right" to MoveParams(
            distance = 180,
            startDelay = 1000,
            duration = 7500,
            interpolator = AccelerateDecelerateInterpolator()
        )
    )

    private val defaultMoveParams = MoveParams(
        distance = 0,
        startDelay = 0,
        duration = 0,
        interpolator = LinearInterpolator()
    )

    private fun getMoveParams(actionId: String): MoveParams {
        return actionMoveParams[actionId] ?: defaultMoveParams
    }

    private var moveAnimator: ValueAnimator? = null
    private var screenWidth = 0
    private val viewWidth = 400
    private val viewHeight = 400

    // ================== 动作按钮管理器 ==================
    private lateinit var actionButtonManager: ActionButtonManager

    // ================== 生命周期与核心逻辑 ==================

    override fun onCreate() {
        super.onCreate()
        startForegroundService()

        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        screenWidth = resources.displayMetrics.widthPixels

        // 初始化动作按钮管理器
        actionButtonManager = ActionButtonManager(
            context = this,
            windowManager = windowManager,
            screenWidth = screenWidth,
            screenHeight = resources.displayMetrics.heightPixels,
            petViewWidth = viewWidth,
            petViewHeight = viewHeight,
            edgePaddingPx = edgePaddingPx,
            edgePaddingPy = edgePaddingPy
        )
        // 设置按钮点击回调
        actionButtonManager.setOnActionClickListener(object : ActionButtonManager.OnActionClickListener {
            override fun onWatchingPhoneClick() {
                actionButtonManager.hide()

                manager.getWatchingLoopAction()?.let { loopAction ->
                    player?.forcePlay(loopAction)
                }
            }

            override fun onReadingClick() {
                actionButtonManager.hide()

                manager.getReadingLoopAction()?.let { loopAction ->
                    player?.forcePlay(loopAction)
                }
            }

            override fun onSearchingClick() {
                actionButtonManager.hide()

                manager.getSearchingLoopAction()?.let { loopAction ->
                    player?.forcePlay(loopAction)
                }
            }
        })

        val allActions = listOf(
            PetAction("idle", "pets/idle/idle.webm", 11120L),
            PetAction("sleepy", "pets/sleepy/sleepy.webm", 10760L),
            PetAction("walking-left", "pets/walk/walking-left.webm", 10760L),
            PetAction("walking-right", "pets/walk/walking-right.webm", 10760L),
            PetAction("bowing", "pets/click/bowing.webm", 5042L),
            PetAction("shy", "pets/click/shy.webm", 5042L),
            PetAction("sulking", "pets/click/sulking.webm", 5042L),
            PetAction("watching_phone", "pets/loop_watching_phone/watching_phone.webm", 5480L),
            PetAction("reading", "pets/loop_reading/reading.webm", 5480L),
            PetAction("searching", "pets/loop_searching/searching.webm", 5480L),
        )

        manager = PetBehaviorManager(allActions)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val prepare = intent?.getLongExtra("prepare_advance", 100L) ?: 100L
        val overlap = intent?.getLongExtra("overlap_delay", 60L) ?: 60L

        if (player == null) {
            player = PetVideoPlayer(this, manager, prepare, overlap).apply {
                setOnActionChangeListener(this@FloatingWindowService)
            }
            val webView = player!!.getWebView()
            val screenHeight = resources.displayMetrics.heightPixels
            layoutParams.x = layoutParams.x.coerceIn(edgePaddingPx, screenWidth - viewWidth - edgePaddingPx)
            layoutParams.y = layoutParams.y.coerceIn(edgePaddingPy, screenHeight - viewHeight - edgePaddingPy)
            windowManager.addView(webView, layoutParams)
            setupTouch(webView)
            player!!.start()
        } else {
            player!!.setPrepareAdvance(prepare)
            player!!.setOverlapDelay(overlap)
        }

        return START_STICKY
    }

    override fun onActionChanged(newAction: PetAction) {
        val params = getMoveParams(newAction.id)
        when (manager.getDirection(newAction.id)) {
            PetBehaviorManager.Direction.LEFT,
            PetBehaviorManager.Direction.RIGHT -> {
                if (params.distance != 0) startMoving(params) else stopMoving()
                // 行走时自动关闭按钮（可选）
                if (actionButtonManager.isShowing()) {
                    actionButtonManager.hide()
                }
            }
            else -> stopMoving()
        }
    }

    private fun startMoving(params: MoveParams) {
        stopMoving()

        val startX = layoutParams.x
        val endX = (startX + params.distance)
            .coerceIn(edgePaddingPx, screenWidth - viewWidth - edgePaddingPx)

        moveAnimator = ValueAnimator.ofInt(startX, endX).apply {
            duration = params.duration
            interpolator = params.interpolator
            startDelay = params.startDelay

            addUpdateListener {
                layoutParams.x = it.animatedValue as Int
                try {
                    player?.getWebView()?.let { view ->
                        windowManager.updateViewLayout(view, layoutParams)
                        // 同步更新按钮框架位置
                        updateActionButtonPosition()
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
            start()
        }
    }

    private fun stopMoving() {
        moveAnimator?.cancel()
        moveAnimator = null
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun setupTouch(view: View) {
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f
        var downTime = 0L

        view.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialX = layoutParams.x
                    initialY = layoutParams.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    downTime = System.currentTimeMillis()
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val deltaX = (event.rawX - initialTouchX).toInt()
                    val deltaY = (event.rawY - initialTouchY).toInt()
                    var newX = initialX + deltaX
                    var newY = initialY + deltaY
                    val screenHeight = resources.displayMetrics.heightPixels
                    newX = newX.coerceIn(edgePaddingPx, screenWidth - viewWidth - edgePaddingPx)
                    newY = newY.coerceIn(edgePaddingPy, screenHeight - viewHeight - edgePaddingPy)
                    layoutParams.x = newX
                    layoutParams.y = newY
                    stopMoving()
                    try {
                        windowManager.updateViewLayout(view, layoutParams)
                        // 同步更新按钮框架位置
                        updateActionButtonPosition()
                    } catch (e: Exception) {
                        e.printStackTrace()
                    }
                    true
                }
                MotionEvent.ACTION_UP -> {
                    val deltaX = (event.rawX - initialTouchX).toInt()
                    val deltaY = (event.rawY - initialTouchY).toInt()
                    val distance = kotlin.math.sqrt((deltaX * deltaX + deltaY * deltaY).toDouble())
                    if (distance < 15 && (System.currentTimeMillis() - downTime) < 500) {
                        handleClick()
                    }
                    true
                }
                else -> false
            }
        }
    }

    private fun handleClick() {
        stopMoving()

        manager.clearLoopMode()
        // 播放点击动画（原有逻辑）
        manager.getClickAction()?.let { clickAction ->
            player?.forcePlay(clickAction)
        }
        // 切换按钮显示状态
        val centerX = layoutParams.x + viewWidth / 2
        val centerY = layoutParams.y + viewHeight / 2
        if (actionButtonManager.isShowing()) {
            actionButtonManager.hide()
        } else {
            actionButtonManager.show(centerX, centerY)
        }
    }

    /**
     * 当宠物位置发生变化时，调用此方法同步更新按钮框架的位置。
     */
    private fun updateActionButtonPosition() {
        if (actionButtonManager.isShowing()) {
            val centerX = layoutParams.x + viewWidth / 2
            val centerY = layoutParams.y + viewHeight / 2
            actionButtonManager.updatePosition(centerX, centerY)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        stopForeground(true)
        stopMoving()
        actionButtonManager.release() // 释放并移除按钮

        val webView = player?.getWebView()
        webView?.let {
            if (it.isAttachedToWindow) {
                try {
                    windowManager.removeView(it)
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
        }

        player?.release()
        player = null
    }

    override fun onBind(intent: Intent?): IBinder? = null

    @SuppressLint("ForegroundServiceType")
    private fun startForegroundService() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "floating_service_channel",
                "悬浮窗服务",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "用于显示宠物悬浮窗"
                setShowBadge(false)
            }
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(this, "floating_service_channel")
            .setContentTitle("宠物悬浮窗")
            .setContentText("宠物正在运行中...")
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        startForeground(1001, notification)
    }
}