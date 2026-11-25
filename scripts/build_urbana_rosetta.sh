#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(dirname -- "$script_dir")
compat_dir="${VIVADO_COMPAT_DIR:-$HOME/vivado-compat}"

if ! command -v bwrap >/dev/null 2>&1; then
    printf 'Missing bwrap. Install bubblewrap in the Debian VM.\n' >&2
    exit 1
fi
for shim in uname arch lscpu; do
    if [[ ! -x "$compat_dir/$shim" ]]; then
        printf 'Missing executable compatibility shim: %s\n' "$compat_dir/$shim" >&2
        exit 1
    fi
done

export PATH="$compat_dir:$PATH"
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:+$JAVA_TOOL_OPTIONS }-Djdk.lang.Process.launchMechanism=FORK"
vivado_command="${VIVADO_BIN:-vivado}"
if ! command -v "$vivado_command" >/dev/null 2>&1; then
    printf 'Vivado launcher not found: %s\n' "$vivado_command" >&2
    printf 'Set VIVADO_BIN to the working launcher path if it is not on PATH.\n' >&2
    exit 1
fi

output_dir="$repo_root/build/urbana"
mkdir -p "$output_dir"
exec bwrap \
    --dev-bind / / \
    --ro-bind "$compat_dir/lscpu" /usr/bin/lscpu \
    --chdir "$repo_root" \
    --setenv PATH "$PATH" \
    --setenv JAVA_TOOL_OPTIONS "$JAVA_TOOL_OPTIONS" \
    --setenv LC_ALL C \
    --setenv LANG C \
    "$vivado_command" \
    -mode batch \
    -source "$repo_root/scripts/build_urbana.tcl" \
    -log "$output_dir/vivado_rosetta.log" \
    -journal "$output_dir/vivado_rosetta.jou"
