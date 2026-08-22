# Deepseek-Android-Desktop-Pet

> 在安卓上运行deepseek桌宠

![平台](https://img.shields.io/badge/platform-Android-brightgreen)
![语言](https://img.shields.io/badge/language-Kotlin-orange)
![Python](https://img.shields.io/badge/language-Python-blue)
![许可证](https://img.shields.io/badge/license-MIT-blue)

---

## 📖 目录

- [项目介绍](#项目介绍)
- [功能特性](#功能特性)
- [效果预览](#效果预览)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [使用教程](#使用教程)
- [项目结构](#项目结构)
- [声明](#声明)
- [许可证](#许可证)
- [联系方式](#联系方式)
- [致谢](#致谢)

---

## 项目介绍

DeepPet 采用 WindowManager 实现全局悬浮窗，无论你在浏览网页、聊天还是玩游戏，宠物都会始终显示在屏幕最上层。它通过 WebView 播放透明背景的 WebM 视频来实现宠物的动态表现，并利用双视频无缝切换技术保证动作过渡自然流畅。

应用内置了丰富的动作库（待机、行走、鞠躬、害羞、生闷气等），并具备智能行为管理：宠物会在空闲时随机切换动作，当你点击它时，会触发可爱的反馈动画，并弹出三个功能按钮——看手机、看书、搜索，让宠物进入相应的循环行为模式，仿佛拥有自己的“小习惯”。

---

## 功能特性

### 核心功能

| 功能 | 说明 |
|------|------|
| 桌面悬浮显示 | 宠物以悬浮窗形式常驻桌面，不影响其他应用操作 |
| 自由拖拽移动 | 长按宠物可拖拽到桌面任意位置 |
| 点击触发动画 | 点击宠物会触发点击动画 |


### 技术亮点

# 技术亮点

## 🪟 悬浮窗服务与权限管理
- 基于 `WindowManager` 实现全局悬浮窗，适配 Android 6.0+ 的 `SYSTEM_ALERT_WINDOW` 权限动态申请。
- 通过 `ActivityResultLauncher` 优雅处理权限回调，并支持参数持久化，权限获取后自动恢复服务启动。
- 前台服务（`startForeground`）保证进程优先级，避免被系统回收。

## 🎞️ 双视频无缝衔接切换
- 采用 **双 `WebView` 视频叠加** 方案，利用两个 `<video>` 元素实现预加载 + 无缝切换。
- 结合 `prepareAdvance`（提前加载）和 `overlapDelay`（重叠时长）参数，精准控制切换时机，消除黑屏和加载延迟。
- 通过 JavaScript 与 Android 通信，实现视频源预加载、播放控制与位置交换，切换流畅自然。

## 🧠 智能行为管理系统
- 使用 `PetBehaviorManager` 集中管理所有动作（普通、循环、点击），支持随机选播、去重和方向识别。
- 支持 **循环模式**（`watching`、`reading`、`searching`），进入模式后以 90% 概率播放主循环动作，10% 随机播放同目录其他动作，模拟真实宠物行为。
- 动作切换时自动触发位移动画，利用 `ValueAnimator` 实现平滑左右移动，并结合屏幕边缘检测自动调整行走方向。

## 🎨 轻量级 UI 与性能优化
- 使用 `WebView` 渲染视频，配合 `LAYER_TYPE_HARDWARE` 硬件加速，降低 CPU 占用。
- 透明背景 + 无控件视频，实现纯宠物形象展示，无多余干扰。
- 所有视图（宠物、按钮）均为独立 `WindowManager` 层，互不影响，且支持全局屏幕适配。

---

**更多项目细节，请参阅源码实现。**

---

## 效果预览

### 主界面
![主界面截图](docs/images/main.png)

> 📌 截图待补充

### 对话功能
![对话截图](docs/images/chat.png)

> 📌 截图待补充

### 桌面宠物展示
![桌面宠物](docs/images/pet_display.png)

> 📌 截图待补充

---

## 环境要求

| 项目 | 要求 |
|------|------|
| Android 系统 | Android 7.0 (API 24) 及以上 |
| Android Studio | Ladybug \| 2024.2.1 或更新版本 |
| JDK | JDK 17 |
| Gradle | 8.0 及以上 |
| Kotlin | 1.9.0 及以上 |
| 测试设备 | 支持悬浮窗功能的 Android 手机 |

---

## 快速开始

### 1. 克隆项目

打开终端，执行以下命令：

```bash
git clone https://github.com/whz112/Deepseek-Android-Desktop-Pet.git
cd Deepseek-Android-Desktop-Pet
```

### 2. 打开项目

使用 Android Studio 打开项目根目录：

1. 启动 Android Studio
2. 点击 `Open` 或 `File → Open`
3. 选择项目根目录文件夹
4. 等待 Gradle 同步完成

> ⚠️ 如果同步失败，请检查网络连接，或尝试 `File → Invalidate Caches → Invalidate and Restart`


### 4. 运行项目

1. 连接 Android 设备（开启 USB 调试模式）或启动模拟器
2. 点击 Android Studio 工具栏的 `Run` 按钮（▶️）
3. 或使用快捷键 `Shift + F10`
4. 等待编译完成，应用自动安装到设备

---

## 使用教程

### 基础使用

#### 第一步：启动应用

安装 APK 后，点击桌面应用图标启动。首次启动时，应用会检查悬浮窗权限，如未授权，会弹出引导提示。

#### 第二步：开启悬浮窗权限

应用启动后，如果检测到未授予悬浮窗权限，会弹出引导对话框：

1. 点击弹窗中的「去设置」按钮，跳转到系统权限设置页面
2. 在系统设置页面中找到「Deepseek-Android-Desktop-Pet」
3. 开启「显示在其他应用上层」开关
4. 返回应用，权限状态会自动更新

> 不同品牌手机路径略有差异，也可在系统设置中直接搜索「悬浮窗」或「显示在其他应用上层」快速定位

#### 第三步：显示桌面宠物

- 应用启动后，宠物会自动显示在桌面
- 点击「关闭」按钮可以关闭宠物

---

## 项目结构

```
com.deeppet.application/
├── MainActivity.kt              # 主界面，权限管理，启动/停止服务
├── MainScreen.kt            #管理主页面的样式
├── FloatingWindowService.kt     # 悬浮窗服务，核心逻辑（视频播放、触摸、移动）
├── ActionButtonManager.kt       # 悬浮动作按钮管理（看手机/看书/搜索）
├── pet/
│   ├── manager/
│   │   └── PetBehaviorManager.kt   # 行为数据管理（动作分类、动作分发、模式切换）
│   ├── model/
│   │   └── PetAction.kt            # 动作数据模型
│   └── player/
│       └── PetVideoPlayer.kt       # 视频播放控制器（双视频无缝切换）
```


---

## 声明

### 免责声明

- 本项目仅供**学习交流**使用，**严禁用于商业用途**
- 本项目为第三方开源项目，**与 DeepSeek 官方无直接关联**

### 使用规范

- 请勿使用本项目进行任何违法、违规或侵犯他人权益的行为
- 请勿利用本应用传播违法信息或进行恶意攻击
- 尊重开源精神，二次分发请保留原作者信息和许可证声明
- 不得将本项目用于任何形式的商业牟利活动

### 数据隐私

- 本项目**不会主动收集或上传**用户的任何个人信息
- 如对隐私安全有更高要求，建议在使用前查看完整源代码

---

## 许可证

本项目基于 [MIT License](LICENSE) 开源。

```
MIT License

Copyright (c) 2026 whz112

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 联系方式

- **作者**：whz112
- **GitHub**：[whz112](https://github.com/whz112)
- **项目地址**：[Deepseek-Android-Desktop-Pet](https://github.com/whz112/Deepseek-Android-Desktop-Pet)
- **问题反馈**：[Issues](https://github.com/whz112/Deepseek-Android-Desktop-Pet/issues)
- **邮箱**：3067367688@qq.com

欢迎提交 Issue 和 Pull Request，共同完善本项目！

---

## 致谢

- 本项目的开发参考了以下优秀开源项目和作者：
- PC2005-cloud
- 链接：
- [https://github.com/PC2005-cloud/dsh-pet/tree/main](https://github.com/PC2005-cloud/dsh-pet/tree/main/scripts)


### 致歉声明

如本项目中引用了您的作品但未及时标注，请联系我补充署名，感谢您的理解与支持。

---

## Star History

如果觉得本项目对你有帮助，欢迎点个 Star ⭐ 支持一下！

[![Star History Chart](https://api.star-history.com/svg?repos=whz112/Deepseek-Android-Desktop-Pet&type=Date)](https://star-history.com/#whz112/Deepseek-Android-Desktop-Pet&Date)

---

**Happy Coding! 🚀**
```
