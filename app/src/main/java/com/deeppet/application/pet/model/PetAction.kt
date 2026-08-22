package com.deeppet.application.pet.model

/**
 * 纯数据契约，固化一次播放所需的所有元数据
 */
data class PetAction(
    val id: String,          // 动作唯一标识，如 "idle", "walk", "eat"
    val assetPath: String,   // assets 目录下的相对路径，如 "pets/idle/idle.webm"
    val durationMs: Long     // 硬编码的视频时长（毫秒）
)