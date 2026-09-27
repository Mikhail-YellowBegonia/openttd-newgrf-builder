# TTD 建筑标定页

这是一个无依赖的静态页面，用来替代 Photopea 的手工测量。

打开 `index.html` 后：

1. 加载 PNG/JPEG/WebP；
2. 点击地基南角作为原点；
3. 点击 X 轴边界终点；
4. 点击 Y 轴边界终点；
5. 下载标定 JSON，或下载带标记的 PNG。

鼠标位置会显示两条固定的 OpenTTD 地面轴，屏幕边角分别为约 `26.565°` 和
`153.435°`，夹角为 `126.870°`。点击 X/Y 终点时，页面会把点击位置投影到对应
轴线上，因此不会再因为测量工具读数格式或轻微手抖产生非标准角度。JSON 的
`raw_clicks` 保存原始落点，`projected_clicks` 保存用于校准的投影点。

导出的 JSON 字段可以直接复制到工单的 `calibration`：

- `source_origin`：原始图片坐标中的地基南角；
- `source_x_axis`、`source_y_axis`：从原点到两条地基边终点的向量；
- `ground_tile_size`：两条边中较长者；
- `axis_scope`：1×1 为 `tile`，2×2 为 `footprint`；
- `projection_mode`：页面输出 `uniform`，不做投影仿射矫正。

页面不会修改源图，也不会自动抠图。建议先准备带透明通道的 PNG；JPEG 只能用于
标定参考，不能直接作为最终素材。
