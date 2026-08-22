package com.deeppet.application.pet.player

import android.content.Context
import android.graphics.Color
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import com.deeppet.application.pet.manager.PetBehaviorManager
import com.deeppet.application.pet.model.PetAction

/**
 * 内部自动循环播放，支持动态调整切换参数
 * 新增：强制播放接口 forcePlay
 */
class PetVideoPlayer(
    context: Context,
    private val manager: PetBehaviorManager,
    private var prepareAdvanceMs: Long = 100,
    private var overlapDelayMs: Long = 60
) {

    // ---------- 监听器接口 ----------
    interface OnActionChangeListener {
        fun onActionChanged(newAction: PetAction)
    }

    private var actionListener: OnActionChangeListener? = null

    fun setOnActionChangeListener(listener: OnActionChangeListener?) {
        actionListener = listener
    }

    // ---------- 原有成员 ----------
    private val webView: WebView
    private val handler = Handler(Looper.getMainLooper())

    private var currentAction: PetAction? = null
    private var nextAction: PetAction? = null
    private var currentStartTime: Long = 0
    private var nextStartTime: Long? = null

    private var prepareRunnable: Runnable? = null
    private var finishRunnable: Runnable? = null

    private var isPageReady = false
    private var pendingPlayAction: PetAction? = null
    private var pendingPreloadAction: PetAction? = null

    fun setPrepareAdvance(ms: Long) {
        prepareAdvanceMs = ms
        if (currentAction != null && nextAction != null) {
            schedulePrepare()
        }
    }

    fun setOverlapDelay(ms: Long) {
        overlapDelayMs = ms
    }

    init {
        webView = WebView(context).apply {
            setBackgroundColor(Color.TRANSPARENT)
            setLayerType(View.LAYER_TYPE_HARDWARE, null)

            settings.apply {
                javaScriptEnabled = true
                allowFileAccess = true
                mediaPlaybackRequiresUserGesture = false
                cacheMode = WebSettings.LOAD_NO_CACHE
                domStorageEnabled = true
                setSupportZoom(false)
                builtInZoomControls = false
                displayZoomControls = false
            }

            isVerticalScrollBarEnabled = false
            isHorizontalScrollBarEnabled = false

            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView?, url: String?) {
                    isPageReady = true
                    pendingPreloadAction?.let { preload(it) }
                    pendingPlayAction?.let { play(it) }
                    pendingPreloadAction = null
                    pendingPlayAction = null
                }
            }

            loadDataWithBaseURL(
                "file:///android_asset/",
                getHtmlWithTwoVideos(),
                "text/html",
                "UTF-8",
                null
            )
        }
    }

    fun start() {
        if (!isPageReady) {
            handler.post {
                if (isPageReady) startInternal() else start()
            }
            return
        }
        startInternal()
    }

    private fun startInternal() {
        val initial = manager.getInitialAction()
        val next = manager.getNextAction(initial.id)
        preload(next)
        play(initial)
    }

    // ---------- 原有 play 改为 internal（模块内可见） ----------
    internal fun play(action: PetAction) {
        if (!isPageReady) {
            pendingPlayAction = action
            return
        }

        cancelAllTimers()
        currentAction = action
        currentStartTime = System.currentTimeMillis()
        nextStartTime = null

        webView.evaluateJavascript("playVideo('${action.assetPath}')", null)
        scheduleFinish(action.durationMs)
        schedulePrepare()

        actionListener?.onActionChanged(action)
    }

    private fun preload(action: PetAction) {
        if (!isPageReady) {
            pendingPreloadAction = action
            return
        }

        nextAction = action
        webView.evaluateJavascript("preloadVideoSrc('${action.assetPath}')", null)

        if (currentAction != null) {
            schedulePrepare()
        }
    }

    // ---------- 新增：强制播放接口 ----------
    fun forcePlay(action: PetAction, nextAction: PetAction? = null) {
        // 1. 取消所有定时任务
        cancelAllTimers()

        // 2. 确定下一个动作
        val next = nextAction ?: manager.getNextAction(action.id)
        this.nextAction = next

        // 3. 预加载下一个动作（确保切换时 ready）
        preload(next)

        // 4. 播放当前动作（会重置状态并调度切换）
        play(action)
    }

    fun release() {
        cancelAllTimers()
        currentAction = null
        nextAction = null
        pendingPlayAction = null
        pendingPreloadAction = null
        try {
            webView.stopLoading()
            webView.loadUrl("about:blank")
            webView.destroy()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun getWebView(): WebView = webView

    // ---------- 私有方法 ----------
    private fun cancelAllTimers() {
        prepareRunnable?.let { handler.removeCallbacks(it) }
        finishRunnable?.let { handler.removeCallbacks(it) }
        prepareRunnable = null
        finishRunnable = null
    }

    private fun scheduleFinish(delayMs: Long) {
        finishRunnable?.let { handler.removeCallbacks(it) }
        val runnable = Runnable {
            finishRunnable = null
        }
        finishRunnable = runnable
        handler.postDelayed(runnable, delayMs)
    }

    private fun schedulePrepare() {
        prepareRunnable?.let { handler.removeCallbacks(it) }
        prepareRunnable = null

        val current = currentAction ?: return
        val next = nextAction ?: return

        val elapsed = System.currentTimeMillis() - currentStartTime
        val remaining = current.durationMs - elapsed

        if (remaining > prepareAdvanceMs) {
            val delay = remaining - prepareAdvanceMs
            val runnable = Runnable { prepareSwitch() }
            prepareRunnable = runnable
            handler.postDelayed(runnable, delay)
        } else if (remaining > 0) {
            prepareSwitch()
        } else {
            prepareSwitch()
        }
    }

    private fun prepareSwitch() {
        prepareRunnable?.let { handler.removeCallbacks(it) }
        prepareRunnable = null

        val next = nextAction ?: return

        nextStartTime = System.currentTimeMillis()

        webView.evaluateJavascript("moveNextToLeftAndPlay($overlapDelayMs)", null)

        handler.postDelayed({
            currentAction = next
            currentStartTime = nextStartTime ?: System.currentTimeMillis()
            nextStartTime = null

            actionListener?.onActionChanged(next)

            val newNext = manager.getNextAction(currentAction?.id)
            nextAction = newNext
            preload(newNext)
            schedulePrepare()
        }, overlapDelayMs + 30)
    }

    // ---------- HTML（不变） ----------
    private fun getHtmlWithTwoVideos(): String = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        html, body { margin:0; padding:0; width:100%; height:100%; overflow:hidden; background:transparent; }
        video {
            position: absolute;
            top: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
            background: transparent;
            outline: none;
            border: none;
            display: block;
        }
        video::-webkit-media-controls { display:none !important; }
        .pos-left { left: 0; }
        .pos-right { left: 100%; }
    </style>
</head>
<body>
    <video id="video0" muted playsinline preload="auto" class="pos-left" poster="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"></video>
    <video id="video1" muted playsinline preload="auto" class="pos-right" poster="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"></video>
    <script>
        var video0 = document.getElementById('video0');
        var video1 = document.getElementById('video1');
        var currentVideo = video0;
        var nextVideo = video1;

        function setPosition(video, pos) {
            video.className = pos === 'left' ? 'pos-left' : 'pos-right';
        }

        function playVideo(src) {
            currentVideo.src = src;
            currentVideo.load();
            currentVideo.play().catch(function(e){ console.log('play error:', e); });
        }

        function preloadVideoSrc(src) {
            nextVideo.src = src;
            nextVideo.load();
            nextVideo.play().then(function() { nextVideo.pause(); }).catch(function(e){});
        }

        function moveNextToLeftAndPlay(delay) {
            setPosition(nextVideo, 'left');
            nextVideo.play().catch(function(e){});
            setTimeout(function() {
                moveCurrentToRight();
            }, delay);
        }

        function moveCurrentToRight() {
            setPosition(currentVideo, 'right');
            currentVideo.pause();
            var temp = currentVideo;
            currentVideo = nextVideo;
            nextVideo = temp;
            setPosition(currentVideo, 'left');
            currentVideo.style.left = '';
        }
    </script>
</body>
</html>
""".trimIndent()
}