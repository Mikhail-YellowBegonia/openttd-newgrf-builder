# 建筑素材流程验证记录

本文记录 `test1-2x2` 从 AI 成图到 OpenTTD 游戏内验证的完整过程，作为后续批量化工单和工作台开发的基线。

## 1. 流程结论

本次验证确认了以下最小生产链路可以工作：

1. 准备带透明背景的 AI 建筑图；
2. 使用 TTD 方向网格标定地基原点和两条地面轴；
3. 以较长地基边作为正方形地基尺寸；
4. 统一缩放到 2×2 zi4 模板并应用模板 alpha mask；
5. 从 zi4 最近邻派生 zi2 和 normal；
6. 用 NML 生成 2×2 House：north tile 挂完整画布，其余 tile 使用透明精灵；
7. 编译 GRF 并在 JGRPP 中检查地基、遮挡和完整性；
8. 根据游戏截图修正 sprite 挂接偏移，再次编译验证。

## 2. 标定结果

最终使用网页标定页导出的 `test1-round2-calibration.json`：

```text
source image:    assets/generated/test1-round2.png (1024×853)
footprint:       2x2
source origin:   (515, 761)
source X axis:   (-511, -255)
source Y axis:   (508, -254)
ground size:     570.998 source pixels
projection:      uniform
screen angles:   153.435° / 26.565°
included angle:  126.870°
```

X/Y 点击点会在网页中投影到固定 TTD 轴线上。导出的 JSON 同时记录原始鼠标落点和投影后的标定点，避免测量工具格式差异影响工单。

## 3. 关键问题与处理

### 2×2 完整图被裁切

早期 sprite layout 使用固定的 `16×16×16` extent，高层建筑在游戏中被裁掉。现在 extent 根据占地和模板高度生成：

```text
xextent = 32
yextent = 32
zextent = 64
```

完整 2×2 画布保留 `1024×1536`，切片工具只用于检查各 tile 的透明包络，不把局部切片直接当作正式建筑图。

### 游戏内图像整体偏上

初版 north tile 挂接时，图像相对实际 2×2 地块偏上约一个地面 tile 的屏幕高度。最终 NML 偏移为：

```text
normal: -288
zi2:    -576
zi4:    -1152
```

这只改变 sprite 挂接位置，不改变源图、标定参数或切片内容。修正后的 GRF 已由用户在游戏内测试通过。

## 4. 可复现命令

```sh
# 网页标定工具
python3 -m http.server 4173 --directory web
# 浏览器打开 http://127.0.0.1:4173/calibration/

# 生成校准预览、zi4 和 2×2 检查切片
.venv/bin/python -m tools.work_order preview \
  assets/work_orders/test1-2x2.json \
  --output assets/work/test1-2x2-round4-calibration.png
.venv/bin/python -m tools.work_order process \
  assets/work_orders/test1-2x2.json \
  --output assets/work/test1-2x2-zi4.png
.venv/bin/python -m tools.work_order slice \
  assets/work_orders/test1-2x2.json \
  assets/work/test1-2x2-zi4.png \
  --output-dir assets/work/test1-2x2-round4-slices

# 校验、生成 NML、编译 GRF
make package
```

最终 GRF 的 SHA-256：

```text
86150dce736381047b56ae398ab038cbac10f63b151a1e7eb4370d0fc0271607
```

## 5. 归档内容

- `web/calibration/`：交互式 TTD 标定页；
- `assets/work_orders/test1-2x2.json`：机器可读工单；
- `assets/work/test1-2x2-round4-calibration.png`：标定预览；
- `assets/work/test1-2x2-round4-slices/`：2×2 检查切片；
- `assets/work/test1-2x2-zi4.png`：正式 zi4 母版；
- `building/building.nml`：由 manifest 生成的人类可读 NML；
- `building.grf`：通过游戏内测试的 NewGRF；
- `assets/work_orders/archive/` 和 `assets/work/archive/`：旧轮次和旧参数。

## 6. 下一阶段

下一步是批量化，而不是继续扩大单个样例的特殊逻辑。优先顺序建议为：

1. 网页工单表单与 JSON schema 校验；
2. 可视化标定结果和模板 mask 预览；
3. 背景 mask、调色、缩放和切片的可重复处理；
4. 多建筑 manifest 注册、失败项报告和批量 NML/GRF 构建；
5. 补充 1×1、低矮建筑、透明边缘和不同背景等边缘用例。
