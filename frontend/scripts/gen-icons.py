#!/usr/bin/env python3
"""生成 AceExam TabBar PNG 图标（81x81，8x 超采样抗锯齿，纯 stdlib）。

用法: python scripts/gen-icons.py
输出: src/static/tabbar/{subjects,practice,mine}[-active].png
"""
import math
import os
import struct
import zlib

SIZE = 81
SS = 8  # 超采样倍数
GRAY = (0x9C, 0xA3, 0xAF)  # 未选中（辅助灰）
AMBER = (0xF5, 0x9E, 0x0B)  # 选中（$primary-500）


def rounded_rect_sdf(x, y, cx, cy, hx, hy, r):
    """圆角矩形带符号距离（<=0 为内部）"""
    dx = abs(x - cx) - (hx - r)
    dy = abs(y - cy) - (hy - r)
    ax, ay = max(dx, 0.0), max(dy, 0.0)
    return math.hypot(ax, ay) + min(max(dx, dy), 0.0) - r


def circle_sdf(x, y, cx, cy, r):
    return math.hypot(x - cx, y - cy) - r


def dist_to_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def shape_coverage(x, y, kind):
    """返回 0~1 覆盖率"""
    if kind == "subjects":
        # 2x2 圆角方块（选科：科目矩阵）
        cells = [(-16, -16), (16, -16), (-16, 16), (16, 16)]
        for cx, cy in cells:
            if rounded_rect_sdf(x, y, cx, cy, 11, 11, 5) <= 0:
                return 1.0
        return 0.0
    if kind == "practice":
        # 圆圈 + 对勾（刷题：答对）
        d = circle_sdf(x, y, 0, 0, 26)
        ring = 1.0 if -6 <= d <= 0 else 0.0
        # 对勾折线：两段线段
        d1 = dist_to_segment(x, y, -9, 3, -2, 11)
        d2 = dist_to_segment(x, y, -2, 11, 12, -8)
        check = 1.0 if min(d1, d2) <= 5.5 else 0.0
        return max(ring, check)
    if kind == "mine":
        # 人像：头 + 肩
        head = 1.0 if circle_sdf(x, y, 0, -13, 9) <= 0 else 0.0
        # 椭圆肩部，裁掉头顶以上
        body = (x / 24.0) ** 2 + ((y - 18) / 22.0) ** 2
        shoulder = 1.0 if (body <= 1.0 and y >= -4) else 0.0
        return max(head, shoulder)
    return 0.0


def write_png(path, pixels):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(
        b"\x00" + b"".join(struct.pack("4B", *px) for px in row) for row in pixels
    )
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


def render(kind, rgb):
    """渲染一张图标：8x 超采样求覆盖率，输出 RGBA"""
    pixels = []
    for py in range(SIZE):
        row = []
        for px in range(SIZE):
            covered = 0
            for sy in range(SS):
                for sx in range(SS):
                    x = px + (sx + 0.5) / SS - SIZE / 2
                    y = py + (sy + 0.5) / SS - SIZE / 2
                    covered += shape_coverage(x, y, kind)
            alpha = int(round(255 * covered / (SS * SS)))
            row.append((rgb[0], rgb[1], rgb[2], alpha))
        pixels.append(row)
    return pixels


def main():
    out_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "src",
        "static",
        "tabbar",
    )
    os.makedirs(out_dir, exist_ok=True)
    for kind in ("subjects", "practice", "mine"):
        write_png(os.path.join(out_dir, f"{kind}.png"), render(kind, GRAY))
        write_png(os.path.join(out_dir, f"{kind}-active.png"), render(kind, AMBER))
        print(f"[ok] {kind}.png / {kind}-active.png")


if __name__ == "__main__":
    main()
