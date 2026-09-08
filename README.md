# ai-daily

日报系列的唯一权威源。私有库，`yawnzhao/ai-daily`。

每天一篇，落在 `daily/YYYY/YYYY-MM-DD.md`。由 agent 每天更新，人负责定规则和抽查。

## 目录

| 路径 | 放什么 |
|---|---|
| `daily/YYYY/YYYY-MM-DD.md` | 当天成稿。一天一个文件，文件名即日期，不改历史文件 |
| `templates/daily.md` | 成稿模板。改格式改这里，不在单篇里即兴发挥 |
| `data/runs/YYYY-MM-DD-receipts.json` | 当天的采集收据：查了哪些源、成功失败、原始条目。没有收据的成稿不算数 |
| `config/` | 信源与门槛（**待建**，规则定下来之后再加） |
| `scripts/` | 采集与校验脚本（**待建**） |
| `AGENTS.md` | agent 的执行契约。动手前先读它 |

## 状态

骨架已建，**内容规则未定**。`AGENTS.md` 里标了「待定」的段落需要人先填，填完之前 agent 不应开始每日例行。

## 备份

本库是 `AI-digest` 工作区里少数有 git 和 GitHub 私有远端的地方之一。工作区根目录不在 Time Machine 备份内，所以：**权威内容写进这个库并 push，才算有副本。**
