class WhichKeyboard < Formula
  desc "Real-time macOS input source indicator for zsh"
  homepage "https://github.com/Iristack/which-keyboard"
  url "https://github.com/Iristack/which-keyboard/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "27133b181ec93f5fe6ed82f130e9833e3af4051d58ffc76c29563466ae9541c2"
  license "MIT"
  head "https://github.com/Iristack/which-keyboard.git", branch: "main"

  depends_on :macos

  def install
    system "make", "CC=#{ENV.cc}"
    libexec.install "which-keyboard.plugin.zsh"
    (libexec/"build").install "build/which-keyboard"
    bin.install_symlink libexec/"build/which-keyboard"
    pkgshare.install_symlink libexec/"which-keyboard.plugin.zsh"
  end

  def caveats
    <<~EOS
      Add this after your theme initialization in ~/.zshrc:
        source "#{HOMEBREW_PREFIX}/share/which-keyboard/which-keyboard.plugin.zsh"

      To display the label on the left, set this before the source line:
        WHICH_KEYBOARD_POSITION=left

      Open a new terminal after installation or upgrade.
    EOS
  end

  test do
    assert_predicate libexec/"build/which-keyboard", :executable?
    assert_equal (libexec/"which-keyboard.plugin.zsh").realpath,
                 (pkgshare/"which-keyboard.plugin.zsh").realpath
    system "/bin/zsh", "-n", pkgshare/"which-keyboard.plugin.zsh"
    assert_match "Usage: which-keyboard", shell_output("#{bin}/which-keyboard --invalid 2>&1", 64)
  end
end
