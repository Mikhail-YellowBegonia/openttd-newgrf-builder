# 技术调研索引

本目录用于把“可验证的 NewGRF 约束”与具体实现决策分开记录。调研优先引用官方规范和工具项目自身文档。

## 当前结论

本项目的新主线是“AI 生成/修整 2D/2.5D 建筑素材 + 程序化 NewGRF 编译”，不是体素建模再渲染。仓库中已有的 MagicaVoxel/GoRender 代码属于上一次原型验证的遗留路径，默认构建不会导入或依赖它们。

第一轮标准已经拆成三份：

- [建筑 NewGRF 结构](building-newgrf-standard.md)：House feature、Action 0/1/2/3 和构建产物；
- [建筑精灵标准](building-sprite-standard.md)：32bpp、Info version 32、zoom、锚点、透明和兼容策略；
- [素材归档标准](asset-archive-standard.md)：素材身份、来源、生成记录、人工处理、QA 和发布闸门。
- [参考图驱动工作流](ai-art-workflow.md)：风格参考、建筑参考、草图、人工清理和 zi4 落位流程。

本地构建入口和当前依赖边界见[本地工作流](local-build-workflow.md)。清单校验与锁文件生成可以先独立运行；真正生成 `.grf` 需要 NML 和 Pillow，正式路径不再依赖 grf-py。

## 第一批问题

- House feature 的 Action 0 属性与 callback 最小集合是什么？
- NML 输出的 Action 1/2/3 结构是否覆盖当前建筑工单的最小需求？
- 32bpp 与 extra zoom 精灵在编码、尺寸、offset、透明通道方面有哪些硬约束？
- 建筑年代、城镇 zone、人口与替换概率应如何映射到项目的密度/年代分类？
- 相邻建筑信息能否在 house feature 的可用变量和 scope 中稳定读取？
- 大批量素材如何保持视角、太阳方向、阴影强度、尺度与八方向一致？

## 权威入口

- [NewGRF specification](https://newgrf-specs.tt-wiki.net/wiki/Main_Page)
- [House feature](https://newgrf-specs.tt-wiki.net/wiki/Houses)
- [Action 2](https://newgrf-specs.tt-wiki.net/wiki/Action2)
- [Variational Action 2](https://newgrf-specs.tt-wiki.net/wiki/VariationalAction2)
- [Real sprites](https://newgrf-specs.tt-wiki.net/wiki/RealSprites)
- [NML documentation](https://www.tt-wiki.net/wiki/NMLTutorial)
- [grf-py](https://github.com/citymania-org/grf-py)
- [GoRender](https://github.com/mattkimber/gorender)

## 证据等级

- **规范**：直接来自 GRFSpecs、OpenTTD/NML 或 grf-py 文档；
- **实验**：由最小 GRF 和游戏内观察确认；
- **决策**：项目为自动化和内容质量做出的约束；
- **待验证**：规范没有直接回答，必须做实验后才能进入正式版本。

## 产出格式

每个结论应包含：规范链接、适用版本、最小实验、结论、未决风险，以及它对生成器或素材标准的具体影响。未经游戏内实验验证的推断必须标记为“待验证”。
