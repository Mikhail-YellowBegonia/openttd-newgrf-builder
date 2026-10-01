# 建筑素材工单

建筑不再以“交一张看起来不错的图片”为交付单位，而以一张可追踪、可复现、可自动打包的工单为交付单位。

## 第一版的交付边界

每个工单对应一个建筑和一个 `zi4` 母版，至少交付：

1. AI 原始候选图：保留模型、版本、提示词版本、seed 和来源参考；
2. 校准参数：源图中的地面原点、X/Y 轴方向和方形地基边长；
3. 背景处理结果：自动抠图或人工 alpha mask；
4. `zi4` RGBA 成品：不含网格、标尺、文字、水印和背景；
5. 元数据和审核状态：建筑 ID、House ID、年代、密度、占地、版权和 QA。

`normal` 和 `zi2` 不作为人工交付物，由构建阶段从 `zi4` 最近邻派生。第一版只处理最基本的单建筑图形，不实现 VarAction2、邻接变体或随机逻辑。

## 工单示例

```json
{
  "schema": 1,
  "work_order_id": "cn_highrise_001",
  "building_id": "cn_urban_2000_001",
  "house_id": "128",
  "footprint": "1x1",
  "source": {"image": "assets/generated/cn_highrise_001.png"},
  "calibration": {
    "source_origin": [480, 820],
    "source_x_axis": [96, 48],
    "source_y_axis": [-96, 48],
    "ground_tile_size": 96,
    "ground_tile_policy": "square_max",
    "projection_mode": "orthographic_affine",
    "source_projection_angle_deg": 30.0,
    "target_template": "templates/isometric-1x1-h8/spec.json"
  },
  "processing": {
    "saturation": 1.05,
    "background": {"method": "flood_fill", "tolerance": 24}
  }
}
```

校准参数的单位是源图像素。`source_origin` 是地面 tile 的下角原点；`source_x_axis` 和 `source_y_axis` 是从该原点指向两个上角的地基向量。`ground_tile_size` 采用较长边，并按正方形地基进行统一缩放；较短方向留下的空白最终保持透明。这里不再要求独立的 tile 高度向量，因为建筑高度随同一全局比例缩放，不能使用非均匀拉伸。若自动抠图不可靠，可以把 `background.method` 改为 `mask_file`，提交一张同尺寸的灰度 alpha mask。

注意：三维等距坐标中的三轴夹角是 `120°`，但当前 OpenTTD PNG 模板采用 `64×32` 的屏幕 tile，地面两条上行边的屏幕夹角约为 `126.87°`。输入图测得的 `121°` 表示 AI 图存在轻微投影误差。处理器现在用统一旋转和缩放同时最小化两条地基边的误差，不使用剪切来强行拉正。

如果确认源图是正交的约 30° 投影，应将 `projection_mode` 设为 `orthographic_affine`。这会把源图的正交地面基向量转换到 OpenTTD 的 2:1 屏幕基向量；它不是透视变形，平行墙线仍然平行，垂直墙线仍然保持屏幕垂直。普通 `uniform` 模式适合已经接近 OpenTTD 2:1 投影的输入。

可以额外填写 `source_projection_angle_deg`（本例建议 `29.75` 或 `30.0`）。工具会以屏幕垂直线为对称轴重建源图的两条地面方向，吸收手工测量的半度误差，避免把墙面一起带斜。

## 本地工具

### 本地 Web 工作台

当前已提供一个把人工环节和确定性处理串起来的本地工作台：

```sh
python3 web/workbench/server.py
# 浏览器打开 http://127.0.0.1:4173/workbench/
```

工作台覆盖建筑/NML 参数、参考图记录、AI 生成元数据、生成结果审核、多边形
alpha mask、原点与 XY 轴标定、zi4 配准、2×2 切片、审核复制、manifest 登记和
完整 GRF 构建。AI 服务调用仍由外部工具完成，工作台负责接收生成结果并保存
provider、模型、提示词版本和 seed；不保存 API Key。

工作台后端复用本文件下面的 `preview`、`process`、`slice` 和 `register` 逻辑，
因此浏览器操作和命令行工单使用同一份 JSON 数据格式。

工单现在还记录 `sprite_mode`：`single` 表示一张 zi4 在运行时复用到八个方向；
`four_direction` 用于标记需要四方向独立素材的建筑。后者目前只进入工单规划，
工作台会在配准/登记前明确拦截，直到 NML 方向贴图编译器接入。

```sh
# 建立工单骨架
.venv/bin/python -m tools.work_order init \
  --output assets/work_orders/cn_highrise_001.json \
  --work-order-id cn_highrise_001 \
  --building-id cn_urban_2000_001 \
  --house-id 128 \
  --source-image assets/generated/cn_highrise_001.png \
  --template templates/isometric-1x1-h8/spec.json

# 在原图上显示人工标定的 tile 网格
.venv/bin/python -m tools.work_order preview \
  assets/work_orders/cn_highrise_001.json \
  --output assets/work/cn_highrise_001-calibration.png

# 执行调色、抠图、透视/比例拟合、模板 mask 和 zi4 输出
.venv/bin/python -m tools.work_order process \
  assets/work_orders/cn_highrise_001.json \
  --output assets/approved/cn_highrise_001-zi4.png

# 2x2 工单的美术切片测试；输出仍保留完整模板画布，避免跨 tile 的建筑像素被裁掉
.venv/bin/python -m tools.work_order slice \
  assets/work_orders/cn_block_2x2.json \
  assets/work/cn_block_2x2-zi4.png \
  --output-dir assets/work/cn_block_2x2-slices

# 人工审核后把工单中的 rights_status 与 qa_status 都改为 approved，再登记到清单
.venv/bin/python -m tools.work_order register \
  assets/work_orders/cn_highrise_001.json \
  --approved assets/approved/cn_highrise_001-zi4.png

make package
```

## 人工试做建议

第一轮可以用 Photoshop、Photopea 或 Krita 完成标定：

1. 打开 AI 成图和 `preview` 网格；
2. 在建筑地面上选一个稳定原点，测量一个 X tile 和一个 Y tile 的屏幕位移；
3. 取两条地基边中较长者作为 `ground_tile_size`；
4. 把原点、两个向量和地基边长写入工单 JSON；
5. 检查预览网格是否贴合地面；
6. 再运行 `process`，只人工修正自动抠图失败的部分。

这样人工试做的结果会直接留下机器可读的参数，后续可以把相同步骤搬进专用界面，而不需要重新设计数据格式。

## 验收条件

- 输出是与模板完全相同尺寸的 RGBA PNG；
- 模板 mask 外 alpha 必须为零；
- 成品不包含背景网格、标尺、文字、水印或悬浮阴影；
- 地面接触点与模板 anchor 对齐；
- `rights_status=approved` 且 `qa_status=approved` 后，才允许写入正式 manifest 并参与 GRF 构建。

当前提供的示例图在自动 flood fill 后仍会残留地面网格，因此不能直接标记为 approved；应先用图像编辑器制作同尺寸 alpha mask，再以 `mask_file` 方式处理。`register` 只执行工单审核门禁和 manifest 登记；最终 PNG 仍会由 `make validate` 的模板校验检查。

`process` 现在可以处理与模板匹配的 `2x2` 完整图；`slice` 会按四个 tile 的地面包络生成四张带透明区域的测试图，并写入 `slices.json`。正式 NML 编译将完整画布绑定到 north tile，其余三个 tile 使用透明精灵，并自动生成连续 House ID、House flags 和 Action 3 绑定。示例建筑有突出的大体量裙房和连桥，切片结果仍需要人工检查遮挡和切缝。

完整画布的素材锚点是整个地基的南角，而 House 精灵实际挂接在 north tile。NML 生成器从模板 `tile_polygons["0,0"]` 取得挂接 tile 的北角，按两点的 X/Y 差换算 sprite offset；因此 1×1、2×2 及未来的非正方形占地使用同一条几何规则。1×1 的 normal/zi2/zi4 offset 分别为 `(-96,-288)`、`(-192,-576)`、`(-384,-1152)`；现有 2×2 offset 保持 `(-128,-288)`、`(-256,-576)`、`(-512,-1152)`。object 等其他特性可复用点到点换算，但须先明确其运行时挂接点。

`slice` 生成的四张图是按地基垂直包络分配的局部图，每张单独查看时只会显示建筑的一部分；四张图叠加后才还原完整 zi4。当前生产 NML 仍将完整画布绑定到 north tile，附属 tile 使用透明精灵，因此不能把某一张 `tile-*.png` 当作完整建筑贴图。

1x1 不需要准备八张方向图。NML 编译器会把一张 approved `zi4` PNG 用作基础布局，并由构建器派生 normal/zi2。2x2 可以登记一张完整画布；构建器负责 north tile 顺序、连续 House ID、多 tile flags 和其余透明 tile。
