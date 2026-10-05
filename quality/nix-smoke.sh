#!/usr/bin/env bash
set -euo pipefail

package=$(realpath -e "${1:?font output required}")
font_dir="$package/share/fonts/truetype"
font="$font_dir/Goku.ttc"
docs="$package/share/doc/goku"
test -s "$font"
test -s "$docs/THIRD_PARTY_NOTICES.md"
test -s "$docs/GohuFont-WTFPL.txt"
test ! -d "$package/bin"
(cd "$font_dir" && sha256sum --check "$docs/Goku.ttc.sha256")

scratch=$(mktemp -d "${TMPDIR:-/tmp}/goku-font-check.XXXXXXXX")
trap 'rm -rf "$scratch"' EXIT
for weight in {100..900..100}; do
  printf 'Goku-%s\nGoku-%sItalic\n' "$weight" "$weight"
done > "$scratch/expected"
fc-scan --format '%{postscriptname}\n' "$font" > "$scratch/actual"
diff -u "$scratch/expected" "$scratch/actual"
cat > "$scratch/fonts.conf" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>$font_dir</dir>
  <cachedir>$scratch/cache</cachedir>
</fontconfig>
EOF
export FONTCONFIG_FILE="$scratch/fonts.conf"
while IFS= read -r face; do
  test "$(fc-match --format '%{postscriptname}' ":postscriptname=$face")" = "$face"
  test "$(fc-match --format '%{file}' ":postscriptname=$face")" = "$font"
done < "$scratch/expected"
printf 'Goku: all 18 installed faces and isolated font discovery passed\n'
