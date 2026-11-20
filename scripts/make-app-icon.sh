#!/bin/sh
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
dir="$root/software-factory/lib/factory/appicon"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
set="$work/AppIcon.iconset"
mkdir "$set"

cat > "$work/render.swift" <<'SWIFT'
import AppKit

let args = CommandLine.arguments
guard let svg = NSImage(contentsOfFile: args[1]) else { exit(1) }
let size = 1024
guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { exit(1) }
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
svg.draw(in: NSRect(x: 0, y: 0, width: size, height: size))
NSGraphicsContext.restoreGraphicsState()
guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
try png.write(to: URL(fileURLWithPath: args[2]))
SWIFT

swift "$work/render.swift" "$dir/captn-icon.svg" "$work/master.png"

for size in 16 32 128 256 512; do
  double=$((size * 2))
  sips -z "$size" "$size" "$work/master.png" --out "$set/icon_${size}x${size}.png" >/dev/null
  sips -z "$double" "$double" "$work/master.png" --out "$set/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil -c icns "$set" -o "$dir/AppIcon.icns"
