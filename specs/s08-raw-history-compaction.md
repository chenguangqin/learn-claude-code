# Spec: s08 原始历史与 API 视图分离

- 状态：提案（未实现）
- 涉及文件：`s08_context_compact/code.py`、`tests/test_compaction_tool_pairs.py`
- 日期：2026-10-23

## 1. 背景

s08 在每次调用模型前执行 `ContextCompactor.prepare()`：

```
tool_result_budget → snip_compact → micro_compact → 超限则 compact_history
```

另有两个入口：模型调用 `compact` 工具、API 报 prompt too long 时的 `reactive_compact`。

## 2. 现状与问题

### P1：总结的输入是已被压缩过的历史

`prepare()` 把经过 `micro_compact` 的 `messages` 直接传给 `compact_history`，
后者用它写 transcript、做总结。`compact` 工具和 `reactive_compact` 入口同理
（`messages` 在本轮开头已被 `prepare` 处理）。

### P2：`micro_compact` 原地修改，原文永久丢失

```python
block["content"] = "[Earlier tool result omitted.]"
```

`block` 就是 `history` 里的 tool_result 字典，`agent_loop` 又通过
`messages[:] = COMPACTOR.prepare(...)` 写回。因此：

- 超过最近 3 个的工具结果，原文在内存中被覆盖；
- 之后任何 transcript（snip 或 compact 写的）都只包含占位符；
- 只有 >30000 字符、被 `tool_result_budget` 落盘的结果可找回；
  **120–30000 字符之间的结果（最常见的 read_file / ls / 测试输出）在任何地方都没有原文**；
- summary 消息里的 `Full transcript: <path>` 名不副实。

### P3：`snip_compact` 每轮重复触发、重复写 transcript

裁剪后长度为 3 + 1(marker) + 47 = 51 > 50，下一轮再次触发，每轮都把整段历史
写一份新的 `.transcripts/transcript_<uuid>.jsonl`。

### P4（关联）：reactive compact 的错误识别可能不适配 Bedrock

识别依据是异常文本包含 `prompt_too_long` / `too many tokens`。切换到
`AnthropicBedrock` 后，Bedrock 的超长错误文案未验证是否命中；不命中则兜底失效、直接抛错。

## 3. 目标 / 非目标

目标：
- 存在一份**只追加、永不修改**的原始历史，作为唯一事实来源。
- 所有压缩只作用于"发给 API 的视图"，不回写原始历史。
- `compact_history` / `reactive_compact` 以原始历史写 transcript、做总结。
- transcript 文件不再每轮重复生成。

非目标：
- 不改变各层阈值的数值（教学用小阈值保留）。
- 不改为 token 精确计数（仍用字符估算）。
- 不改变 `compact` 工具的对外行为。

## 4. 设计

### 4.1 数据模型

```
RawLog（只追加）
  - messages: list[dict]          内存中的原始消息，永不修改
  - path: .transcripts/session_<id>.jsonl   每追加一条立即写一行

CompactState
  - boundary: int                  原始历史中"已被总结覆盖"的截止下标
  - summary: dict | None           最近一次总结生成的 user 消息
  - persisted: dict[tool_use_id, str]   tool_result_budget 的替换结果（保证跨轮稳定）
```

API 视图每轮重新构建，**不持久化**：

```
view = [summary?] + raw[boundary:]
     → apply persisted 替换 / tool_result_budget
     → snip_compact
     → micro_compact
```

所有变换对**拷贝**操作（构造新的 message / block dict），不修改 `raw`。

### 4.2 `prepare()` 新流程

```python
def prepare(self, raw, state, active_request) -> list:
    view = self.build_view(raw, state)          # 拷贝
    view = self.tool_result_budget(view, state) # 新的大结果落盘，记入 state.persisted
    view = self.snip_compact(view)
    view = self.micro_compact(view)
    if self.estimate_chars(view) > self.CONTEXT_CHAR_LIMIT:   # 用视图大小判断：它决定请求体积
        self.compact_history(raw, state, active_request)       # 用原始历史总结
        view = self.build_view(raw, state)
    return view
```

### 4.3 `compact_history`（原始历史为输入）

- 总结输入 = 上一次的 `state.summary`（若有）+ `raw[state.boundary:]` 的**原文**。
- 仍经过 `summary_input` 做长度保护（头 1/4 + 尾 3/4）。
- 完成后：`state.summary = 新总结消息`，`state.boundary = len(raw)`。
- summary 消息中的 transcript 字段指向 `RawLog.path`，并注明覆盖的下标区间
  `[prev_boundary, boundary)`，不再单独写一份文件。

### 4.4 `reactive_compact`

- 与 4.3 相同，但 `boundary` 设为 `len(raw) - KEEP_RECENT_MESSAGES`，
  并按现有规则调整切口，保证 `tool_use` / `tool_result` 成对。
- 最近 5 条原文留在视图中。

### 4.5 `snip_compact`

- 不再写 transcript；marker 改为
  `[N messages omitted; raw log <path> lines a-b]`。
- 修正触发条件：裁剪后总长度（含 marker）≤ `max_messages`，消除 P3。

### 4.6 `micro_compact`

- 对视图拷贝替换旧结果；占位符补充原文位置：
  `[Earlier tool result omitted; raw log <path> line n]`。
  模型如需原文可用 `read_file` 读取 raw log（或后续加专门工具，见待定问题）。

### 4.7 `agent_loop`

```python
raw_log.append(user_msg)
while True:
    view = COMPACTOR.prepare(raw_log.messages, state, active_request)
    response = client.messages.create(..., messages=view)
    raw_log.append({"role": "assistant", "content": response.content})
    ...
    raw_log.append({"role": "user", "content": results})
```

- `history` 变量替换为 `raw_log`；不再出现 `messages[:] = ...` 的回写。
- `compact` 工具：本批工具结果追加进 raw 之后调用 `compact_history`。

### 4.8 P4 处理

- 识别条件扩展为：`BadRequestError` 且文本包含
  `prompt_too_long` / `too many tokens` / `prompt is too long` / `input is too long`
  之一（大小写不敏感）。
- 实现前先用 Bedrock 实际构造一次超长请求，记录真实错误文案，再确定匹配串。

## 5. 不变量

1. `raw` 中任何已追加的消息及其 block 永不被修改。
2. 视图中 `tool_use` 与 `tool_result` 始终成对。
3. 每次总结后，`active_request` 原文出现在视图首条消息中。
4. 任意被省略的内容都能在 raw log 或 `.task_outputs/tool-results/` 中找到原文。

## 6. 测试

保留并适配：`tests/test_compaction_tool_pairs.py` 现有的成对性断言。

新增：
- 执行多轮 `prepare` 后，`raw` 与追加时的深拷贝完全相等（验证不变量 1）。
- 触发 `compact_history` 时，传给 `summarize_history` 的输入包含早已被
  `micro_compact` 省略的工具结果原文（P1/P2 回归）。
- 消息数 > 50 时连续多轮 `prepare`，`.transcripts/` 下文件数不随轮数增长（P3 回归）。
- reactive 路径：最近 5 条原文保留，切口不拆 tool 对。
- 连续两次 compact：第二次总结输入包含第一次的 summary + 之后的原文。
- 用 fake client 抛出各种超长文案，验证 reactive 识别（P4）。

改完需要重新生成网页数据：`cd web && npx tsx scripts/extract-content.ts`。

## 7. 取舍与待定问题

- **内存**：raw 常驻内存且包含全部原文（含 >30000 字符的结果）。教学场景可接受；
  如需优化，可让 raw 内存中只保留落盘引用，原文只在 jsonl 中。
- **总结输入过长**：raw 段可能远超 `SUMMARY_INPUT_CHAR_LIMIT`，头尾截断会丢中段。
  备选：对超限部分先用 micro_compact 后的版本，或分段总结再合并。
- **是否提供读取 raw log 的专门工具**（按下标取消息），而不是让模型 `read_file` 整个 jsonl。
- **对课程叙述的影响**：README 中"每层压缩"的图示与描述需同步更新（原地修改 → 视图变换）。
