# 本地素材到 NewGRF 工作流

这是调研阶段确定的第一版本地自动打包接口。它先固定参考图板、人工后处理、审核闸门和可复现记录，再接入批量图像生成；AI 服务本身不属于构建器的隐含依赖。

## 输入和状态

`assets/manifest.csv` 是人工维护的任务清单。每行代表一个不可变 `asset_id` 的 revision，至少提供建筑身份、House ID、密度、年代、占地、模板、文件路径、mask、锚点、三类参考图来源和两个审核状态。

只有以下记录进入锁文件和发布构建：

```text
rights_status = approved
qa_status = approved
file_path 存在且是 zi4 RGBA PNG
贴图尺寸、锚点和 alpha 包络符合 template spec/mask
sha256 与文件内容一致
asset_id、building_id、house_id 不重复
```

未批准的记录可以留在 CSV 中，供生成和审核阶段追踪，但不会阻塞本地清单校验，也不会进入 `manifest.lock.yaml`。

## 命令

```sh
# 选择 .venv/bin/python（存在时）并检查所有清单行
make validate

# 生成确定性的锁文件
make lock

# 校验素材、生成 GRF、写入 building.grf.sha256
make package
```

锁文件写入 `assets/manifests/manifest.lock.yaml`。它记录原始 CSV 的 SHA-256 和本次实际进入构建的条目；构建产物旁的 `building.grf.sha256` 用于发布校验。

## 运行环境

`make package` 需要 NML 和 Pillow；当前默认生成器读取批准的 PNG，先生成
`building/building.nml`，再调用 NML 产出 GRF，正式路径不依赖 GoRender 或
grf-py。仓库中的 VOX/GoRender 文件位于历史原型路径，仅作考古参考。没有批准素材时，GRF 构建会明确失败并提示补充输入；这比生成一个空模组更安全。

本地建议使用仓库的 `.venv`：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 下一步实验

1. 为一个批准的 PNG 增加 zi4 母版和锚点字段；normal/zi2 由构建器最近邻派生。
2. 将锁文件条目替代当前 CSV 读取，继续由建筑记录生成稳定的 Action 0/1/2/3 顺序；编译器从 zi4 母版最近邻派生 zi2/normal。
3. 用最小的 1x1 House 实验验证 VarAction2 的东西邻接变量，再决定是否推广到建筑族。
