# TTD 建筑制作工作台

这是一个本地运行的半自动建筑制作工作台，把已经验证过的人工环节和现有
`tools.work_order` 流程串起来。

## 启动

```sh
python3 -m web.workbench.server
```

或在仓库根目录执行：

```sh
make workbench
```

如果从仓库根目录执行，也可以使用：

```sh
python3 web/workbench/server.py
```

然后打开 <http://127.0.0.1:4173/workbench/>。

## 当前工作流

1. 填写建筑身份、占地、年代、密度、House ID 和模板；
   方向素材可选择单图复用或四方向计划；当前四方向编译仍会被明确拦截，避免产出错误 GRF；
2. 记录风格、建筑和草图参考；
3. 填写 provider、模型、提示词版本和 seed，复制提示词到外部生图服务；
4. 上传生成结果并人工审核；
5. 在画布上用多边形点选建筑轮廓，生成 alpha mask；
6. 在画布上标定原点、X 轴和 Y 轴；
7. 调用现有 Python 工具生成标定预览、zi4 和占地切片；
8. 审核通过后复制到 `assets/approved/`，登记 `assets/manifest.csv`；
9. 按需执行 `make package` 构建整个 GRF。

工作台不保存 AI 服务 API Key，也不把某一家生图服务写死。AI 生成目前保留为
“外部调用后上传结果”，后续可增加 provider adapter。

## 文件位置

- 工单：`assets/work_orders/<work_order_id>.json`
- AI 原图：`assets/generated/<work_order_id>.png`
- 手工 alpha mask、预览和 zi4：`assets/work/`
- 通过审核的成品：`assets/approved/`

这是第一版本地工作台，服务只监听回环地址，适合单人制作和审核，不提供多用户
权限或远程部署能力。
