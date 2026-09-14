# which-keyboard

<p align="center">
  <a href="./README_EN.md"><img src="https://img.shields.io/badge/English-README-red" alt="English README"></a>
  <img src="https://img.shields.io/badge/platform-macOS-blue?logo=apple" alt="Platform: macOS">
  <img src="https://img.shields.io/badge/zsh-5.8%2B-blue" alt="zsh 5.8+">
  <img src="https://img.shields.io/badge/native-Objective--C-F05138" alt="Native helper: Objective-C">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?logo=open-source-initiative" alt="License: MIT"></a>
  <a href="https://github.com/Iristack/which-keyboard/stargazers"><img src="https://img.shields.io/github/stars/Iristack/which-keyboard?style=social" alt="GitHub Stars"></a>
</p>

**在 zsh 提示符中实时显示 macOS 当前输入法。**

切换输入法，标签随即更新，无需按回车或继续输入。支持左右位置、自定义标签和多行命令。

```text
# 左侧
[EN]   ~/project ❯ git status
[拼音] ~/project ❯ git status

# 右侧（默认）
~/project ❯ git status                              [拼音]
```

[快速开始](#快速开始) · [配置](#配置) · [使用限制](#使用限制) · [开发与测试](#开发与测试) · [参与贡献](#参与贡献)

## 特性

- **实时更新**：监听系统输入源变化，事件驱动，无定时轮询。
- **灵活显示**：标签可放在左侧或右侧，支持按输入源 ID 自定义名称。
- **保留编辑状态**：异步更新时保留命令内容和光标位置，支持多行输入。
- **减少重复计算**：缓存标签，显示内容不变时不重绘主题。
- **轻量依赖**：使用 macOS 原生 API，无需 `im-select`、辅助功能或键盘监听权限。

插件只读取输入源状态，不记录按键，也不自动切换输入法。

## 快速开始

### 环境要求

| 依赖 | 要求 |
| --- | --- |
| 系统 | macOS 本地桌面会话 |
| Shell | zsh 5.8+；已在 Apple Silicon / zsh 5.9 上验证 |
| 构建工具 | Xcode Command Line Tools，或包含 macOS SDK 的 Xcode |

### 安装

```sh
git clone https://github.com/Iristack/which-keyboard.git "$HOME/.local/share/which-keyboard"
make -C "$HOME/.local/share/which-keyboard"
```

在 `~/.zshrc` 的**主题初始化之后**添加：

```zsh
source "$HOME/.local/share/which-keyboard/which-keyboard.plugin.zsh"
```

打开新的终端窗口，切换 ABC 和系统拼音即可看到标签更新。也可以在当前 zsh 中执行上述 `source` 命令立即试用。

> 安装目录可以自行调整，修改对应的加载路径即可。项目不会自动修改 shell 配置或下载依赖。

## 配置

配置应放在插件的 `source` 行之前。

### 显示位置

默认显示在右侧。设置 `left` 可将标签放在原提示符前面：

```zsh
WHICH_KEYBOARD_POSITION=left
source "$HOME/.local/share/which-keyboard/which-keyboard.plugin.zsh"
```

加载后也可以即时切换：

```zsh
WHICH_KEYBOARD_POSITION=right  # left 或 right
which-keyboard-refresh
```

位置设置同时作用于普通提示符和多行命令的第二提示符，保留原有提示符内容。

### 自定义标签

默认使用系统提供的输入法名称。可以按输入源 ID 映射为短标签：

```zsh
typeset -A WHICH_KEYBOARD_LABELS=(
  com.apple.keylayout.ABC EN
  com.apple.inputmethod.SCIM.ITABC 拼音
)
WHICH_KEYBOARD_POSITION=left
source "$HOME/.local/share/which-keyboard/which-keyboard.plugin.zsh"
```

查看本机启用的输入源及其 ID：

```sh
"$HOME/.local/share/which-keyboard/build/which-keyboard" --list
```

标签按纯文本处理，不解析颜色或其他提示符代码。加载后修改映射，运行 `which-keyboard-refresh` 即可应用。

### 命令

| 命令 | 用途 |
| --- | --- |
| `which-keyboard-refresh` | 应用配置，并请求最新输入源状态 |
| `which-keyboard-unload` | 停止监听、移除插件钩子并恢复原提示符 |

重复加载不会启动多个监听进程。卸载后可再次 `source`。

<details>
<summary>高级配置与原生接口</summary>

可在加载前设置 `WHICH_KEYBOARD_BINARY`，指定兼容监听程序的绝对路径。

以下状态变量可供其他 shell 配置读取：

| 变量 | 内容 |
| --- | --- |
| `WHICH_KEYBOARD_INPUT_SOURCE_ID` | 系统输入源 ID |
| `WHICH_KEYBOARD_INPUT_SOURCE_NAME` | 系统提供的显示名称 |
| `WHICH_KEYBOARD_LABEL` | 应用映射后的标签 |

在仓库目录运行原生工具：

```sh
./build/which-keyboard --once   # 查询当前输入源
./build/which-keyboard --list   # 列出启用且可选择的输入源
./build/which-keyboard --watch  # 输出初始状态和后续变更，Ctrl-C 退出
```

输出格式为 UTF-8 `ID<TAB>名称<换行>`。监听模式下收到 `SIGUSR1` 会输出最新快照。

</details>

## 更新与卸载

更新源码并重新编译：

```sh
git -C "$HOME/.local/share/which-keyboard" pull --ff-only
make -C "$HOME/.local/share/which-keyboard"
```

在已加载插件的终端中重新加载：

```zsh
which-keyboard-unload
source "$HOME/.local/share/which-keyboard/which-keyboard.plugin.zsh"
```

卸载时，执行 `which-keyboard-unload`，并删除 `~/.zshrc` 中的加载行和相关配置；不再使用的安装目录可以自行删除。

## 使用限制

| 场景 | 当前支持情况 |
| --- | --- |
| 系统输入源切换，例如 ABC ↔ 系统拼音 | 支持实时显示 |
| 搜狗、鼠须管内部通过 Shift 切换中英文 | 若系统输入源未改变，则无法区分内部模式 |
| 多行命令 | 支持，第二提示符使用相同的位置设置 |
| Vim、less 或其他前台命令运行中 | 不显示标签，回到 zsh 行编辑时恢复 |
| Powerlevel10k、Starship 等复杂主题 | 尚未专门适配，兼容性需验证 |
| SSH 远端、tmux 多客户端 | 不支持获取远端对应的本地输入源，也未实现按客户端区分 |

右侧标签可能在命令过长时被 zsh 隐藏；启用 `SINGLE_LINE_ZLE` 等不显示右侧提示符的配置时，请使用左侧模式。

输入源状态来自当前 macOS 桌面。后台终端可能收到其他应用引起的变更，回到终端时会重新同步。

## 工作原理

每个 shell 启动一个原生监听进程，通过 macOS 的输入源变更通知查询当前状态，并写入管道。zsh 使用 `zle -F` 异步接收事件，仅在提示符内容变化时调用 `zle reset-prompt` 重绘。

标签缓存在 `precmd` 阶段准备好，避免每次进入命令行时重复展开主题。插件退出时清理监听进程；监听异常结束后移除标签，下次进入命令行时尝试重启。

## 性能

Apple Silicon / zsh 5.9 / 简单提示符下的连续切换样本（2026-09-14）：

| 测量 | 样本数 | 中位数 | P95 | 最大值 |
| --- | --- | --- | --- | --- |
| 模拟事件写入 → PTY 输出新标签 | 100 | 0.162 ms | 0.207 ms | 0.299 ms |
| 调用系统切换接口 → PTY 输出新标签 | 20 | 5.111 ms | 6.946 ms | 41.725 ms |

测量不包含快捷键识别、终端画面呈现及显示器刷新时间。结果来自单机短时样本，实际表现取决于系统、终端和主题，不能视为跨设备保证。

## 开发与测试

开发测试额外需要 Python 3，使用标准库，无需安装 Python 依赖。在仓库目录执行：

```sh
make        # 编译原生监听程序
make test   # 语法检查、原生接口与 PTY 集成测试
```

默认测试不会切换系统输入法，覆盖异步重绘、光标和编辑内容、多行输入、提示符兼容、标签转义及进程生命周期。

运行无需切换系统输入法的性能基准：

```sh
python3 tools/benchmark.py
```

以下命令会短暂切换真实输入源，并在结束时尝试恢复原状态；需要至少两个启用的输入源：

```sh
WK_TEST_REAL_SWITCH=1 python3 -m unittest discover -s tests -v
python3 tools/benchmark.py --real-switch --switches 20
```

## 参与贡献

欢迎通过 [Issues](https://github.com/Iristack/which-keyboard/issues) 反馈问题或提出建议，也欢迎提交 Pull Request。

反馈问题时，请提供 macOS 与 zsh 版本、终端及主题名称、使用的输入法，以及最小复现步骤。涉及界面显示的问题，可附上已隐去个人信息的截图。

提交代码前请运行 `make test`。涉及提示符重绘的改动，请一并检查多行输入、光标位置和已有主题内容是否保持正常。

## 许可证

本项目采用 [MIT 许可证](./LICENSE)。
