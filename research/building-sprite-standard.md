# 建筑精灵标准

状态：以 OpenTTD Info version 32 / Real Sprites 规范为基线。

## 1. 文件与颜色

推荐源素材使用 PNG，保留 RGBA 透明通道；编译时按 Info version 32 声明为 `32bpp`。规范同时定义 `8bpp`、`32bpp` 和紧随其后的 `mask` 类型：mask 是同尺寸的 8bpp 调色板，用于透明/染色等特殊效果。

32bpp-only 在现代 OpenTTD 中可以加载，但规范指出 8bpp 模式没有 8bpp 普通精灵时会显示红色问号。项目决策暂定为：

- 主交付采用 32bpp；
- 是否生产 8bpp fallback 作为发布配置，不混入素材源标准；
- 在首个可玩 Demo 中实测目标 OpenTTD 版本，再决定是否强制 fallback。

## 2. Zoom 等级

Info version 32 支持：

| 名称 | 相对尺寸 | 用途 |
| --- | --- | --- |
| `zo8` / `zo4` / `zo2` | 缩小 | 远景显示 |
| `normal` | 1x | 标准视图 |
| `zi2` | 2x 放大 | 推荐的高质量近景 |
| `zi4` | 4x 放大 | 极近景/最高质量 |

对于 normal zoom，游戏 tile 的参考网格是 64×32；`zi2` 约为 128×64，`zi4` 约为 256×128。建筑本身可以超出一个 tile，但必须使用统一的地面中心和锚点规则。

“最现代的 32bpp 精灵分辨率”在工程上应解释为：**Info version 32 + 32bpp + 至少 normal/zi2，必要时 zi4**，而不是任意放大 PNG。每个 zoom 应独立检查轮廓、阴影和细节，禁止简单 nearest-neighbor 放大作为最终素材。

## 3. 精灵记录字段

每个 real sprite 至少需要：

- 文件路径；
- 类型：`8bpp` / `32bpp` / `mask`；
- 在图集中的 `xpos`, `ypos`；
- `xsize`, `ysize`；
- `xrel`, `yrel` 锚点；
- zoom level；
- flags：如 `nocrop`, `chunked`。

透明边界、锚点和尺寸属于逻辑数据，不能仅存在于美术软件工程文件里；它们必须进入机器可读 manifest。

## 4. 建筑方向与施工阶段

House Action 1 的 `num-ent` 是施工阶段数，规范上限为 4；它不是建筑四向视图数。建筑方向应作为同一 sprite set 内的布局/视图组织，由编译器或项目布局层负责。

项目素材标准建议：

- 每个建筑先定义 canonical north-east 参考方向；
- 如果建筑存在明显不对称，生成并审查 4/8 个方向；
- 方向之间必须共享同一太阳方向、地面中心、层高和裁切规则；
- 施工阶段若不需要独立图像，使用一个阶段，不能伪造空白阶段破坏 Action 逻辑。

## 5. 自动 QA

构建前拒绝以下情况：

- RGBA 图片含有未预期的半透明背景像素；
- sprite 宽高为零，或超过编码器限制；
- `xrel/yrel` 缺失、超出有符号 16 位范围；
- 同一建筑不同 zoom 的 anchor 换算不一致；
- 32bpp sprite 后缺失所需的 mask；
- 8bpp fallback 被声明却不是 normal zoom 的第一条 sprite。

### 规范依据

- [Real Sprites](https://newgrf-specs.tt-wiki.net/wiki/RealSprites)
- [Action 1](https://newgrf-specs.tt-wiki.net/wiki/Action1)
- [NML graphics documentation](https://github.com/OpenTTD/nml/tree/master/docs)
