# 素材归档与可追溯标准

目标：未来无论素材由 AI、人工绘制还是程序合成产生，都能回答“谁在何时用什么输入生成了什么，经过哪些修改，依据什么批准发布”。

## 1. 每个建筑一个不可变 asset_id

建议格式：

```text
cn-{density}-{era}-{family}-{serial}
```

例如：`cn-town-1979_2000-midrise-001`。asset_id 一旦进入发布版本不得复用；素材迭代用 `revision` 和内容哈希区分。

## 2. 目录层级

```text
assets/
  references/   # 实景参考或仅链接记录
  generated/    # 模型原始输出
  work/         # 抠图、重绘、调色、透视和合成中间稿
  approved/     # 进入构建的最终 PNG/源文件
  manifests/    # manifest.lock.yaml、哈希和批次记录
```

原始大文件不强制全部进 Git；但 Git LFS、对象存储或外部链接都必须通过 manifest 固定版本和 SHA-256。

## 3. 最小记录字段

| 字段 | 要求 |
| --- | --- |
| `asset_id` / `revision` | 必填，唯一 |
| `building_id` / `house_id` | 与代码定义绑定 |
| `density` / `era` / `footprint` | 内容分类 |
| `style_reference_uri` / `architecture_reference_uri` / `sketch_reference_uri` | 参考图板中三类输入的来源；草图可为空 |
| `reference_author` / `reference_license` | 参考来源的作者和许可证 |
| `generator_type` | `ai`, `manual`, `procedural`, `hybrid` |
| `model` / `model_version` / `prompt_hash` / `seed` | AI 生成时必填 |
| `parent_assets` | 由哪些素材派生 |
| `artist` / `edited_at` / `toolchain` | 人工处理记录 |
| `postprocess_status` | `pending`, `cleaned`, `fitted`, `approved` |
| `sha256` / `dimensions` / `zoom_levels` | 文件完整性与图形规格；源素材固定为 zi4，低倍率由最近邻派生 |
| `rights_status` | `unknown`, `review`, `approved`, `rejected` |
| `qa_status` | `pending`, `failed`, `approved` |
| `reviewer` / `reviewed_at` / `notes` | 审核证据 |

## 4. 状态机

```text
reference -> generated -> work -> candidate -> approved -> released
                                  \-> rejected
```

- `generated` 不得直接进入构建；
- `candidate` 必须完成尺寸、透明、锚点、视角一致性和来源检查；
- `approved` 只允许追加新 revision，不原地覆盖；
- `released` 由某次构建的 `manifest.lock.yaml` 固定，不随主分支后续修改而漂移。

## 5. AI 生成记录原则

- 不保存无法合法再分发的实景图副本；可以保存 URL、作者、许可证和检索日期；
- prompt 本身也要版本化，使用 `prompt_hash` 防止长文本字段造成重复；
- 记录模型供应商和模型版本，不把“AI 生成”当作来源许可证；
- 人工重绘、拼接、清理和最终选择必须单独记录；
- 对建筑 logo、广告、可识别个人和受版权保护的独特外观进行人工审查。

## 6. 构建闸门

自动化构建只接受同时满足以下条件的记录：

```text
rights_status == approved
qa_status == approved
file exists
sha256 matches
building_id and house_id are unique
all declared zoom levels pass sprite validation
```

### 与现有清单的关系

现有 `assets/manifest.csv` 保留作人工查看和批量导入格式；正式构建时应由它生成锁定的 `assets/manifests/manifest.lock.yaml`，而不是直接信任 CSV 的当前内容。
