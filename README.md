# ai-daily

日报系列的唯一权威源。**公开库** `yawnzhao/ai-daily`，同时是站点 <https://yawnzhao.github.io/ai-daily/> 的 GitHub Pages 来源。

每天一篇，落在 `daily/YYYY/YYYY-MM-DD.md`。由 agent 每天更新，人负责定规则和抽查。

## 目录

| 路径 | 放什么 |
|---|---|
| `daily/YYYY/YYYY-MM-DD.md` | 当天成稿。一天一个文件，文件名即日期，不改历史文件 |
| `index.html`、`ai-daily-digest-YYYY-MM-DD.html` | 站点页面。push 到 `main` 后由 GitHub Pages 直接发布 |
| `templates/daily.md` | 成稿模板。改格式改这里，不在单篇里即兴发挥 |
| `data/runs/YYYY-MM-DD-receipts.json` | 当天的采集收据：查了哪些源、成功失败、原始条目。没有收据的成稿不算数 |
| `config/` | 信源、来源分级与覆盖门槛 |
| `scripts/` | 采集、页面生成与发布前校验脚本 |
| `data/issues/`、`templates/daily.html` | 单期公开元数据与原版四栏目页面模板 |
| `AGENTS.md` | agent 的执行契约。动手前先读它 |

## 公开范围

任何人都能看到本库的全部内容，**包括提交历史和提交说明**。所以：

- 成稿、`data/runs/` 收据（含 `evidence` 和备注）、提交说明，都按「对外发布」的标准来写。
- 密钥、令牌、Cookie、登录态、私人联系方式一律不进库，本机绝对路径也不写。
- 删除文件不等于撤回，历史里仍然查得到。误提交了密钥，**先到服务商那里轮换**，再考虑清理历史。
- 不打算公开的内容（内部讨论、未定稿的规则草案、私人素材）放在工作区其他地方，不放这里。

## 状态

截至 2026-09-26，已发布 **20 期**。最新一期为 [第 20 期 · 2026-09-26](https://yawnzhao.github.io/ai-daily/ai-daily-digest-2026-09-26.html)，正文和[小宇宙语音版](https://www.xiaoyuzhoufm.com/episode/6ab764c0e742e36efcbb5b61)均已上线，音频时长约 **11 分 24 秒**。

- **线上核验**：第 20 期音频更新提交 `1cd5b718de3e98345a87740c81f72ecfab04df67` 对应的 [GitHub Pages 部署](https://github.com/yawnzhao/ai-daily/actions/runs/36228526574)成功。首页、最新一期、RSS 和站点地图可访问；最新一期 HTML 与该版本仓库文件一致。浏览器已成功加载音频，但本次未完整试听。
- **采集范围**：第 20 期完成 19/24 个来源，5 个部分完成，成功率 79.2%，已标注“采集不完整”。arXiv 报告 596 条、取得 500 条，仍缺 96 条；其余待补来源为通义、智谱、阶跃和 OpenReview。不能据此判断这些来源没有新消息。
- **历史音频**：当前首页中，2026-09-19、09-20、09-21、09-25 仍显示“语音版制作中”；这仅反映本站状态，不代表已经核验这些日期在小宇宙上的发布情况。
- **自动化**：原 AI-daily routine 的启停及切换状态尚未确认。

第 19 期于 2026-09-25 恢复原版 UI，第 20 期继续沿用橙色配色、居中标题、卡片和四栏目结构，采集说明折叠展示。

正文仍以 `daily/YYYY/YYYY-MM-DD.md` 为权威；`data/issues/YYYY-MM-DD.json` 保存条目来源、日期、栏目、页面标题及音频状态，不复制整份正文。公开收据只保存可公开的来源链接与检查结论。生成脚本沿用现有文件名，但现在使用 `templates/daily.html`，不再使用 `templates/editorial.html` 或 `assets/editorial-v2/`。后续更新在原有框架内做小幅调整，不重新设计版式。

```sh
python3 scripts/build_editorial_issue.py 2026-09-26
python3 scripts/build_site.py
python3 scripts/check_page.py
python3 -m unittest discover -s scripts -p 'test_editorial_pages.py'
```

将生成文件与对应正文、元数据、收据提交到 `main` 后，GitHub Pages 发布站点。首页、RSS 与上下期导航由 `build_site.py` 统一生成。

语音未发布时，页面仅显示“制作中”和小宇宙节目入口；取得匹配本期内容的 HTTPS 音频直链后，再更新 `audio_src` 并重新构建。音频发布与定时采集任务的切换分别核验。

## 备份

本库是 `AI-digest` 工作区里少数有 git 和 GitHub 远端的地方之一（远端是公开库，见上文「公开范围」）。工作区根目录不在 Time Machine 备份内，所以：**权威内容写进这个库并 push，才算有副本。**
