# which-keyboard

<p align="center">
  <a href="./README.md"><img src="https://img.shields.io/badge/%E4%B8%AD%E6%96%87-README-red" alt="中文 README"></a>
  <img src="https://img.shields.io/badge/platform-macOS-blue?logo=apple" alt="Platform: macOS">
  <img src="https://img.shields.io/badge/zsh-5.8%2B-blue" alt="zsh 5.8+">
  <img src="https://img.shields.io/badge/native-Objective--C-F05138" alt="Native helper: Objective-C">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?logo=open-source-initiative" alt="License: MIT"></a>
  <a href="https://github.com/Iristack/which-keyboard/stargazers"><img src="https://img.shields.io/github/stars/Iristack/which-keyboard?style=social" alt="GitHub Stars"></a>
</p>

**Show the active macOS input source in your zsh prompt, in real time.**

Switch input sources and the label updates automatically—no need to press Enter or type another character. Choose either side of the prompt, customize labels, and keep using multiline commands.

```text
# Left
[EN]     ~/project ❯ git status
[Pinyin] ~/project ❯ git status

# Right (default)
~/project ❯ git status                            [Pinyin]
```

[Quick Start](#quick-start) · [Configuration](#configuration) · [Limitations](#limitations) · [Development and Testing](#development-and-testing) · [Contributing](#contributing)

## Features

- **Live updates**: listens for system input-source changes without periodic polling.
- **Flexible placement**: display labels on the left or right, with custom names mapped to input-source IDs.
- **Preserves editing state**: asynchronous updates keep your command and cursor position intact, including multiline input.
- **Avoids redundant work**: caches labels and skips prompt redraws when the displayed content has not changed.
- **Minimal dependencies**: uses native macOS APIs; no `im-select`, Accessibility access, or Input Monitoring permission required.

The plugin only reads input-source state. It does not record keystrokes or switch input sources automatically.

## Quick Start

### Requirements

| Dependency | Requirement |
| --- | --- |
| System | A local macOS desktop session |
| Shell | zsh 5.8+; tested on Apple Silicon with zsh 5.9 |
| Build tools | Xcode Command Line Tools, or Xcode with the macOS SDK |

### Install with Homebrew (Recommended)

```sh
brew tap iristack/which-keyboard https://github.com/Iristack/which-keyboard.git
brew install iristack/which-keyboard/which-keyboard
```

Add this to `~/.zshrc`, **after your theme initialization**:

```zsh
WHICH_KEYBOARD_POSITION=left  # Optional; defaults to the right
source "$(brew --prefix)/share/which-keyboard/which-keyboard.plugin.zsh"
```

Open a new terminal to start using the plugin. Homebrew downloads a versioned source archive, verifies its SHA-256, and builds it locally, so the build tools listed above are still required. Prebuilt bottles are not currently provided. The installation also makes the `which-keyboard` command available.

### Install from Source

```sh
git clone https://github.com/Iristack/which-keyboard.git "$HOME/.local/share/which-keyboard"
make -C "$HOME/.local/share/which-keyboard"
```

Add the following to `~/.zshrc`, **after your theme initialization**:

```zsh
source "$HOME/.local/share/which-keyboard/which-keyboard.plugin.zsh"
```

Open a new terminal window and switch between input sources, such as ABC and Apple's Pinyin input method, to see the label update. To try it in your current zsh session, run the same `source` command directly.

> You can choose a different installation directory; adjust the source path accordingly. The project does not modify your shell configuration or download dependencies automatically.

## Configuration

Place configuration settings before the plugin's `source` line.

### Position

Labels appear on the right by default. Set `left` to prepend the label to your existing prompt:

```zsh
WHICH_KEYBOARD_POSITION=left
```

You can also change the position in an active session:

```zsh
WHICH_KEYBOARD_POSITION=right  # left or right
which-keyboard-refresh
```

The setting applies to both the primary prompt and the continuation prompt for multiline commands. Existing prompt content is preserved.

### Custom Labels

By default, labels use the input-source names provided by macOS. Map input-source IDs to shorter names:

```zsh
typeset -A WHICH_KEYBOARD_LABELS=(
  com.apple.keylayout.ABC EN
  com.apple.inputmethod.SCIM.ITABC Pinyin
)
WHICH_KEYBOARD_POSITION=left
```

List enabled input sources and their IDs (for source installations, use `./build/which-keyboard --list`):

```sh
which-keyboard --list
```

Labels are treated as plain text, not color codes or other prompt syntax. After changing a mapping in an active session, run `which-keyboard-refresh` to apply it.

### Commands

| Command | Purpose |
| --- | --- |
| `which-keyboard-refresh` | Apply configuration and request the latest input-source state |
| `which-keyboard-unload` | Stop the listener, remove plugin hooks, and restore the original prompts |

Sourcing the plugin repeatedly does not start duplicate listeners. You can source it again after unloading.

<details>
<summary>Advanced configuration and native interface</summary>

Set `WHICH_KEYBOARD_BINARY` before loading the plugin to use the absolute path of a compatible listener executable.

Other shell configuration can read these state variables:

| Variable | Contents |
| --- | --- |
| `WHICH_KEYBOARD_INPUT_SOURCE_ID` | System input-source ID |
| `WHICH_KEYBOARD_INPUT_SOURCE_NAME` | Display name supplied by macOS |
| `WHICH_KEYBOARD_LABEL` | Label after applying custom mappings |

Run the native helper from the repository directory:

```sh
./build/which-keyboard --once   # Query the current input source
./build/which-keyboard --list   # List enabled, selectable input sources
./build/which-keyboard --watch  # Emit initial state and changes; Ctrl-C to exit
```

Output is UTF-8, with one `ID<TAB>name<newline>` record per line. In watch mode, `SIGUSR1` requests a fresh snapshot.

</details>

## Updating and Uninstalling

**Homebrew installations**:

```sh
brew update
brew upgrade which-keyboard
```

After upgrading, open a new terminal, or run `which-keyboard-unload` followed by the Homebrew `source` line again. To uninstall, run `brew uninstall which-keyboard`, then remove the corresponding source line and settings from `.zshrc`.

**Source installations**: update the source and rebuild:

```sh
git -C "$HOME/.local/share/which-keyboard" pull --ff-only
make -C "$HOME/.local/share/which-keyboard"
```

Reload the plugin in an existing session:

```zsh
which-keyboard-unload
source "$HOME/.local/share/which-keyboard/which-keyboard.plugin.zsh"
```

To uninstall, run `which-keyboard-unload` and remove the source line and related settings from `~/.zshrc`. You can then delete the installation directory.

## Limitations

| Scenario | Current support |
| --- | --- |
| System input-source changes, such as ABC ↔ Apple Pinyin | Live updates supported |
| Shift toggles within Sogou or Squirrel/Rime | Internal Chinese/English modes cannot be distinguished if the system input source stays the same |
| Multiline commands | Supported; the continuation prompt uses the same position setting |
| Vim, less, or another foreground command | No live label while the command runs; updates resume in the zsh line editor |
| Complex themes such as Powerlevel10k and Starship | No dedicated integration yet; compatibility requires testing |
| Remote SSH sessions and multiple tmux clients | No forwarding of local input-source state to remote shells or per-client state mapping |

zsh may hide a right-hand label when the command becomes too long. Use left placement if your configuration disables right prompts, for example with `SINGLE_LINE_ZLE`.

Input-source state belongs to the current macOS desktop. Background terminal sessions may receive changes caused by other applications; the plugin resynchronizes when you return to the terminal.

## How It Works

Each shell starts a small native listener. The listener queries the current input source when macOS sends a change notification, then writes the state to a pipe. zsh receives events asynchronously through `zle -F` and calls `zle reset-prompt` only when the prompt content changes.

Cached labels are prepared during `precmd` to avoid expanding the theme twice for each new command line. The listener is cleaned up on exit. If it terminates unexpectedly, the label is removed and the plugin attempts to restart it at the next command line.

## Performance

Consecutive-switch samples on Apple Silicon, zsh 5.9, and a simple prompt (September 14, 2026):

| Measurement | Samples | Median | P95 | Maximum |
| --- | --- | --- | --- | --- |
| Synthetic event write → updated label in PTY output | 100 | 0.162 ms | 0.207 ms | 0.299 ms |
| System switch API call → updated label in PTY output | 20 | 5.111 ms | 6.946 ms | 41.725 ms |

These measurements exclude shortcut recognition, terminal rendering, and display refresh. They are short runs on one machine, not guarantees across devices. Results depend on your system, terminal, and theme.

## Development and Testing

Development tests also require Python 3. They use the standard library, with no additional Python dependencies. From the repository directory, run:

```sh
make        # Build the native listener
make test   # Syntax checks, native interface tests, and PTY integration tests
```

The default test suite does not switch the system input source. It covers asynchronous redraws, command and cursor preservation, multiline input, prompt compatibility, label escaping, and process lifecycle.

Run the benchmark without changing system input sources:

```sh
python3 tools/benchmark.py
```

The following commands briefly switch real input sources and attempt to restore the original state on completion. At least two input sources must be enabled:

```sh
WK_TEST_REAL_SWITCH=1 python3 -m unittest discover -s tests -v
python3 tools/benchmark.py --real-switch --switches 20
```

## Contributing

Bug reports and suggestions are welcome in [Issues](https://github.com/Iristack/which-keyboard/issues), as are pull requests.

When reporting a problem, include your macOS and zsh versions, terminal and theme names, input method, and minimal reproduction steps. For display issues, screenshots with personal information removed are helpful.

Run `make test` before submitting code. For changes to prompt rendering, also check multiline input, cursor position, and preservation of existing theme content.

## License

This project is licensed under the [MIT License](./LICENSE).
