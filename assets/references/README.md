# 建筑参考图

- `style/`：等距视角、构图和目标美术风格参考；
- `architecture/`：实景、立面、屋顶、材料和时代参考；
- `sketches/`：手绘草图、平面草图和体块关系参考。

每个引用都应记录 URI、作者、许可证、检索日期和用途。参考图默认不进入最终 NewGRF。

## AI 重绘网格

`openttd-isometric-grid-2x2-h8-zi4.png` 是当前 2×2 建筑工单使用的重绘底图：

- 画布为 `1024×1536`，与 `isometric-2x2-h8` 的 zi4 模板一致；
- tile 边方向为 `(128, 64)` 和 `(-128, 64)`，即 OpenTTD 的 2:1 等距投影；
- 每条 tile 边细分为 8 段，细网格比 tile 边界更密；
- 主边界、四分之一边界和细网格使用不同线色；
- 所有线条直接按整数像素绘制，关闭抗锯齿；
- 几何参数记录在同名 `.json` 文件中。

重新生成：

```sh
.venv/bin/python -m tools.isometric_grid
```

## AI 工作网格与 TTD 验收网格

生图模型通常更熟悉 30° 轴、120° 地面夹角。因此另有
`ai-isometric-grid-120-2x2-h8-zi4.png`，专门用于 AI 重绘；它不是最终
NewGRF 的几何标准。

- AI 工作网格：120°，用于生成体块、立面、屋顶、光影和纹理；
- TTD 验收网格：126.87°，用于最后的几何检查和切片；
- 两者之间不采用单一全局变换作为最终修正；后续工作台应支持对屋顶、左墙、右墙等主要平面分别进行四边形映射。

生成 AI 工作网格：

```sh
.venv/bin/python -m tools.isometric_grid \
  --projection ai120 \
  --output assets/references/ai-isometric-grid-120-2x2-h8-zi4.png
```
