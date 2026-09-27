# AI 建筑素材生成配置

当前首选模型是 OpenAI GPT Image 系列，默认配置使用 `gpt-image-2`。模型根据风格参考、建筑参考和可选草图生成建筑候选；人工清理和 zi4 落位之后，模板约束、mask 检查、最近邻 LOD 派生和 NewGRF 编译仍由本地工具完成。

## 本地配置

不要把 API key 写入仓库。使用当前 shell 的环境变量：

```sh
export OPENAI_API_KEY="..."
```

配置见 [`providers/openai-gpt-image.yaml`](providers/openai-gpt-image.yaml)，提示词见 [`prompts/cn-building-zi4.txt`](prompts/cn-building-zi4.txt)。参考图分为风格/空间参考、建筑内容参考和可选草图；`zi4.guide.png` 默认只在生成后用于人工落位和 QA。

## 生成约束

- 只生成 zi4；不要让模型分别生成 normal 或 zi2；
- 生成阶段不要求模型精确理解 guide 的白色包络或 40m 箭头；人工落位阶段才应用最大允许绘制包络；
- 平房、低层公寓和窄体建筑可以只占用包络的一部分；
- 黑色区域和红色 40m 箭头属于 guide，不应出现在建筑成品中；
- 生成结果进入 `assets/generated/`，经过抠图、mask、锚点和权利审核后才能进入 `assets/approved/`。

当前仓库只提交配置和提示词，不在没有明确 API 调用授权的情况下自动发送外部请求。
