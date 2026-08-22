package com.deeppet.application.pet.manager

import com.deeppet.application.pet.model.PetAction
import java.util.Random

/**
 * 只负责提供动作数据，不参与播放控制
 * 根据资源路径自动区分：
 * - 普通动作：不含 "loop" 和 "click" 的路径
 * - 循环动作：路径包含 "loop"（用于 watching/reading/searching 模式）
 * - 点击动作：路径包含 "click"
 */
class PetBehaviorManager(
    private val allActions: List<PetAction>   // 所有动作（普通 + 循环 + 点击）
) {

    enum class Direction { LEFT, RIGHT, NONE }

    // ---------- 动作池分类 ----------
    private val normalActions: List<PetAction> = allActions.filter {
        !isClickAction(it) && !isLoopAction(it)
    }
    private val loopActions: List<PetAction> = allActions.filter {
        !isClickAction(it) && isLoopAction(it)
    }
    private val clickActions: List<PetAction> = allActions.filter { isClickAction(it) }

    private val random = Random()
    private var lastActionId: String? = null

    // ---------- 循环模式状态 ----------
    private var currentMode: String? = null
    // 缓存每个模式的动作列表（key: mode 名，value: 该 loop 目录下的所有动作）
    private val modeActionCache = mutableMapOf<String, List<PetAction>>()
    private val modeMainActionIdMap = mutableMapOf<String, String>()

    private val directionMap = mapOf(
        "walking-left" to Direction.LEFT,
        "walking-right" to Direction.RIGHT
    )

    init {
        require(normalActions.isNotEmpty()) { "至少需要一个非 loop 的普通动作" }
        // 可选：打印循环动作数量，方便调试
    }

    // ---------- 辅助判断 ----------
    private fun isClickAction(action: PetAction): Boolean {
        return action.assetPath.contains("click")
    }

    private fun isLoopAction(action: PetAction): Boolean {
        // 判断是否属于任何 loop 目录（如 loop_watching_phone, loop_reading_book 等）
        return action.assetPath.contains("loop")
    }

    // ---------- 核心随机逻辑 ----------
    fun getInitialAction(): PetAction = getRandomAction()

    fun getNextAction(exclude: String?): PetAction = getRandomAction(exclude)

    private fun getRandomAction(exclude: String? = null): PetAction {
        // 1. 如果处于循环模式，从对应的 loop 目录中按概率选取
        currentMode?.let { mode ->
            val actions = modeActionCache[mode]
            val mainId = modeMainActionIdMap[mode]
            if (actions != null && mainId != null) {
                val mainAction = actions.find { it.id == mainId }
                if (mainAction != null) {
                    // 90% 返回主动作，10% 从其他动作随机（如果只有一个动作则 100% 返回主动作）
                    if (actions.size == 1 || random.nextDouble() < 0.9) {
                        lastActionId = mainAction.id
                        return mainAction
                    } else {
                        val others = actions.filter { it.id != mainId }
                        if (others.isNotEmpty()) {
                            val selected = others[random.nextInt(others.size)]
                            lastActionId = selected.id
                            return selected
                        } else {
                            lastActionId = mainAction.id
                            return mainAction
                        }
                    }
                }
            }
            // 缓存异常，降级到普通随机（但理论上不会发生）
        }

        // 2. 普通模式：从 normalActions 中随机，避免与上一个重复，同时排除外部指定的 exclude
        if (normalActions.size == 1) return normalActions[0]
        var candidate: PetAction
        var attempts = 0
        do {
            candidate = normalActions[random.nextInt(normalActions.size)]
            attempts++
        } while ((candidate.id == lastActionId || candidate.id == exclude) && attempts < 20)
        lastActionId = candidate.id
        return candidate
    }

    fun getDirection(actionId: String): Direction {
        return directionMap[actionId] ?: Direction.NONE
    }

    // ---------- 点击动作 ----------
    fun getClickAction(): PetAction? {
        return if (clickActions.isNotEmpty()) {
            clickActions[random.nextInt(clickActions.size)]
        } else null
    }

    // ---------- 循环模式管理 ----------
    fun getWatchingLoopAction(): PetAction? {
        return enterMode("watching", "watching_phone")
    }

    fun getReadingLoopAction(): PetAction? {
        return enterMode("reading", "reading")  // 根据实际 id 调整
    }

    fun getSearchingLoopAction(): PetAction? {
        return enterMode("searching", "searching")   // 根据实际 id 调整
    }

    /**
     * 清空循环模式状态，恢复正常随机（从 normalActions 中选取）
     */
    fun clearLoopMode() {
        currentMode = null
        lastActionId = null
        // 缓存保留，下次进入可复用
    }

    // ---------- 内部辅助 ----------
    /**
     * 进入指定模式，从 loopActions 中筛选路径包含 "loop_$mode" 的动作，
     * 并缓存到 modeActionCache 中。
     * @return 主动作，若不存在则返回 null 且不改变模式
     */
    private fun enterMode(mode: String, mainActionId: String): PetAction? {
        // 从 loopActions 中筛选属于该目录的动作
        val actions = modeActionCache.getOrPut(mode) {
            loopActions.filter { it.assetPath.contains("loop_$mode") }
        }

        if (actions.isEmpty()) return null

        val mainAction = actions.find { it.id == mainActionId }
        if (mainAction == null) {
            // 主动作不在该目录中，无法进入模式
            return null
        }

        // 设置模式
        currentMode = mode
        modeMainActionIdMap[mode] = mainActionId
        lastActionId = mainAction.id   // 避免退出模式后第一次随机立刻重复（但清除时会置 null）
        return mainAction
    }
}