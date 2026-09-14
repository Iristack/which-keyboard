CC = clang
CFLAGS = -O2 -Wall -Wextra -Werror -fobjc-arc

.PHONY: all clean test
all: build/which-keyboard

build/which-keyboard: native/main.m
	mkdir -p build
	$(CC) $(CFLAGS) $< -o $@ -framework Carbon -framework Cocoa

test: all
	zsh -n which-keyboard.plugin.zsh
	python3 -m unittest discover -s tests -v

clean:
	rm -rf build
