package com.deeppet.application

import android.content.Context
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.view.View
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout

/**
 * 负责管理宠物悬浮窗的动作按钮（watching、reading、searching）。
 * 按钮使用 assets/icons/ 下的 PNG 图片作为图标。
 */
class ActionButtonManager(
    private val context: Context,
    private val windowManager: WindowManager,
    private val screenWidth: Int,
    private val screenHeight: Int,
    private val petViewWidth: Int,
    private val petViewHeight: Int,
    private val edgePaddingPx: Int,
    private val edgePaddingPy: Int
) {

    // ---------- 内部状态 ----------
    private var actionFrame: View? = null
    private var actionButtons: List<ImageButton>? = null
    private var buttonOffset: Int? = null
    private val offsetY = 20

    // watching、reading、searching 的基础偏移
    private val baseOffsets = listOf(-5, 10, -5)
    private var listener: OnActionClickListener? = null

    // ---------- 尺寸辅助 ----------
    private fun dpToPx(dp: Int): Int = (dp * context.resources.displayMetrics.density).toInt()

    // ---------- 回调接口 ----------
    interface OnActionClickListener {
        fun onWatchingPhoneClick()
        fun onReadingClick()
        fun onSearchingClick()
    }

    fun setOnActionClickListener(listener: OnActionClickListener?) {
        this.listener = listener
    }

    // ---------- 公开 API ----------
    fun show(centerX: Int, centerY: Int) {
        removeInternal()

        val clampedX = centerX.coerceIn(
            edgePaddingPx + petViewWidth / 2,
            screenWidth - edgePaddingPx - petViewWidth / 2
        )
        val clampedY = centerY.coerceIn(
            edgePaddingPy + petViewHeight / 2,
            screenHeight - edgePaddingPy - petViewHeight / 2
        )

        val frame = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.TRANSPARENT)
            setPadding(dpToPx(4), dpToPx(4), dpToPx(4), dpToPx(4))
            clipChildren = false
            clipToPadding = false
        }

        val buttonSize = dpToPx(30)
        val buttonMargin = dpToPx(5)

        // 创建图标按钮
        fun createIconButton(iconFileName: String, baseOffset: Int, onClick: () -> Unit): ImageButton {
            return ImageButton(context).apply {
                try {
                    context.assets.open("icons/$iconFileName").use { inputStream ->
                        val bitmap = BitmapFactory.decodeStream(inputStream)
                        setImageBitmap(bitmap)
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                    // 如果图标加载失败，可以设置一个默认颜色或占位文字
                    setBackgroundColor(Color.GRAY)
                }
                scaleType = ImageView.ScaleType.CENTER_INSIDE
                setBackgroundColor(Color.TRANSPARENT)
                setPadding(0, 0, 0, 0)

                layoutParams = LinearLayout.LayoutParams(buttonSize, buttonSize).apply {
                    topMargin = buttonMargin
                    bottomMargin = buttonMargin
                    leftMargin = baseOffset
                }
                setOnClickListener { onClick() }
            }
        }

        // 创建三个按钮：watching、reading、searching
        val btnWatching = createIconButton("phone.png", baseOffsets[0]) {
            listener?.onWatchingPhoneClick()
        }
        val btnReading = createIconButton("book.png", baseOffsets[1]) {
            listener?.onReadingClick()
        }
        val btnSearching = createIconButton("search.png", baseOffsets[2]) {
            listener?.onSearchingClick()
        }

        val buttons = listOf(btnWatching, btnReading, btnSearching)
        actionButtons = buttons

        frame.addView(btnWatching)
        frame.addView(btnReading)
        frame.addView(btnSearching)

        // 测量框架以获取实际宽高
        val widthSpec = View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
        val heightSpec = View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
        frame.measure(widthSpec, heightSpec)
        val frameWidth = frame.measuredWidth
        val frameHeight = frame.measuredHeight

        // 计算框架位置（偏移逻辑）
        var offsetX = -200
        var left = clampedX + offsetX - frameWidth / 2
        if (left < edgePaddingPx) {
            offsetX = -offsetX
            left = clampedX + offsetX - frameWidth / 2
        } else if (left + frameWidth > screenWidth - edgePaddingPx) {
            offsetX = -offsetX
            left = clampedX + offsetX - frameWidth / 2
        }
        left = left.coerceIn(edgePaddingPx, screenWidth - frameWidth - edgePaddingPx)
        val top = (clampedY + offsetY - frameHeight / 2).coerceIn(
            edgePaddingPy,
            screenHeight - frameHeight - edgePaddingPy
        )

        buttonOffset = offsetX
        applyButtonOffsets(offsetX)

        val params = WindowManager.LayoutParams(
            frameWidth, frameHeight,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_PHONE
            },
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = android.view.Gravity.TOP or android.view.Gravity.START
            x = left
            y = top
        }

        windowManager.addView(frame, params)
        actionFrame = frame
    }

    fun updatePosition(centerX: Int, centerY: Int) {
        val frame = actionFrame ?: return
        val offsetX = buttonOffset ?: return

        var frameWidth = frame.width
        var frameHeight = frame.height
        if (frameWidth == 0 || frameHeight == 0) {
            // 若未测量，则用估算值（近似）
            frameWidth = dpToPx(160)
            frameHeight = dpToPx(50) * 3 + dpToPx(10) * 4
        }

        var left = centerX + offsetX - frameWidth / 2
        var needUpdateOffsets = false

        // 边界检测，若碰到屏幕边缘则翻转偏移
        if (left < edgePaddingPx) {
            val newOffset = -offsetX
            left = centerX + newOffset - frameWidth / 2
            if (left < edgePaddingPx) left = edgePaddingPx
            else if (left + frameWidth > screenWidth - edgePaddingPx) left = screenWidth - frameWidth - edgePaddingPx
            buttonOffset = newOffset
            needUpdateOffsets = true
        } else if (left + frameWidth > screenWidth - edgePaddingPx) {
            val newOffset = -offsetX
            left = centerX + newOffset - frameWidth / 2
            if (left < edgePaddingPx) left = edgePaddingPx
            else if (left + frameWidth > screenWidth - edgePaddingPx) left = screenWidth - frameWidth - edgePaddingPx
            buttonOffset = newOffset
            needUpdateOffsets = true
        }
        left = left.coerceIn(edgePaddingPx, screenWidth - frameWidth - edgePaddingPx)

        val top = (centerY + offsetY - frameHeight / 2).coerceIn(
            edgePaddingPy,
            screenHeight - frameHeight - edgePaddingPy
        )

        // 更新视图布局
        val params = frame.layoutParams as WindowManager.LayoutParams
        params.x = left
        params.y = top
        try {
            windowManager.updateViewLayout(frame, params)
            if (needUpdateOffsets) {
                buttonOffset?.let { applyButtonOffsets(it) }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun hide() {
        removeInternal()
    }

    fun isShowing(): Boolean = actionFrame != null

    fun release() {
        removeInternal()
        listener = null
    }

    // ---------- 私有辅助 ----------
    private fun removeInternal() {
        actionFrame?.let {
            if (it.isAttachedToWindow) {
                try {
                    windowManager.removeView(it)
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
            actionFrame = null
        }
        buttonOffset = null
        actionButtons = null
    }

    private fun applyButtonOffsets(offset: Int) {
        val buttons = actionButtons ?: return
        val direction = if (offset >= 0) 1 else -1
        buttons.forEachIndexed { index, button ->
            val base = baseOffsets[index]
            val newMargin = base * direction
            (button.layoutParams as? LinearLayout.LayoutParams)?.leftMargin = newMargin
            button.requestLayout()
        }
    }
}