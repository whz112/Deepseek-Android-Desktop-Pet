package com.deeppet.application.pet.player

import com.deeppet.application.pet.model.PetAction

/**
 * 定义 Player 与外部（Manager）的通信协议
 */
interface PlayerCallback {
    fun onPlaybackComplete(actionId: String)
}