# which-keyboard

在 macOS 的 zsh 提示符中实时显示当前输入法，支持左侧或右侧（默认）。切换输入法时自动刷新，不需要按回车或继续打字。

```text
~/project ❯ git status                              [ABC]
~/project ❯ git status                              [拼音]
```

## 安装与试用

需要 macOS、zsh 5.8+ 和 Xcode Command Line Tools（提供 `clang`、`make` 和系统 SDK）。目前在 macOS / Apple Silicon / zsh 5.9 上开发和验证。

克隆仓库并编译：

```sh
git clone https://github.com/Iristack/which-keyboard.git "$HOME/.local/share/which-keyboard"
cd "$HOME/.local/share/which-keyboard"
make
```

然后在你自己的交互式 zsh 中加载：

```zsh
source "$HOME/.local/share/which-keyboard/which-keyboard.plugin.zsh"
```

切换 ABC 和系统拼音，右侧标签应自动变化。默认显示系统提供的输入法名称，名称的语言取决于系统 API 返回的本地化结果。

确认可用后，将上述 `source` 行添加到 `~/.zshrc` **主题初始化之后**。更换安装目录时，修改路径即可。项目不会自动修改你的 shell 配置，也不会自动编译或下载程序。

无需安装 `im-select`，也不需要辅助功能或键盘监听权限。插件只查询输入源，不记录按键，不自动切换输入法。

## 显示在左侧

在加载插件前设置 `WHICH_KEYBOARD_POSITION=left`：

```zsh
WHICH_KEYBOARD_POSITION=left
source "$HOME/.local/share/which-keyboard/which-keyboard.plugin.zsh"
```

标签会放在原提示符前面，例如：

```text
[拼音] ~/project ❯ git status
```

已经加载新版插件时，可直接切换，无需重新编译：

```zsh
WHICH_KEYBOARD_POSITION=left  # 改为 right 切回右侧
which-keyboard-refresh
```

从不支持位置配置的旧版升级时，先执行 `which-keyboard-unload`，再设置位置并重新 `source`。要永久生效，把位置设置放在 `~/.zshrc` 的插件加载行之前。卸载和左右切换都会恢复另一侧原有内容；多行命令的第二提示符使用同样的位置。

## 自定义标签

在加载插件之前设置输入源 ID 对应的短名称：

```zsh
typeset -A WHICH_KEYBOARD_LABELS=(
  com.apple.keylayout.ABC EN
  com.apple.inputmethod.SCIM.ITABC 拼音
)
source "$HOME/.local/share/which-keyboard/which-keyboard.plugin.zsh"
```

查询本机启用的输入源 ID：

```sh
./build/which-keyboard --list
```

也可以加载后修改标签并刷新：

```zsh
WHICH_KEYBOARD_LABELS[com.apple.keylayout.ABC]=ABC
which-keyboard-refresh
```

标签作为纯文本处理，不能包含用于着色的 zsh 提示符代码。

## 命令与状态

```zsh
which-keyboard-refresh  # 重新读取输入源，并应用标签配置
which-keyboard-unload   # 停止监听，移除钩子，恢复原来的提示符
```

卸载后可以重新 `source`。重复加载不会启动多个监听程序。

插件提供以下只读用途的状态变量：

| 变量 | 内容 |
| --- | --- |
| `WHICH_KEYBOARD_INPUT_SOURCE_ID` | 系统输入源 ID |
| `WHICH_KEYBOARD_INPUT_SOURCE_NAME` | 系统提供的显示名称 |
| `WHICH_KEYBOARD_LABEL` | 应用自定义映射后的标签 |

监听程序支持：

```sh
./build/which-keyboard --once   # 当前输入源
./build/which-keyboard --list   # 启用且可选择的键盘输入源
./build/which-keyboard --watch  # 初始状态及后续变更，Ctrl-C 退出
```

输出协议为 UTF-8 `ID<TAB>名称<换行>`。`--watch` 收到 `SIGUSR1` 时会输出新快照。高级用途可在加载前设置 `WHICH_KEYBOARD_BINARY` 为兼容监听程序的绝对路径。

## 工作方式

- 一个 shell 对应一个小型原生监听进程，通过 macOS 的 `kTISNotifySelectedKeyboardInputSourceChanged` 获取输入源变化，使用 `TISCopyCurrentKeyboardInputSource()` 查询状态。
- 切换前台应用时重新同步；应用激活后额外延迟 100 ms 查询一次，处理输入源恢复的时序。
- 原生通知直接在主运行循环处理，避免额外的操作队列转发；zsh 使用 `zle -F` 接收管道事件，通过 `zle reset-prompt` 重绘，保留正在编辑的命令和光标。
- 缓存标签在 `precmd` 阶段准备好，普通命令行只展开一次主题。标签未变化时不重绘，包括多个输入源映射到同一标签的情况。
- 不做定时轮询，不在每次提示符展开时执行外部查询。每次开始编辑新的命令行时请求一次最新快照。
- 管道按非阻塞方式读取，支持分段消息；退出、卸载时清理监听。监听异常结束后移除标签，下次开始编辑时重启。
- 普通提示符和多行命令的第二提示符均显示标签，保留已有 `PROMPT` / `PROMPT2` / `RPROMPT` / `RPROMPT2` 内容。左侧模式前置标签，右侧模式追加标签。

## 范围与限制

- 显示的是**系统输入源**。搜狗、鼠须管内部通过 Shift 切换的中英文模式，若不改变系统输入源，则不会被识别为「中 / EN」。本版本不做这类输入法专属适配。
- 只有 zsh 的行编辑器活动时才刷新。运行 Vim、less 或其他命令时不会向终端插入标签；回到 shell 后恢复显示。
- 右侧模式下，长命令占满行时标签可能被 zsh 自动隐藏；`SINGLE_LINE_ZLE` 等禁用右侧提示符的配置不适用。可切换到左侧显示。
- 普通 zsh 提示符已验证。Powerlevel10k、Starship 等自行管理异步重绘的主题尚未专门适配，不能保证兼容。
- 针对本地桌面会话。SSH 远端不能直接获取你本地 Mac 的输入法；tmux 多客户端没有独立的输入源映射。
- macOS 输入源是当前桌面状态，后台终端会话也可能收到其他应用引起的变化；回到终端时重新同步。

## 测试

```sh
make test
```

默认测试不修改系统输入法。测试包括原生快照、监听和刷新信号，以及使用模拟输入源的真实 PTY / zsh 行编辑测试：无按键刷新、编辑缓冲区和光标、多行输入、退出码、主题内容保留、标签转义、分段/畸形消息、重复加载、卸载、进程退出及恢复。

如需验证真实的系统输入源变更通知，可以显式运行以下测试。它需要至少两个启用的输入源，会短暂切换到另一个输入源，并在 `finally` 中恢复原输入源：

```sh
WK_TEST_REAL_SWITCH=1 python3 -m unittest discover -s tests -v
```

候选框显示期间的视觉效果、不同终端和复杂主题仍需手工验收。

## 响应时间与基准

2026-09-14 在本机 Apple Silicon / zsh 5.9 / 简单提示符上的短时测试结果：

| 测量 | 样本数 | 中位数 | P95 | 最大值 |
| --- | --- | --- | --- | --- |
| 模拟输入源事件写入到 PTY 输出新标签 | 100 | 0.162 ms | 0.207 ms | 0.299 ms |
| 调用系统输入源切换到 PTY 输出新标签 | 20 | 5.111 ms | 6.946 ms | 41.725 ms |
| 系统切换调用返回到 PTY 输出新标签 | 20 | 3.822 ms | 4.599 ms | 5.680 ms |

这些是连续切换的本机样本，不是跨设备保证，也不包括快捷键识别、终端渲染到屏幕、显示器刷新等时间。20 个样本的尾部统计仍较粗略。最慢样本的系统切换调用本身耗时约 37.6 ms。

优化前后对比中，10 次普通命令行的主题展开次数从 **20 次降为 10 次**。这是可稳定复现的减少；事件到重绘本身原已低于 1 ms，未显示出有意义的进一步提速。之前单次 479 ms 的结果包含切换程序启动，不能代表日常热切换延迟。

运行不改变系统输入法的基准：

```sh
python3 tools/benchmark.py
```

显式测试真实切换（结束后自动恢复原输入源）：

```sh
python3 tools/benchmark.py --real-switch --switches 20
```

基准使用常驻切换驱动排除每次进程启动开销，并同时观察独立原生监听程序及 zsh PTY。默认模拟事件通过 FIFO 直接发送，不用定时轮询，避免把测试工具的轮询间隔算作插件延迟。
