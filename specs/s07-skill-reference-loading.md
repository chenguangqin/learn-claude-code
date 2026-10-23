# Spec: s07 Skill reference 由系统加载

- 状态：提案（未实现）
- 涉及文件：`s07_skill_loading/code.py`、`tests/test_skill_loading.py`
- 日期：2026-10-23

## 1. 背景

s07 演示两级渐进加载：system prompt 里只放 skill 目录（catalog），模型需要时调用
`load_skill` 读取完整 `SKILL.md`。像 `skills/planandexecute` 这样带 `references/`
的 skill，还需要第三级：按需读取 reference 文件。

## 2. 现状与问题

当前 reference 的加载**完全依赖模型推理路径**：

1. `SkillLoader.scan()` 只读 `*/SKILL.md`，记录 `name / description / content`，
   不知道 skill 目录下还有哪些文件。
2. `load_skill` 原样返回 `SKILL.md` 文本，其中只有 `references/xxx.md` 这样的相对路径。
3. 唯一线索是 system prompt 里的
   `Each skill's extra files live under {SKILLS_DIR}/<skill-name>/.`
4. 模型自行拼出绝对路径，再调用 `read_file`。`run_read` 只做
   `(WORKDIR / path).resolve()`，不校验、不纠错。

问题：

| # | 问题 | 后果 |
|---|------|------|
| P1 | 路径拼接靠模型 | 弱模型容易漏段、写成相对 `WORKDIR` 的路径，读取失败 |
| P2 | prompt 里的 `<skill-name>` 实为**目录名**，catalog 展示的是 frontmatter `name` | 两者不一致时，模型按提示拼出的路径必然错误 |
| P3 | 模型不知道 skill 有哪些附带文件 | 只能读 `SKILL.md` 里提到的；文件改名后 `SKILL.md` 未同步就会失效 |
| P4 | `read_file` 可读任意路径 | 与 skill 无关的既有简化，本 spec 不处理，但新工具不应延续这一点 |

## 3. 目标 / 非目标

目标：
- reference 路径由系统解析，模型只需提供 skill 名 + `SKILL.md` 中写的相对路径。
- 模型在加载 skill 时能看到该 skill 的文件清单。
- 新工具只能读取对应 skill 目录内的文件。

非目标：
- 不改变 catalog 格式和"两级加载"的教学主线。
- 不处理 `read_file` 的通用沙箱问题（P4）。
- 不支持执行 skill 内的脚本（`scripts/`）。

## 4. 设计

推荐组合方案：**新增 `load_skill_file` 工具（方案 2）+ 扫描时登记文件清单（方案 3）**。

### 4.1 `SkillLoader.scan()` 登记目录与文件

每个 skill 额外记录：

```python
self.skills[name] = {
    "name": name,
    "description": description,
    "content": content,
    "dir": manifest.parent.resolve(),          # 以目录为准，解决 P2
    "files": [                                  # 相对 skill 目录的路径，排序
        "references/example.md",
        "references/plan-template.md",
        ...
    ],
}
```

清单规则：
- 递归列出 skill 目录下的普通文件，排除 `SKILL.md`、`__pycache__/`、隐藏文件。
- 上限 50 个文件，超出时截断并注明 `(+N more)`。

### 4.2 `load_skill` 返回内容

`SKILL.md` 原文之后追加一个系统生成的块（原文保持不变，放在最前面）：

```
<SKILL.md 原文>

---
[skill files]  (read with load_skill_file(name="planandexecute", path=...))
- references/example.md
- references/plan-template.md
- references/replanning.md
```

无附带文件时不追加。

### 4.3 新工具 `load_skill_file(name, path)`

```json
{"name": "load_skill_file",
 "description": "Read a file bundled with a skill (e.g. references/x.md). path is relative to the skill directory.",
 "input_schema": {"type": "object",
   "properties": {"name": {"type": "string"}, "path": {"type": "string"}},
   "required": ["name", "path"]}}
```

处理逻辑：

1. `name` 不存在 → `Error: Unknown skill '<name>'. Available: ...`
2. `target = (skill["dir"] / path).resolve()`
3. `not target.is_relative_to(skill["dir"])` → `Error: path escapes skill directory`
   （挡住 `../`、绝对路径、软链跳出）
4. 文件不存在 → `Error: '<path>' not found in skill '<name>'. Files: <清单>`
   （把清单返回给模型，便于自我纠正）
5. 读取文本，超过 50000 字符截断并注明。

### 4.4 system prompt

删除目前临时加的 `Each skill's extra files live under {SKILLS_DIR}/<skill-name>/.`，
改为一句：`Use load_skill_file to read files listed under a skill.`

### 4.5 加载层级（教学叙述）

| 层级 | 内容 | 何时进入上下文 | 由谁负责 |
|------|------|----------------|----------|
| L1 | catalog（name + description） | 每次请求 | system prompt |
| L2 | `SKILL.md` + 文件清单 | 模型调用 `load_skill` | `SkillLoader.load` |
| L3 | reference 文件 | 模型调用 `load_skill_file` | `SkillLoader.load_file`，路径由系统解析 |

## 5. 兼容性与测试

需要修改的既有测试（`tests/test_skill_loading.py`）：
- `load("code-review") == manifest`：该用例 skill 无附带文件，按 4.2 不追加，**保持通过**。
- `test_s07_exposes_only_base_tools_and_load_skill`：工具列表断言需加入 `load_skill_file`。

新增测试：
- 有 `references/` 的 skill：`load()` 以原文开头，并包含文件清单。
- `load_skill_file` 正常读取。
- `../SKILL.md` 之外的逃逸路径、绝对路径被拒。
- 文件不存在时错误信息包含可用清单。
- frontmatter `name` 与目录名不同时，`load_skill_file(name=<frontmatter name>)` 仍能读到文件（P2）。
- 清单排除 `__pycache__`。

手工验证：用 s07 跑一次 `planandexecute` 任务，确认模型调用的是
`load_skill_file(name="planandexecute", path="references/plan-template.md")`，
而不是自己拼绝对路径。

改完需要重新生成网页数据：`cd web && npx tsx scripts/extract-content.ts`。

## 6. 待定问题

- 文件清单是否要附带每个文件的首行/大小，帮助模型判断该不该读？（增加 L2 体积）
- `scripts/` 下的文件是否也列出？列出但不提供执行能力，可能诱导模型用 bash 去跑。
- 现有 `skills/agent-builder/references/` 下会生成 `__pycache__/*.pyc`（已被 `.gitignore`
  忽略，但存在于磁盘上），4.1 的排除规则必须覆盖它，否则会出现在文件清单里。
