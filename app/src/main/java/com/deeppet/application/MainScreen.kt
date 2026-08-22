package com.deeppet.application

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun MainScreen(
    onStartFloating: (prepareAdvance: Long, overlapDelay: Long) -> Unit,
    onStopFloating: () -> Unit
) {
    val prepareAdvance = remember { mutableStateOf(100f) }
    val overlapDelay = remember { mutableStateOf(60f) }

    // 动态计算 overlapDelay 的最大值（必须小于 prepareAdvance）
    val maxOverlap = (prepareAdvance.value - 1f).coerceAtLeast(20f)

    // 当 prepareAdvance 变化时，若 overlapDelay 不满足小于条件，则自动修正
    fun ensureOverlapLessThanPrepare() {
        if (overlapDelay.value >= prepareAdvance.value) {
            overlapDelay.value = (prepareAdvance.value - 1f).coerceAtLeast(20f)
        }
    }

    // 颜色定义（浅蓝主题）
    val primaryBlue = Color(0xFF1E88E5)
    val lightBlueBg = Color(0xFFE8F0FE)
    val textDark = Color(0xFF333333)
    val sliderTrackColor = Color(0xFFBBDEFB)
    val sliderThumbColor = primaryBlue

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // 标题：deeppet（蓝色）
        Text(
            text = "Deeppet",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = primaryBlue
        )
        Spacer(modifier = Modifier.height(32.dp))

        // 启动按钮
        Button(
            onClick = {
                onStartFloating(
                    prepareAdvance.value.toLong(),
                    overlapDelay.value.toLong()
                )
            },
            colors = ButtonDefaults.buttonColors(
                containerColor = lightBlueBg,
                contentColor = primaryBlue
            ),
            modifier = Modifier.padding(horizontal = 16.dp)
        ) {
            Text("启动 deeppet", fontSize = 16.sp)
        }
        Spacer(modifier = Modifier.height(12.dp))

        // 关闭按钮
        Button(
            onClick = onStopFloating,
            colors = ButtonDefaults.buttonColors(
                containerColor = lightBlueBg,
                contentColor = primaryBlue
            ),
            modifier = Modifier.padding(horizontal = 16.dp)
        ) {
            Text("关闭 deeppet", fontSize = 16.sp)
        }

        Spacer(modifier = Modifier.height(32.dp))

        // 分组标题：动画衔接设置
        Text(
            text = "动画衔接设置",
            fontSize = 16.sp,
            fontWeight = FontWeight.Medium,
            color = Color.Gray
        )
        Spacer(modifier = Modifier.height(16.dp))

        // 参数1：提前触发时机
        Text(
            text = "提前触发时机：${prepareAdvance.value.toInt()} ms",
            fontSize = 14.sp,
            color = textDark
        )
        Spacer(modifier = Modifier.height(4.dp))
        Slider(
            value = prepareAdvance.value,
            onValueChange = { newValue ->
                prepareAdvance.value = newValue
                ensureOverlapLessThanPrepare()
            },
            valueRange = 20f..200f,
            colors = SliderDefaults.colors(
                thumbColor = sliderThumbColor,
                activeTrackColor = sliderThumbColor,
                inactiveTrackColor = sliderTrackColor
            )
        )

        Spacer(modifier = Modifier.height(20.dp))

        // 参数2：动画重叠时间
        Text(
            text = "动画重叠时长：${overlapDelay.value.toInt()} ms",
            fontSize = 14.sp,
            color = textDark
        )
        Spacer(modifier = Modifier.height(4.dp))
        Slider(
            value = overlapDelay.value,
            onValueChange = { newValue ->
                overlapDelay.value = if (newValue >= prepareAdvance.value) {
                    (prepareAdvance.value - 1f).coerceAtLeast(20f)
                } else {
                    newValue
                }
            },
            valueRange = 20f..maxOverlap,
            colors = SliderDefaults.colors(
                thumbColor = sliderThumbColor,
                activeTrackColor = sliderThumbColor,
                inactiveTrackColor = sliderTrackColor
            )
        )
    }
}