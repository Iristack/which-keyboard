# macOS input-source indicator for interactive zsh. Source after your theme.
[[ -o interactive ]] || return 0
[[ -n ${_WK_LOADED:-} ]] && return 0

typeset -g _WK_ROOT=${${(%):-%x}:A:h}
if [[ ! -x ${WHICH_KEYBOARD_BINARY:-$_WK_ROOT/build/which-keyboard} ]]; then
  print -u2 -- "which-keyboard: run 'make' in $_WK_ROOT first."
  return 1
fi
zmodload zsh/system || return 1
autoload -Uz add-zsh-hook add-zle-hook-widget

typeset -g _WK_LOADED=1 _WK_PENDING='' _WK_BASE_RPROMPT=${RPROMPT-}
typeset -g _WK_RENDERED_RPROMPT=${RPROMPT-}
typeset -g _WK_BASE_RPROMPT2=${RPROMPT2-} _WK_RENDERED_RPROMPT2=${RPROMPT2-}
typeset -g _WK_BASE_PROMPT=${PROMPT-} _WK_RENDERED_PROMPT=${PROMPT-}
typeset -g _WK_BASE_PROMPT2=${PROMPT2-} _WK_RENDERED_PROMPT2=${PROMPT2-}
typeset -gi _WK_FD=-1 _WK_PID=0
typeset -g WHICH_KEYBOARD_INPUT_SOURCE_ID='' WHICH_KEYBOARD_INPUT_SOURCE_NAME=''
typeset -g WHICH_KEYBOARD_LABEL=''
(( ${+WHICH_KEYBOARD_LABELS} )) || typeset -gA WHICH_KEYBOARD_LABELS

_wk_render() {
  emulate -L zsh
  local before_prompt=${PROMPT-} before_prompt2=${PROMPT2-}
  local before_rprompt=${RPROMPT-} before_rprompt2=${RPROMPT2-}
  # A theme may have replaced a prompt since the previous update.
  [[ ${PROMPT-} == $_WK_RENDERED_PROMPT ]] || _WK_BASE_PROMPT=${PROMPT-}
  [[ ${PROMPT2-} == $_WK_RENDERED_PROMPT2 ]] || _WK_BASE_PROMPT2=${PROMPT2-}
  [[ ${RPROMPT-} == $_WK_RENDERED_RPROMPT ]] || _WK_BASE_RPROMPT=${RPROMPT-}
  [[ ${RPROMPT2-} == $_WK_RENDERED_RPROMPT2 ]] || _WK_BASE_RPROMPT2=${RPROMPT2-}
  # Restore all bases first so changing sides cannot leave a duplicate label.
  typeset -g PROMPT=$_WK_BASE_PROMPT PROMPT2=$_WK_BASE_PROMPT2
  typeset -g RPROMPT=$_WK_BASE_RPROMPT RPROMPT2=$_WK_BASE_RPROMPT2
  if [[ -n $WHICH_KEYBOARD_INPUT_SOURCE_ID ]]; then
    WHICH_KEYBOARD_LABEL=${WHICH_KEYBOARD_LABELS[$WHICH_KEYBOARD_INPUT_SOURCE_ID]:-$WHICH_KEYBOARD_INPUT_SOURCE_NAME}
    # Names and custom labels are data, never prompt syntax or shell code.
    local label=${WHICH_KEYBOARD_LABEL//\%/%%}
    label=${label//[[:cntrl:]]/ }
    if [[ -o promptsubst ]]; then
      label=${label//\\/\\\\}
      label=${label//\$/\\\$}
      label=${label//\`/\\\`}
    fi
    if [[ ${WHICH_KEYBOARD_POSITION:-right} == left ]]; then
      typeset -g PROMPT="%F{cyan}[${label}]%f ${_WK_BASE_PROMPT}"
      typeset -g PROMPT2="%F{cyan}[${label}]%f ${_WK_BASE_PROMPT2}"
    else
      typeset -g RPROMPT="${_WK_BASE_RPROMPT}${_WK_BASE_RPROMPT:+ }%F{cyan}[${label}]%f"
      typeset -g RPROMPT2="${_WK_BASE_RPROMPT2}${_WK_BASE_RPROMPT2:+ }%F{cyan}[${label}]%f"
    fi
  fi
  _WK_RENDERED_PROMPT=$PROMPT
  _WK_RENDERED_PROMPT2=$PROMPT2
  _WK_RENDERED_RPROMPT=$RPROMPT
  _WK_RENDERED_RPROMPT2=$RPROMPT2
  # Only ask ZLE to re-expand a theme when the visible prompt actually changes.
  [[ $before_prompt != $PROMPT || $before_prompt2 != $PROMPT2 ||
     $before_rprompt != $RPROMPT || $before_rprompt2 != $RPROMPT2 ]]
}

_wk_disconnect() {
  emulate -L zsh
  if (( _WK_FD >= 0 )); then
    zle -F $_WK_FD 2>/dev/null
    exec {_WK_FD}<&-
  fi
  _WK_FD=-1
  if (( _WK_PID > 0 )); then
    kill -TERM $_WK_PID 2>/dev/null
    wait $_WK_PID 2>/dev/null
  fi
  _WK_PID=0
  _WK_PENDING=''
}

_wk_receive() {
  emulate -L zsh
  local chunk line identifier name
  local -i result=0 changed=0 rounds=0
  # sysread is nonblocking and buffers partial records. A broken or slow helper
  # must never freeze editing. Bound each callback to avoid starving keyboard IO.
  while (( ++rounds <= 32 )); do
    sysread -i $_WK_FD -s 4096 -t 0 chunk
    result=$?
    if (( result == 4 )); then
      break
    elif (( result != 0 )); then
      _wk_disconnect
      WHICH_KEYBOARD_INPUT_SOURCE_ID=''
      WHICH_KEYBOARD_INPUT_SOURCE_NAME=''
      WHICH_KEYBOARD_LABEL=''
      changed=1
      break
    fi
    _WK_PENDING+=$chunk
    while [[ $_WK_PENDING == *$'\n'* ]]; do
      line=${_WK_PENDING%%$'\n'*}
      _WK_PENDING=${_WK_PENDING#*$'\n'}
      [[ $line == *$'\t'* ]] || continue
      identifier=${line%%$'\t'*}
      name=${line#*$'\t'}
      if [[ $identifier == '__which_keyboard_pid__' && $name == <-> ]]; then
        _WK_PID=$name
        continue
      fi
      [[ -n $identifier && -n $name ]] || continue
      # Reject control characters even when a custom helper is configured.
      [[ $identifier == *[[:cntrl:]]* || $name == *[[:cntrl:]]* ]] && continue
      if [[ $identifier != $WHICH_KEYBOARD_INPUT_SOURCE_ID || $name != $WHICH_KEYBOARD_INPUT_SOURCE_NAME ]]; then
        WHICH_KEYBOARD_INPUT_SOURCE_ID=$identifier
        WHICH_KEYBOARD_INPUT_SOURCE_NAME=$name
        changed=1
      fi
    done
    # Bound malformed unterminated records from a custom helper.
    (( ${#_WK_PENDING} > 16384 )) && _WK_PENDING=''
  done
  if (( changed )); then
    if _wk_render; then
      zle && zle reset-prompt
    fi
  fi
  return 0
}

_wk_start() {
  emulate -L zsh
  (( _WK_FD >= 0 )) && return 0
  # zsh does not reliably expose a process-substitution PID through $!.
  # Send the actual child PID before exec, then wait for the first source
  # record before sending any refresh signal.
  exec {_WK_FD}< <(
    print -r -- $'__which_keyboard_pid__\t'${sysparams[pid]}
    exec "${WHICH_KEYBOARD_BINARY:-$_WK_ROOT/build/which-keyboard}" --watch
  )
  zle -F $_WK_FD _wk_receive
}

_wk_precmd() {
  emulate -L zsh
  (( _WK_FD >= 0 )) && _wk_receive
  _wk_start
  _wk_render
  return 0
}

_wk_line_init() {
  emulate -L zsh
  # precmd prepares the cached label before ZLE's initial prompt expansion.
  # There is no unconditional reset here: expensive themes should expand once.
  # Do not signal until the helper's first record confirms it is ready.
  (( _WK_PID > 0 )) && [[ -n $WHICH_KEYBOARD_INPUT_SOURCE_ID ]] && kill -USR1 $_WK_PID 2>/dev/null
  return 0
}

which-keyboard-refresh() {
  emulate -L zsh
  if _wk_render; then
    zle && zle reset-prompt
  fi
  (( _WK_PID > 0 )) && kill -USR1 $_WK_PID 2>/dev/null
  return 0
}

which-keyboard-unload() {
  emulate -L zsh
  _wk_disconnect
  add-zle-hook-widget -d line-init _wk_line_init
  add-zsh-hook -d precmd _wk_precmd
  add-zsh-hook -d zshexit _wk_disconnect
  [[ ${PROMPT-} == $_WK_RENDERED_PROMPT ]] && typeset -g PROMPT=$_WK_BASE_PROMPT
  [[ ${PROMPT2-} == $_WK_RENDERED_PROMPT2 ]] && typeset -g PROMPT2=$_WK_BASE_PROMPT2
  [[ ${RPROMPT-} == $_WK_RENDERED_RPROMPT ]] && typeset -g RPROMPT=$_WK_BASE_RPROMPT
  [[ ${RPROMPT2-} == $_WK_RENDERED_RPROMPT2 ]] && typeset -g RPROMPT2=$_WK_BASE_RPROMPT2
  unset _WK_LOADED
  WHICH_KEYBOARD_INPUT_SOURCE_ID=''
  WHICH_KEYBOARD_INPUT_SOURCE_NAME=''
  WHICH_KEYBOARD_LABEL=''
  zle && zle reset-prompt
  return 0
}

add-zle-hook-widget line-init _wk_line_init
add-zsh-hook precmd _wk_precmd
add-zsh-hook zshexit _wk_disconnect
_wk_start
