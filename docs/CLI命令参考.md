# ExamManager CLI 命令参考

> 唯一事实源：`grade_analyzer/cli.py` 的 `build_parser()`。本文档所有命令与参数已与该定义对拍，并由 `scripts/check_cli_docs.py` 持续校验，防止漂移。

## 1. 入口与通用约定

```bash
python -m grade_analyzer.cli <命令> [子命令] [参数...]
```

程序名：`grade-analyzer`。命令行根参数只有 `-h/--help`；除 `exam update/remove` 的位置参数外，**所有命令都支持全局参数 `--config`**：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径（全局配置） |

### 退出码

- `check`：有 FAIL 的场次时返回 `1`，否则返回 `0`；
- 其余命令正常完成返回 `0`；遇到错误抛出异常并显示回溯（未捕获时进程退出码非 0）。

### 参数约定（重要）

- **`--exam`**：值全由数字/逗号/空格组成时按**序号列表**解析（1-n 按日期升序，0=第一场，负数=倒数第 |k| 场）；否则按**考试名称**（单场）解析。
- **`--class`**：班级用数字（年级取默认年级，如 `10` → `高一10班`），支持逗号分隔与 `n-m` 连续区间（含两端；`14-12` 为反向区间 14,13,12）。
- 所有日期格式为 `YYYY-MM-DD`；所有输出编码 UTF-8（CSV 为 `utf-8-sig`，Excel 可直接打开）。

## 2. 命令总览

| 命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `check` | 识别并校验考试配置，不运行分析 | `--force` `--exam` |
| `parse` | 原始文件 → 规范表（可复用缓存） | `--reparse` |
| `merge` | 跨场合并输出长表/宽表（≥2 场落盘） | `--semester` `--types` `--subject` `--baseline-exams` |
| `run` | 完整分析流程（parse+合并+统计+汇总+成绩单+图表+报告+质量） | `--semester` `--types` `--baseline-exams` `--exam` `--reparse` `--verify-roster` |
| `exam` | 考试条目管理（add/update/remove/list） | 见第 3.5 节 |
| `config` | 全局配置管理（get/set） | 见第 3.6 节 |
| `roster` | 名单清洗与核对（normalize/check） | 见第 3.7 节 |
| `results` | 只生成班级成绩汇总与个人成绩单 | `--semester` `--exam` `--no-merge-strips` `--summary-only` `--strips-only` |
| `charts` | 只生成统计图（需先 parse） | `--semester` `--exam` `--class` `--per-class` |
| `task` | 运行插件注册的批处理任务 | `--list` `--plugin-config` `--input-dir` `--output-dir` `--baseline` |

### 命令依赖顺序

```text
模板初始化 → exam add → check → parse → {run | results | charts | merge}
```

`results`/`charts`/`merge`/`roster check` 硬依赖 `parse`（规范表未就绪时提示"请先运行 parse"并正常结束）。

## 3. 逐命令参考

### 3.1 `check` — 校验考试配置

```bash
python -m grade_analyzer.cli check [--config 路径] [--force] [--exam 名称或序号]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--force` | 开关 | 关 | 忽略已检查标记，强制重新检查所有考试 |
| `--exam` | 文本 | 全部 | 考试名称或序号列表（如 `1,3`）；缺省=全部 |

- 检查项：文件存在、格式识别、名称提取、科目、班级样例、满分来源、元数据覆盖（教师/班级配置差异）；
- 首次检查后写入已检查标记（`quality/checked/<考试名>.yaml`，含原始文件 mtime）；再次检查且原始文件未变时跳过详细打印，只显示一行概要；
- 报告落盘 `quality/check_<考试名>.csv` 与 `quality/check_汇总.csv`；
- 汇总显示 `X 场检查（Y 场跳过）, Z 场有问题`，有 FAIL 返回退出码 1。

### 3.2 `parse` — 解析规范表

```bash
python -m grade_analyzer.cli parse [--config 路径] [--reparse]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--reparse` | 开关 | 关 | 忽略缓存，强制重新解析全部考试 |

- 规范表落盘 `data/parsed/<学期>/<考试名>/{score_summary,question_detail}.csv`；
- 缓存复用条件：规范表存在、原始文件 mtime 未变、考试条目配置签名（`.config_sig`）与班级/学科配置签名（`.meta_sig`）未变；
- 考试已删除（缓存目录有 `.deleted` 标记）的场次跳过。

### 3.3 `merge` — 跨场合并

```bash
python -m grade_analyzer.cli merge [--config 路径] [--semester 学期] [--types 类型] [--subject 科目] [--baseline-exams 场次]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--semester` | 文本 | 当前学期 | 限定学期（缺省=全局 `current_semester`） |
| `--types` | 文本 | 无 | 考试类型，逗号分隔，如 `默认,模考` |
| `--subject` | 文本 | 无 | 限定科目 |
| `--baseline-exams` | 文本 | 无 | 额外加入的历史场次名称（比较基准），逗号分隔 |

- ≥2 场时落盘 `merged_long_<日期范围>.csv` 与 `merged_wide_<日期范围>.csv`；单场跳过落盘；
- 输出提示：`[完成] 合并 N 场考试，M 名学生`。

### 3.4 `run` — 完整分析流程

```bash
python -m grade_analyzer.cli run [--config 路径] [--semester 学期] [--types 类型] [--baseline-exams 场次] [--exam 名称或序号] [--reparse] [--verify-roster]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--semester` | 文本 | 当前学期 | 限定学期 |
| `--types` | 文本 | 无 | 考试类型筛选，逗号分隔 |
| `--baseline-exams` | 文本 | 无 | 额外加入的历史场次名称（比较基准） |
| `--exam` | 文本 | 按 `current_exam`/全部 | 考试名称或序号列表；不传时打印带序号的考试列表 |
| `--reparse` | 开关 | 关 | 忽略缓存强制重新解析 |
| `--verify-roster` | 开关 | 关 | 生成班级汇总时核对学生名单 |

执行阶段：解析/复用 → 合并 → 每场统计工作簿 → 每场班级汇总 → 每场统计图 → 个人成绩单（多场合并）→ 跨场报告 → 数据质量 → run-info。

### 3.5 `exam` — 考试条目管理

#### `exam add` — 新增考试条目

```bash
python -m grade_analyzer.cli exam add [--config 路径] [--folder 文件夹] [--file 文件名] [--name 名称] [--format 格式] [--type 类型] [--importance 重要度] [--semester 学期] [--date 日期] [--subject 科目] [--full-score 数值] [--objective-full-score 数值] [--subjective-full-score 数值] [--objective-question-count 数值] [--default-grade 年级] [--sheet 表名] [--short-name 简称] [--question-display split|merged] [--show-big-questions] [--filter-by-selection] [--question-types 文本]
```

未传 `--file` 时进入**交互式问答**（必填项优先，其余按模板顺序，回车用默认值）；传 `--file` 时走参数式分支（`--semester`/`--subject` 必填或可从文件名推测）。

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--folder` | 文本 | 全局 `input_dir` | 成绩文件所在文件夹（留空=取全局 input_dir；缺省=交互式问答） |
| `--file` | 文本 | 交互式问答 | 成绩文件名（必填） |
| `--name` | 文本 | 从文件名提取 | 考试名称（留空=自动提取） |
| `--format` | 文本 | 自动识别 | 数据格式（weekly/joint/export 或插件格式） |
| `--type` | 文本 | `默认` | 考试类型：默认/学考/模考… |
| `--importance` | 枚举 | 由格式推导 | `平时` / `联考` |
| `--semester` | 文本 | 交互式问答 | 学期全称（必填） |
| `--date` | 日期 | 运行当日 | 考试日期 YYYY-MM-DD |
| `--subject` | 文本 | 从文件名推测 | 科目（必填） |
| `--full-score` | 浮点 | 科目默认 | 总分满分 |
| `--objective-full-score` | 浮点 | 科目默认 | 客观题满分 |
| `--subjective-full-score` | 浮点 | 科目默认 | 主观题满分 |
| `--objective-question-count` | 整数 | 自动判定 | 客观题数（题号大于该数均为主观题） |
| `--default-grade` | 文本 | 全局默认年级 | 默认年级 |
| `--sheet` | 文本 | 自动选择 | 原始文件 sheet 名 |
| `--short-name` | 文本 | 考试全称 | 考试简称（个人成绩单内使用） |
| `--question-display` | 枚举 | `split` | `split`=小题分列 / `merged`=按大题合并 |
| `--show-big-questions` | 开关 | 关 | 是否额外显示主观大题汇总列 |
| `--filter-by-selection` | 开关 | 开（默认 true） | 名单核对是否按七选三过滤 |
| `--question-types` | 文本 | 无 | 题型配置：`题型名,数量或题号列表;...`（如 `客观题,20;单选,1-10;多选,11-20;主观题,21-25`） |

示例：

```bash
python -m grade_analyzer.cli exam add --file 英语测试.xlsx --name 英语测试 --subject 外语 --semester 高一第二学期 --question-types "听力，5；阅读，6-15；作文题，16,"
```

写入 `config/exams/<学期>/<文件名>.yaml`（原子写入 + 全量校验，失败自动回滚）；重名冲突报错。

#### `exam update` — 修改考试条目

```bash
python -m grade_analyzer.cli exam update <考试名称> [--config 路径] [--folder ...] [--file ...] [--format ...] [--type ...] [--importance 平时|联考] [--semester 学期] [--date ...] [--subject ...] [--full-score ...] [--objective-full-score ...] [--subjective-full-score ...] [--default-grade ...] [--sheet ...]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `name`（位置参数） | 文本 | 必填 | 考试名称 |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--folder` / `--file` / `--format` / `--type` / `--importance` / `--date` / `--subject` / `--full-score` / `--objective-full-score` / `--subjective-full-score` / `--default-grade` / `--sheet` | 对应类型 | 不变 | 修改对应字段 |
| `--semester` | 文本 | 不变 | 变更时自动移动条目文件到新学期目录并重算规范名称 |

#### `exam remove` — 删除考试条目

```bash
python -m grade_analyzer.cli exam remove <考试名称> [--config 路径]
```

删除条目文件，**保留规范表缓存**并写入删除标记（`.deleted`）。

#### `exam list` — 列出考试条目

```bash
python -m grade_analyzer.cli exam list [--config 路径] [--semester 学期] [--checkable] [--results-ready]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--semester` | 文本 | 当前学期 | 限定学期（缺省=当前学期，与 run/results 序号口径一致） |
| `--checkable` | 开关 | 关 | 只列出可执行 check 的场次（原始文件存在） |
| `--results-ready` | 开关 | 关 | 只列出可生成成绩单的场次（规范表有效） |

输出列：序号（按日期升序）、考试名称、学期、考试类型、格式、科目、日期、满分、检查（可检查/文件缺失）、成绩单（已解析/已过期/未解析）、删除标记。

### 3.6 `config` — 全局配置管理

```bash
python -m grade_analyzer.cli config get [--config 路径] [key]
python -m grade_analyzer.cli config set [--config 路径] <key> [value]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `key` | 文本 | get 时省略=全部 | 配置键（白名单内） |
| `value` | 文本 | set 时省略=恢复默认 | 配置值；省略时恢复该键默认值 |

**可修改白名单（8 个键）**：

| 键 | 类型 | 范围 | 默认值 |
| --- | --- | --- | --- |
| `pass_ratio` | number | 0~1 | 0.6 |
| `excellent_ratio` | number | 0~1 | 0.85 |
| `default_full_score` | number | 1~1000 | 100 |
| `default_grade` | text | - | 高一 |
| `current_semester` | text | - | 高一第二学期 |
| `current_exam` | integer | 整数列表（空=全部） | 空 |
| `parsed_dir` | text | - | data/parsed |
| `parsed_format` | text | - | csv |

- `set` 先校验（白名单+类型+范围）再按行文本替换（**保留注释**）→ 临时文件整体校验 → 原子替换；
- `current_exam` 空值写为 `''`（表示处理全部）。

### 3.7 `roster` — 名单清洗与核对

```bash
python -m grade_analyzer.cli roster normalize [--config 路径] [--semester 学期]
python -m grade_analyzer.cli roster check [--config 路径] [--semester 学期] [--exam 考试名称]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--semester` | 文本 | 当前学期 | 学期（normalize 未指定且无 current_semester 时报错） |
| `--exam`（仅 check） | 文本 | 全部 | 考试名称（缺省=全部） |

- `normalize`：读取 `data/roster/<学期>.xlsx` → 清洗 → 写 `<学期>_normalized.xlsx`，打印 `规范化 N 名学生，异常 M 条`；
- `check`：逐场核对名单 vs 有成绩学生，输出差异清单 `quality/名单核对_<考试名>.csv`，并按七选三过滤（考试配置 `filter_by_selection`）。

### 3.8 `results` — 生成成绩单

```bash
python -m grade_analyzer.cli results [--config 路径] [--semester 学期] [--exam 名称或序号] [--no-merge-strips] [--summary-only | --strips-only]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--semester` | 文本 | 当前学期 | 限定学期 |
| `--exam` | 文本 | 按 `current_exam`/全部 | 考试名称或序号列表 |
| `--no-merge-strips` | 开关 | 关 | 多场考试时个人成绩单不合并，每场单独生成（缺省=合并） |
| `--summary-only` | 开关 | 关 | 只生成班级成绩汇总，不生成个人成绩单 |
| `--strips-only` | 开关 | 关 | 只生成个人成绩单，不生成班级成绩汇总（与 `--summary-only` 互斥） |

只读规范表，运行前必须先 `parse`。

### 3.9 `charts` — 生成统计图

```bash
python -m grade_analyzer.cli charts [--config 路径] [--semester 学期] [--exam 名称或序号] [--class 班级列表] [--per-class]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--semester` | 文本 | 当前学期 | 限定学期 |
| `--exam` | 文本 | 按 `current_exam`/全部 | 考试名称或序号列表 |
| `--class` | 文本 | 无 | 指定班级数字列表（如 `10,11`、`10-12`、`14-12`），按班级×考试绘制；缺省按配置分组（层次/教师） |
| `--per-class` | 开关 | 关 | `--class` 给出多个班级时每个班级单独一张图 |

示例：

```bash
python -m grade_analyzer.cli charts --exam 1,3 --class 10,11
```

### 3.10 `task` — 插件批处理任务

```bash
python -m grade_analyzer.cli task [--config 路径] [--list] [name] [--plugin-config 路径] [--input-dir 路径] [--output-dir 路径] [--baseline 值]
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--config` | 路径 | `config/config.yaml` | 配置文件路径 |
| `--list` | 开关 | 关 | 列出已注册任务（名称/插件/描述） |
| `name`（位置参数） | 文本 | 省略=列出 | 任务名称；省略或 `--list` 时列出已注册任务 |
| `--plugin-config` | 路径 | 任务自行解析 | 插件配置文件路径（如 objective_analyze 的 config.yaml） |
| `--input-dir` | 路径 | 插件配置 | 任务输入目录（优先于插件配置） |
| `--output-dir` | 路径 | 插件配置 | 任务输出目录（覆盖插件配置默认输出位置） |
| `--baseline`（别名 `--bl`） | 文本 | `全部班级` | 基线（`全部班级` 或分组名：教师名/层次/未分层） |

内置任务 `objective_analyze` 示例：

```bash
python -m grade_analyzer.cli task objective_analyze --input-dir "G:\...\限时练三(地理)客观题得分明细" --baseline 全部班级
```

## 4. 独立脚本

### 4.1 `template_tools.py`

```bash
python template_tools.py generate --type all|global|charts|results|exams|classes|subjects
python template_tools.py scan --mode existence|diff [--type 类型[,类型...]] [--prompt]
```

| 命令 | 参数 | 默认 | 说明 |
| --- | --- | --- | --- |
| `generate` | `--type` | `all` | 模板类型：all/global/charts/results/exams/classes/subjects；相关配置文件缺失时一并生成 |
| `scan` | `--mode` | `existence` | `existence`=缺失才生成；`diff`=与内置默认值不同则重新生成 |
| `scan` | `--type` | 全部 | 模板类型（逗号分隔） |
| `scan` | `--prompt` | 关 | 只提示，不自动生成 |

注意：`config.yaml` 等实际配置文件已存在时不会被覆盖；无参 `generate` 会重写全部模板，慎用。

### 4.2 `sync_templates.py`

```bash
python sync_templates.py
```

把 `config/charts/config.yaml` 与 `config/results/config.yaml` 同步到对应 `_template.yaml`（考试/班级/学科模板为说明性示例，不参与同步）。

## 5. 参数约定详解

### 5.1 场次序号规则（`--exam`、`current_exam`）

- `1-n`：按日期升序的场次序号（与 `exam list` 一致）；
- `exam list` 未指定 `--semester` 时默认仅列出当前学期（`current_semester`）；
- `0`：第一场；负数：倒数第 |k| 场；
- 正数过大取最后一场，负数绝对值过大取第一场；
- 逗号分隔可多选，如 `1,3`；`current_exam` 留空=处理全部。

### 5.2 `--question-types` 文本格式

`题型名,数量或题号列表;题型名,数量或题号列表;...`，全半角标点兼容（`，；－　：` 自动转半角）：

- 数量式：纯数字，按顺序从 1 起连续分配，只能出现在前面若干行；
- 列表式：逗号/短横线，如 `1,2,3-5`，`"5,"` 表示题号 5；列表式后不允许再出现数量式；
- 子题型：范围完全包含时生效（如 单选 1-10 属于 客观题 1-20）；部分重叠报错。

### 5.3 班级区间语法（`--class`）

- `10,11` → 高一10班、高一11班；
- `10-12` → 10,11,12（含两端）；
- `14-12` → 14,13,12（反向区间）；
- 班级号两位对齐（`高一10班`）。

### 5.4 考试类型与基线

- `--types`：按考试条目 `type` 字段筛选（默认/学考/模考…），逗号分隔；
- `--baseline-exams`：把额外场次加入合并范围作比较基准（名称精确匹配，未找到时打印警告）。

## 6. 常见问题排查

| 报错/现象 | 原因 | 修复 |
| --- | --- | --- |
| `配置文件不存在: config/config.yaml` | 未初始化配置 | 运行 `python template_tools.py scan --mode existence` |
| `考试名称无法解析，请先运行 check` | 条目 `name` 留空且文件名无法提取 | 检查文件命名（`--...】`）或填写 `name` |
| `科目无法推测，请先运行 check` | `subject` 留空且文件名不匹配词表 | 填写 `subject` 或在 `subjects`/`subject_aliases` 中补充词表 |
| `规范表未就绪，请先运行 parse` | 未解析或缓存过期 | 先 `parse`（配置/文件变更后需重新 `parse` 或 `parse --reparse`） |
| `考试名称重复: xxx` | 重名冲突 | `exam list` 查看并 `exam update/remove` |
| `教师代号应为 [A, B, C]` | 学科配置代号不连续 | 修正 `teacher_names` 代号从 A 起连续 |
| `总分越界（满分 100）` | 原始数据总分异常 | 检查原始文件；确认 `full_score` 配置 |
| `题型配置未覆盖题号 [..]` | `binary_split=false` 下配置未覆盖全部题号 | 补全 `question_types` 或开启 `binary_split` |
| `文件可能被占用`（写入失败提示） | Excel 文件被打开 | 关闭占用程序后重试 |
