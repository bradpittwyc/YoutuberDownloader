#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 macOS 用的 .icns 图标（红色 + 白色下载箭头，与 Windows 版同款设计）。
从 1024px 设计图缩放出各尺寸 PNG，按 icns 文件格式打包。"""

import io
import struct

from PIL import Image, ImageDraw

# icns 块类型 -> PNG 像素尺寸
ICNS_TYPES = [
    ("ic11", 32),
    ("ic12", 64),
    ("ic07", 128),
    ("ic08", 256),
    ("ic09", 512),
    ("ic10", 1024),
]


def draw_icon(size):
    """按给定尺寸绘制：红底圆角矩形 + 白色向下箭头 + 托盘（比例与 Windows 版一致）。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size, size], radius=int(size * 0.22),
                        fill=(255, 0, 0, 255))
    # 箭头杆
    d.rectangle([int(size * 0.461), int(size * 0.242),
                 int(size * 0.539), int(size * 0.578)],
                fill=(255, 255, 255, 255))
    # 箭头三角
    d.polygon([(int(size * 0.328), int(size * 0.461)),
               (int(size * 0.672), int(size * 0.461)),
               (int(size * 0.500), int(size * 0.664))],
              fill=(255, 255, 255, 255))
    # 底部托盘
    d.rounded_rectangle([int(size * 0.203), int(size * 0.719),
                         int(size * 0.797), int(size * 0.828)],
                        radius=int(size * 0.055),
                        fill=(255, 255, 255, 255))
    return img


def make_icns():
    master = draw_icon(1024)
    chunks = b""
    for typ, size in ICNS_TYPES:
        buf = io.BytesIO()
        master.resize((size, size), Image.LANCZOS).save(buf, format="PNG")
        png = buf.getvalue()
        chunks += typ.encode() + struct.pack(">I", 8 + len(png)) + png

    header = b"icns" + struct.pack(">I", 8 + len(chunks))
    with open("icon.icns", "wb") as f:
        f.write(header + chunks)
    print(f"icon.icns 生成完成（{len(header + chunks)} 字节，{len(ICNS_TYPES)} 种尺寸）")


if __name__ == "__main__":
    make_icns()
