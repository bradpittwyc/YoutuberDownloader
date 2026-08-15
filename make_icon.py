#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 YouTube 红色【下载】风格的程序图标 icon.ico（用 Pillow）。"""

from PIL import Image, ImageDraw


def make_icon():
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 红色圆角矩形背景（YouTube 红）
    d.rounded_rectangle([0, 0, size, size], radius=56, fill=(255, 0, 0, 255))

    # 白色「下载」标识：向下箭头 + 底部托盘
    # 1) 箭头杆（竖线）
    d.rectangle([118, 62, 138, 148], fill=(255, 255, 255, 255))
    # 2) 箭头头部（三角，指向下）
    d.polygon([(84, 118), (172, 118), (128, 170)], fill=(255, 255, 255, 255))
    # 3) 底部托盘（横条）
    d.rounded_rectangle([52, 184, 204, 212], radius=14, fill=(255, 255, 255, 255))

    # 保存为多尺寸 ICO（Windows 图标格式）
    img.save("icon.ico", format="ICO",
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon.ico 下载标识生成完成")


if __name__ == "__main__":
    make_icon()
