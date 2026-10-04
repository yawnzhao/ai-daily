# ai-daily

日报系列的唯一权威源。**公开库** `yawnzhao/ai-daily`，同时是站点 <https://yawnzhao.github.io/ai-daily/> 的 GitHub Pages 来源。

每天一篇，落在 `daily/YYYY/YYYY-MM-DD.md`。由 agent 每天更新，人负责定规则和抽查。

上游采集例行设为 **05:00 Asia/Shanghai**（北京时间，UTC+8），即前一日历日 **21:00 UTC**，配置见 `config/sources.json`。iMac 在 06:00 接续验收、补采和制作，07:50 接续发布，目标 08:00 左右公开；部署、转码和审核以实际完成状态为准。刊期日期按北京时间的日历日。

成稿权威文件就是这份 Markdown，随本库提交。GitHub Pages 页面由它生成。本流水线不向 Notion 发布。

## 目录

| 路径 | 放什么 |
|---|---|
| `daily/YYYY/YYYY-MM-DD.md` | 当天成稿。一天一个文件，文件名即日期，不改历史文件 |
| [daily/scripts/STYLE.md](daily/scripts/STYLE.md) | 口播写作与证据表达：通俗例子、故事与适度幽默；相关证据与第三方评测的使用 |
| [daily/scripts/README.md](daily/scripts/README.md) | 口播文件、长度、发音和音频制作约定 |
| `index.html`、`ai-daily-digest-YYYY-MM-DD.html` | 站点页面。push 到 `main` 后由 GitHub Pages 直接发布 |
| `templates/daily.md` | 成稿模板。改格式改这里，不在单篇里即兴发挥 |
| `data/runs/YYYY-MM-DD-receipts.json` | 当天的采集收据：查了哪些源、成功失败、原始条目。没有收据的成稿不算数 |
| `config/` | 信源、来源分级与覆盖门槛 |
| `templates/source-review.md` | 来源与论文轻量周回顾模板 |
| `data/runs/YYYY-MM-DD-source-review.md` | 按实际跨度保存的来源回顾、论文候选理由与主题追踪 |
| `scripts/` | 采集、页面生成与发布前校验脚本 |
| `data/issues/`、`templates/daily.html` | 单期公开元数据与原版四栏目页面模板 |
| `AGENTS.md` | agent 的执行契约。动手前先读它 |

## 来源与回顾规则

当前来源以 [config/sources.json](config/sources.json) 为准；执行方法见 [AGENTS.md](AGENTS.md)。每次运行先拉取 main，并把配置 commit 记入收据。来源数量从配置计算，历史收据保留当期口径。

2026-09-27 的清单为 32 源：在原有 24 源基础上加入 36氪、网信办、字节 Seed、MiniMax，以及两周试用的 TechCrunch、Ars Technica、MIT Technology Review、404 Media。试用源计入覆盖率，浏览器来源完成补查前仍为 pending。媒体按文章判断原创与转载，不能把域名当作原创保证。

论文继续使用 arXiv、HF Daily Papers、OpenReview 等现有渠道。按稳定论文 ID 记录核验范围与采用理由；每周用 [回顾模板](templates/source-review.md) 做轻量评价，先追踪 Agent 与评测/可靠性两个方向。规则由执行日报的 agent 落实，本次未新增自动评分器或定时任务。

每天衔接 [AI 话语场素材库](https://github.com/yawnzhao/ai-concourse-library)：播客、访谈、演讲的新增清单与待补材料在该库积累。日报从整个积累库选择 1—3 条与当期新闻相关、材料已核验的内容，写入正文、网页“话语场精选”和自然口播，保留原始日期与语境。分别报告两套来源覆盖，先验收已有运行，只补实际缺口。

## 公开范围

任何人都能看到本库的全部内容，**包括提交历史和提交说明**。所以：

- 成稿、`data/runs/` 收据（含 `evidence` 和备注）、提交说明，都按「对外发布」的标准来写。
- 密钥、令牌、Cookie、登录态、私人联系方式一律不进库，本机绝对路径也不写。
- 删除文件不等于撤回，历史里仍然查得到。误提交了密钥，**先到服务商那里轮换**，再考虑清理历史。
- 不打算公开的内容（内部讨论、未定稿的规则草案、私人素材）放在工作区其他地方，不放这里。

## 状态

截至 2026-10-04，已发布 **28 期**。最新一期为 [第 28 期 · 从演示到交付：训练、权限与停止机制](https://yawnzhao.github.io/ai-daily/ai-daily-digest-2026-10-04.html)，正文和[小宇宙语音版](https://www.xiaoyuzhoufm.com/episode/6ac19718e742e36efcbe28d9)均已公开，节目时长约 **13 分 50 秒**。

- **音频**：本期使用自然口播与原创新闻歌曲混音。正式公开音频已通过可达性、完整解码、时长及静音段核验，并回填当期页面与首页；原始音频和制作成品不入库。本次未完整试听，不将解码核验等同于听感核验。首页 28 期均有音频入口。
- **采集范围**：新闻截至北京时间 06:00，完成 **27/35 个来源**，8 个部分完成，仍标注“采集不完整”。待补来源为 Microsoft、通义、DeepSeek、智谱、阶跃、OpenReview、MIT Technology Review 和 404 Media；详见[当日采集收据](data/runs/2026-10-04-receipts.json)。不能据此判断这些来源没有新消息。
- **话语场**：[当日新增清单](https://github.com/yawnzhao/ai-concourse-library/blob/main/data/digest/2026-10-04.md)归档 22 条。本期采用 Keerthana Gopalakrishnan 在 The Cognitive Revolution 的机器人访谈，网页与口播采用同一条已核验材料；其他节目缺文字材料的状态继续保留。
- **自动化**：本期已接续本机 06:00 准备与 07:50 发布阶段，复用验收合格的采集结果并补缺。目标时间与实际公开时间分别记录；上游外部定时任务的启停不因本次运行而推定。

页面继续使用橙色配色、居中标题、卡片和四栏目结构；逐源目录与采集说明默认折叠。

正文仍以 `daily/YYYY/YYYY-MM-DD.md` 为权威；`data/issues/YYYY-MM-DD.json` 保存条目来源、日期、栏目、页面标题及音频状态，不复制整份正文。公开收据只保存可公开的来源链接与检查结论。生成脚本沿用现有文件名，但现在使用 `templates/daily.html`，不再使用 `templates/editorial.html` 或 `assets/editorial-v2/`。后续更新在原有框架内做小幅调整，不重新设计版式。

```sh
python3 scripts/build_editorial_issue.py 2026-10-04
python3 scripts/build_site.py
python3 scripts/check_page.py
python3 -m unittest discover -s scripts -p 'test_editorial_pages.py'
```

将生成文件与对应正文、元数据、收据提交到 `main` 后，GitHub Pages 发布站点。首页、RSS 与上下期导航由 `build_site.py` 统一生成。

语音未发布时，页面仅显示“制作中”和小宇宙节目入口；取得匹配本期内容的 HTTPS 音频直链后，再更新 `audio_src` 并重新构建。音频发布与定时采集任务的切换分别核验。

## 备份

本库是 `AI-digest` 工作区里少数有 git 和 GitHub 远端的地方之一（远端是公开库，见上文「公开范围」）。工作区根目录不在 Time Machine 备份内，所以：**权威内容写进这个库并 push，才算有副本。**
