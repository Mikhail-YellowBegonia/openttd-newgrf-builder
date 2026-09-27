# 素材工作区

体素建模和 GoRender 是先期技术路线的遗留内容，不属于当前素材标准。当前主线是 2D/2.5D 建筑图像素材，经统一裁切、锚点和 zoom 处理后进入 NewGRF 编译。

AI 生成素材、实景参考和人工处理中间文件体量可能很大。本目录只提交小型、可审计的元数据和明确允许再分发的项目素材；原始大文件后续应使用对象存储或 Git LFS，并在清单中记录校验和。

## 目录约定

- `references/`: 实景参考的授权副本或链接记录；
- `generated/`: 模型原始输出，不直接进入 NewGRF；
- `work/`: 抠图、透视、补绘、调色等可编辑中间稿；
- `approved/`: 已通过人工质量和权利检查、允许进入构建的素材；
- `manifest.csv`: 每个素材任务的身份、来源、生成参数和状态。
- `../templates/`: 确定性的画布、mask、辅助线、锚点和 tile 网格模板。

## 硬性要求

1. 每项素材必须有稳定的 `asset_id`。
2. 风格参考、建筑参考和草图必须分别记录 URI/作者/许可证或“仅作不可分发参考”。
3. AI 输出必须记录模型、模型版本、提示词版本、seed 和生成日期。
4. 人工修改必须保留可编辑源文件并记录作者与 `postprocess_status`。
5. 只有 `rights_status=approved` 且 `qa_status=approved` 的素材才能进入发布构建。
6. 已批准 PNG 必须声明模板 spec、zoom、mask 和 anchor，并通过 mask 外 alpha 检查。

详细归档约束见 [`research/asset-archive-standard.md`](../research/asset-archive-standard.md)。`manifest.csv` 当前仅定义最小字段，字段会随第一轮原型调整。
