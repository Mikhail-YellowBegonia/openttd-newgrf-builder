# 技术调研索引

本目录用于把“可验证的 NewGRF 约束”与具体实现决策分开记录。调研优先引用官方规范和工具项目自身文档。

## 第一批问题

- House feature 的 Action 0 属性与 callback 最小集合是什么？
- 当前 `agrf` 抽象最终输出了哪些 Action 1/2/3 结构？
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

## 产出格式

每个结论应包含：规范链接、适用版本、最小实验、结论、未决风险，以及它对生成器或素材标准的具体影响。未经游戏内实验验证的推断必须标记为“待验证”。
