# image-pre-process

一个基于 Tkinter + Pillow 的本地图片批量裁剪工具。

## 功能

- 加载一张参考图片
- 鼠标拖拽框选裁剪区域
- 自动记录原图裁剪坐标
- 对 `input` 目录下所有图片应用相同裁剪区域
- 将结果输出到 `output` 目录
- 预览 `output/` 目录下的图片，分页显示（每页 10 张）

## 目录结构

```text
image-pre-process/
├── main.py
├── requirements.txt
├── input/
└── output/
```

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 使用步骤

1. 将待处理图片放到 `input/` 目录
2. 运行程序
3. 点击“加载参考图片”，选择一张图片作为参考
4. 在界面中拖拽框选要裁剪的区域
5. 点击“批量裁剪 input”
6. 在 `output/` 目录查看结果
7. 点击“预览 output”可分页预览输出图片（每页 10 张，支持翻页）

## 说明

- 支持格式：png、jpg、jpeg、bmp、gif、tif、tiff、webp
- 如果某张图片尺寸比参考图小，程序会自动按当前图片边界裁剪
- 如果裁剪区域在某张图片上无有效交集，该图片会被记录为失败
- 预览窗口分页 10 张，网格 5x2，可翻页查看
