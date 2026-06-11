# 微信视频号下载器依赖策略

> 文档编号：2026-05-wx-channels-dependency-policy
> 创建日期：2026-05-28
> 状态：Approved

---

## 1. 当前状态

`scripts/wx_channels_download/` 是对上游项目 [ltaoo/wx_channels_download](https://github.com/ltaoo/wx_channels_download) 的完整 vendored clone，共 **352 个文件**，语言为 Go。该目录从未被 git commit，当前状态为 untracked。

关键事实：

- 上游项目使用 **Commons Clause + MIT** 双重许可（详见第 2 节）。
- 内嵌的 gopeed 子模块（`pkg/gopeed/`）为 fork，使用 **GPLv3** 许可。
- `pkg/certificate/certs/private.key`（RSA 私钥）存在于磁盘上，被 `.gitignore` 排除。
- `SunnyRoot.cer`（MITM root CA 证书）存在于 `pkg/certificate/certs/` 和 `docs/public/` 两处。
- F0 importer（`src/finer/ingestion/wechat_adapter.py`）中 `WeChatChannelsDownloadClient` 默认将 binary 路径硬编码为 `scripts/wx_channels_download/wx_video_download`，要求编译产物存在于该路径。

项目级 `.gitignore` 已有以下防御规则：

```
!scripts/wx_channels_download/**/*.json
scripts/wx_channels_download/**/*.log
scripts/wx_channels_download/**/*.db
scripts/wx_channels_download/**/*.key
```

## 2. 许可风险分析

### 2.1 wx_channels_download：Commons Clause + MIT

原作者 ltaoo 对主项目施加了 **Commons Clause v1.0** 限制，叠加在 MIT 许可之上：

> The grant of rights under the License will not include, and the License does not grant to you, the right to Sell the Software.
>
> "Sell" means practicing any or all of the rights granted to you under the License to provide to third parties, for a fee or other consideration, a product or service whose value derives, entirely or substantially, from the functionality of the Software.

**对 Finer 的影响**：

- 如果 Finer 的商业模式依赖或实质受益于视频号下载功能的变现，则构成"Sell"，需要单独获取商业许可。
- 即使不直接销售，将 Commons Clause 代码嵌入 Finer 发布物也会增加下游用户的合规负担。
- Commons Clause 与标准 MIT 不同，不属于 OSI 认可的开源许可，限制了再分发自由度。

### 2.2 gopeed fork：GPLv3

`pkg/gopeed/` 是对 [GopeedLab/gopeed](https://github.com/GopeedLab/gopeed) 的本地 fork，许可为 **GNU GPLv3**。go.mod 中通过 `replace` 指令指向本地路径：

```
replace github.com/GopeedLab/gopeed => ./pkg/gopeed
```

**GPLv3 的 copyleft 义务**：

- 任何包含 GPLv3 代码的衍生作品，整体必须以 GPLv3 发布。
- 必须向接收者提供完整对应源代码。
- Finer 当前未以 GPLv3 发布，将 GPLv3 代码嵌入发布物将直接违反 GPLv3 条款。

### 2.3 兼容性结论

| 许可 | 类型 | 与 Finer 许可兼容 | 风险等级 |
|------|------|-------------------|---------|
| Commons Clause + MIT | 限制性开源 | 不兼容（禁止销售 + 再分发限制） | 高 |
| GPLv3 | Copyleft | 不兼容（要求衍生作品 GPL 发布） | 高 |

**结论：不得将 wx_channels_download 源码或编译产物包含在 Finer 的任何发布物（git 仓库、Docker 镜像、安装包）中。**

## 3. 安全风险

### 3.1 RSA 私钥

`pkg/certificate/certs/private.key` 是用于 MITM 代理的 RSA 私钥。当前状态：

- 存在于磁盘上。
- 被 `.gitignore` 排除（`scripts/wx_channels_download/**/*.key`）。
- 从未进入 git 历史。

**风险**：如果该文件意外进入 git 历史或被包含在发布物中，任何拿到该私钥的人都可以解密通过 MITM 代理捕获的 HTTPS 流量。虽然该密钥是上游项目生成的通用密钥（非 Finer 专属），但暴露仍有安全隐患。

### 3.2 SunnyRoot.cer（MITM Root CA）

`SunnyRoot.cer` 是上游项目用于中间人抓包的 root CA 证书。文件同时存在于：

- `pkg/certificate/certs/SunnyRoot.cer`
- `docs/public/SunnyRoot.cer`

这是项目设计的一部分（MITM 代理架构），不是意外泄露。但该 CA 被系统信任后，可对任意 HTTPS 流量签名。

### 3.3 安全结论

该 vendored 目录包含密码学敏感材料（私钥 + MITM root CA），**不得包含在任何发布物中**。当前 `.gitignore` 规则提供了基本防御，但删除 vendored 目录是唯一彻底的解决方案。

## 4. 决策：External Install 方案

采用 **External Install** 模式：Finer 不内嵌 wx_channels_download 源码，改为要求用户自行安装。

### 4.1 方案设计

1. **删除 vendored 目录**（待用户确认，见第 5 节）。
2. **F0 importer 改为外部调用**：
   - `WeChatChannelsDownloadClient` 不再硬编码 `scripts/wx_channels_download/wx_video_download`。
   - 改为按优先级查找 binary：
     1. 配置文件中显式指定的路径（`configs/*.yaml` 的 `wx_download_bin` 字段）。
     2. `PATH` 环境变量中的 `wx_video_download`。
     3. 如未找到，抛出清晰的 `FileNotFoundError`，附带安装指引链接。
3. **文档化安装流程**：在项目 README 或 INSTALL 指南中说明如何 clone + build 上游项目。
4. **保留 `.gitignore` 防御规则**：即使删除 vendored 目录，保留相关 gitignore 规则作为防御层，防止未来误提交。

### 4.2 方案优势

- 消除许可风险：Finer 仓库和发布物中不包含任何 GPL/Commons Clause 代码。
- 消除安全风险：私钥和 MITM CA 不再存在于 Finer 工作目录。
- 降低仓库体积：减少 352 个文件。
- 明确责任边界：用户自行编译，许可合规由用户与上游直接关系决定。

### 4.3 不采用的方案及理由

| 方案 | 不采用理由 |
|------|-----------|
| 保留 vendored 目录但不发布 | 本地仍存在许可不兼容代码，存在审计风险 |
| 改为 git submodule | 仍受 GPLv3 copyleft 约束，submodule 内容会随 git clone 拉取 |
| 联系原作者获取商业许可 | 可行但耗时，作为长期选项保留（见第 6 节） |

## 5. 实施步骤

- [ ] **用户确认删除** `scripts/wx_channels_download/` 目录（需用户显式确认，属于红线操作）
- [ ] **更新 F0 importer**：`wechat_adapter.py` 中 `WeChatChannelsDownloadClient.__init__` 改为 PATH/config 查找逻辑，移除 `scripts/wx_channels_download/` 硬编码路径
- [ ] **配置扩展**：`configs/*.yaml` 和 `config.py` 新增 `wx_download_bin` 可选配置项
- [ ] **安装文档**：在 README 或 `docs/` 下新增 wx_channels_download 外部安装指引（clone、build、配置路径）
- [ ] **更新 CLAUDE.md**：在启动命令参考中移除对 `scripts/wx_channels_download` 的直接引用
- [ ] **验证 `.gitignore`**：确认规则仍覆盖 `scripts/` 下潜在的临时文件
- [ ] **更新 wechat API route**：`src/finer/api/routes/wechat.py` 中如引用 vendored 路径，同步修改
- [ ] **端到端测试**：验证外部 binary 调用链路（binary 存在 / 不存在 / 路径配置）

## 6. 后续选项

| 选项 | 条件 | 影响 |
|------|------|------|
| 联系原作者获取商业许可 | 如果 Finer 需要内嵌分发 | 需协商费用和条款，解除 Commons Clause 限制 |
| 自研替代方案 | 如果上游不再维护或需求变化 | 完全消除外部依赖，但投入较大 |
| 独立安装脚本 | 如果用户体验需要优化 | 提供 `scripts/install_wx_download.sh`，自动 clone + build |

**推荐**：External Install + 文档化，作为当前最优平衡点。如未来出现内嵌需求，再启动商业许可谈判。
