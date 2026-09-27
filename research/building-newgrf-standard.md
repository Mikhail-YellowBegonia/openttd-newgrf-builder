# 建筑类 NewGRF 文件标准

状态：第一轮规范基线，来源以 GRFSpecs 为准；实现细节仍需最小 GRF 实验确认。

## 1. 交付物分层

一个建筑 NewGRF 至少有四层交付物：

1. **素材源文件**：PNG/PSD/Krita 等可编辑源，带透明通道和项目坐标系；
2. **精灵声明**：NML、grf-py 或等价编译器输入，描述图片裁剪、尺寸、zoom 和锚点；
3. **GRF 逻辑**：Action 0/1/2/3 及字符串、参数和兼容信息；
4. **发布包**：`.grf`、README/CHANGELOG、来源清单、许可证和可复现构建信息。

PNG 本身不是 NewGRF；它必须通过精灵声明进入 Action 1，并由 Action 2/3 绑定到 House ID。

## 2. House feature 的最小结构

### Action 0：属性

House feature 编号为 `07`。使用一个 House ID 前，必须先通过 property `08`（substitute building type）定义该 ID。常用属性如下：

| 属性 | 用途 | 自动化字段 |
| --- | --- | --- |
| `08` | 缺失时的替代建筑 | `substitute_id` |
| `09` | 1x1、2x1、1x2、2x2、平地、动画等 flags | `footprint`, `flat_only`, `animated` |
| `0A` / `21` / `22` | 出现年代 | `start_year`, `end_year` |
| `0B` / `0C` | 人口、邮件生成 | `population`, `mail_multiplier` |
| `0D` / `0E` / `0F` | 旅客、邮件、货物接受 | `acceptance` |
| `12` | 查询窗口建筑名称 | `name_string_id` |
| `13` | town zone 与气候可用性 | `availability_mask` |
| `14` / `1D` | callback 能力开关 | `callback_flags` |
| `18` | 出现相对概率 | `probability` |
| `1C` | 建筑 class | `building_class` |
| `1E` | 接受的货物类型 | `accepted_cargos` |

多 tile 建筑的 north tile 先定义，随后连续定义附属 tile；附属 tile 只能设置有限的 flags，且名称、移除成本/评级等属性需要按规范保持一致。

### Action 1：精灵集合

Action 1 定义一个或多个 sprite set。对 House 来说，`num-ent` 是 construction stage 的数量，规范允许 1 到 4，超过 4 的内容会被忽略。建筑最终选择哪一组精灵，不由 Action 1 单独决定。

当前 NML 编译路径支持基础 1x1 和 2x2：approved zi4 PNG 由构建器派生低倍率；2x2 完整画布绑定到 north tile，其余三个 tile 使用透明精灵，并由 NML 自动生成连续 House ID、House flags 和 Action 3 绑定。

### Action 2：图形决策

普通 Action 2 将 Action 1 的精灵集合编成可引用的 set ID。VarAction2 则根据变量和范围跳转到不同的 Action 2 set，可用于：

- construction stage；
- town zone、地形、建筑年龄；
- 建筑自身的随机位；
- 相邻 tile 的 house class/ID/GRFID；
- 多 tile 建筑的动画帧。

### Action 3：House ID 绑定

Action 3 的 feature 为 `07`，把一个或多个 House ID 绑定到 Action 2 set。对 Houses，`num-cid` 必须为零，只有 default set ID 生效；不能照搬车辆按 cargo 分支的写法。

## 3. 推荐的项目内部输入

未来自动化不直接编辑二进制，而是生成一个建筑记录，再由编译器输出 Action 0/1/2/3：

```yaml
building_id: cn_town_1979_001
house_id: 128
class: town_residential
era: [1979, 2000]
density: town
footprint: 1x1
climate: [temperate]
town_zones: [2, 3, 4]
sprites:
  master_zi4: assets/approved/cn_town_1979_001/zi4.png
  template_spec: templates/isometric-1x1-h8/spec.json
  mask: templates/isometric-1x1-h8/zi4.mask.png
  construction_stages: 1
logic:
  adjacency: none
  random_variants: 4

zoom_derivation:
  zi2: nearest_2x
  normal: nearest_4x
```

这个 YAML 不是 NewGRF 标准格式，而是本项目的可审计中间格式。它必须能稳定生成相同的 House ID、Action 顺序和 sprite set ID。

## 4. 构建产物约定

- `building.grf`：可加载的 NewGRF；
- `building.grf.sha256`：发布文件校验和；
- `manifest.lock.yaml`：参与本次构建的素材版本、编译器版本和输入哈希；
- `CHANGELOG`：对 House ID、属性和素材的变更说明。

### 规范依据

- [Action 0](https://newgrf-specs.tt-wiki.net/wiki/Action0)
- [Action 0 Houses](https://newgrf-specs.tt-wiki.net/wiki/Action0/Houses)
- [Action 1](https://newgrf-specs.tt-wiki.net/wiki/Action1)
- [Action 2](https://newgrf-specs.tt-wiki.net/wiki/Action2)
- [Variational Action 2](https://newgrf-specs.tt-wiki.net/wiki/VariationalAction2)
- [Variational Action 2 Houses](https://newgrf-specs.tt-wiki.net/wiki/VariationalAction2/Houses)
- [Action 3](https://newgrf-specs.tt-wiki.net/wiki/Action3)

## 5. 待验证事项

- 目标 OpenTTD 最低版本与 House ID 上限；OpenTTD 15 的规范页面记录了 4096 House ID 上限，仍需在项目版本策略中正式锁定。
- 目标编译器对 32bpp-only sprite 的兼容行为；规范允许加载，但 8bpp 模式会显示红色问号回退图。
- 多 tile House 的 Action 3/VarAction2 重绘时机。
