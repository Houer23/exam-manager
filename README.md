# exam-manager 学生成绩单处理与分析

用于处理、分析学生成绩单的 Python 工具：从不同格式的原始成绩表解析出规范表，完成清洗、排位、统计、班级汇总、个人成绩单、统计图与跨场合并分析，并以 Excel / CSV / PNG 形式输出。

## 功能概览

- **多格式解析**：支持周测（格式 A，含小题得分）、联考（格式 B）两类原始表，自动识别或手动指定格式；
- **清洗与排位**：考号/总分校验、班级名称规范化、学校过滤、班次/校次真实排位、客观题单选/多选区分；
- **统计报告**：单场统计工作簿（科目统计、分数段分布、个人排名、班级对比、教师对比，多 sheet + 内嵌图表）；
- **班级汇总**：按任课教师分文件、按班级分 sheet，含页眉页脚、条件格式；
- **个人成绩单**：按教师/全部班级/自定义范围生成，小题分列或按大题合并；多场合并为一份（每生一个表头、每场一行），自动分页保证表头与数据同页，样式可配置；
- **统计图**：按班级层次/任课教师分组的组合图（半提琴图 + 中位数/平均分/上下四分位折线），支持按 班级×考试 绘制（`--class` / `--per-class`）；
- **考试条目管理**：`exam add / update / remove / list` 维护考试配置（交互式录入、重名冲突检测、删除标记），`config get/set` 管理全局配置；
- **跨场分析**：合并规范表为长表/宽表，支持多学期、按考试类型筛选、基线场次对比；
- **名单核对**：名单清洗（考号/班级规范化）与考试按七选三过滤核对；
- **题型配置**：考试条目可配置题型（数量式/题号列表式、范围包含为子题型、二分配置 `binary_split`），单选/多选可按配置或按最大得分差异自动区分，分项列（听力分/作文分等）动态生成；
- **插件系统**：从 `plugins/` 目录加载格式适配器、生命周期钩子与批处理任务（`task` 子命令），内置 `objective_analyze` 客观题得分分析插件；
- **可配置化**：全局、图表、成绩单配置独立成文件，模板可生成与同步。

## 目录结构

```text
exam-manager/
├─ grade_analyzer/        # 核心代码
│  ├─ adapters/           # 原始表解析适配器（weekly / joint）
│  ├─ cli.py              # 命令行入口
│  ├─ pipeline.py         # 流程编排（parse / run / results）
│  ├─ checker.py          # check 校验
│  ├─ config.py           # 全局配置与考试条目加载
│  ├─ config_ops.py       # exam list / config get-set 等
│  ├─ question_types.py   # 题型配置解析与方案（数量/列表、子题型、二分配置）
│  ├─ report.py           # 统计与班级汇总
│  ├─ personal_strip.py   # 个人成绩单
│  ├─ dist_charts.py      # 统计图
│  ├─ roster.py           # 名单清洗与核对
│  └─ ...                 # 清洗、存储、合并、质量、run-info 等
├─ config/                # 全部配置文件（已入库）
│  ├─ config.yaml         # 全局配置
│  ├─ exams/              # 考试条目（按学期子目录）
│  ├─ classes/            # 班级配置（学情层次/选科）
│  ├─ subjects/           # 学科配置（任课教师）
│  ├─ charts/             # 统计图配置
│  └─ results/            # 成绩单配置
├─ data/
│  ├─ input/              # 原始成绩文件（不入库）
│  ├─ parsed/             # 规范表缓存（不入库）
│  ├─ roster/             # 学生名单（不入库）
│  └─ output/             # 全部输出（不入库）
├─ plugins/                # 插件目录（内置 objective_analyze：客观题得分分析）
├─ tests/                 # pytest 测试
├─ requirements.txt
├─ template_tools.py      # 模板/配置生成与扫描
├─ sync_templates.py      # 实际配置同步到模板
└─ README.md
```

## 环境要求与安装

需要 Python 3.10+。首次使用（全新环境）：

```bash
git clone https://github.com/Houer23/exam-manager.git   # 私有仓库，先完成 gh auth login
cd exam-manager
python -m venv .venv
.venv\Scripts\activate        # Windows；macOS/Linux 用 source .venv/bin/activate
pip install -r requirements.txt
python template_tools.py scan --mode existence   # 初始化配置：生成缺失的 config/config.yaml 等（已存在不覆盖）
```

依赖：pandas、numpy、openpyxl、lxml、PyYAML、matplotlib、seaborn、pytest、xlrd。

克隆后 `config/` 下仅保留模板（`_template.yaml`）与内置默认值，**实际配置不入库**。
首次使用请先运行上面的模板工具初始化命令，再按需修改 `config/config.yaml`
（如 `default_school`、各目录路径），并用 `python -m grade_analyzer.cli check` 校验后开始使用。

## 配置说明

### 全局配置 `config/config.yaml`

重点确认以下几项：

- `default_school`：原始表无"学校"列时填充的默认学校；
- `current_semester`：run / merge / results 默认处理的学期；
- `current_exam`：场次序号列表（整数，逗号分隔，按日期升序编号：0=第一场，负数=倒数）；留空处理全部，`--exam` 名称或序号列表优先；
- `default_grade`：成绩文件无年级时的默认年级；
- `input_dir`：默认成绩单输入目录（考试配置 `folder` 留空时使用）；
- `subjects` / `subject_aliases` / `subject_defaults`：科目词表、别名（如 英语→外语）与满分默认值；
- 各类目录：`exams_dir`、`parsed_dir`、`roster_dir`、`results_dir`、`output` 等。

### 考试条目 `config/exams/<学期>/<考试名>.yaml`

一场考试一个 yaml，复制 `config/exams/_template.yaml` 新建。规范考试名称 = **学期简写 + 科目 + 考试名**（已含学期/科目或其别名时不重复添加）。常用字段（按模板顺序）：

| 字段 | 说明 |
| --- | --- |
| `subject` | 科目，**必填**（check 校验，留空不通过） |
| `semester` | 学期全称，省略时取子文件夹名；显式声明优先 |
| `date` | 考试日期 YYYY-MM-DD，留空取程序运行当日 |
| `folder` / `file` | 原始成绩文件所在文件夹与文件名；`folder` 可省略，留空取全局 `input_dir` |
| `name` | 考试名称，可省略；留空从文件名自动提取，提取失败 check 不通过 |
| `short_name` | 考试简称，可省略；留空使用考试全称 |
| `question_display` | `split`=小题分列 / `merged`=按大题合并 |
| `show_big_questions` | 是否额外显示主观大题汇总列 |
| `format` | `weekly` / `joint`，留空自动识别 |
| `type` | 考试类型（默认/学考/模考…），联合分析筛选用 |
| `full_score` 等 | 总分/客观/主观满分，留空用科目默认值 |
| `objective_question_count` | 客观题数：题号大于该数为主观题；留空=按题号格式自动判定 |
| `question_types` | 题型配置：题型名 -> 数量或题号列表，可动态增删题型；配置非空时以配置为准 |
| `binary_split` | 二分配置（默认 `true`）：顶层题型 ≤2 时按客观题数分客观/主观，配置题型作为子题型；`false` 时完全按配置划分 |
| `filter_by_selection` | 名单核对是否按七选三过滤，默认 `true` |

也可用 `exam add` 交互式录入（参数式或逐项问答，必填项优先、其余按模板顺序，满分等默认值取自全局 `subject_defaults`）。交互录入包含题型配置项，也可用参数 `--question-types` 指定，例如：

```bash
python -m grade_analyzer.cli exam add --file 英语测试.xlsx --name 英语测试 --subject 外语 \
  --semester 高一第二学期 --question-types "听力，5；阅读，6-15；作文题，16,"
```

### 题型配置 `question_types`

题型名可任意增删（如 客观题/主观题/单选/多选/听力/作文题），配置非空时以配置为准，留空回退默认"主观题/客观题 + 单选/多选自动区分"。值为**数量式**或**题号列表式**：

```yaml
question_types:
  听力: 5            # 数量式：1-5 题
  阅读: 10           # 数量式：6-15 题
  客观题: 16-30      # 列表式：16-30 题
  单选: 16-22        # 子题型：范围完全含于 客观题
  多选: 23-30
  主观题: 31-35
```

- 数量式（纯数字）按顺序从 1 起连续分配，允许放在前面若干行；一旦出现列表式，其后不允许再出现数量式；
- 列表式用逗号/短横线（如 `1,2,3-5`），`"5,"` 表示题号 5；
- 范围**完全包含**时为子题型（小范围为子题型，用法同 单选/多选 分项列）；部分重叠报错；
- 顶层题型数 ≤2 且 `binary_split: true` 时，客观/主观范围由 `objective_question_count` 确定，配置题型作为子题型；否则完全按配置划分；
- 每题题型取包含该题号的最深子题型；分项列按题型动态生成（如 `听力分`、`作文分`），成绩单按存在的分项列显示。

### 班级与学科配置

- `config/classes/<学期>.yaml`：班级 -> `level`（A/B）+ `course`（选科，自由文本）；
- `config/subjects/<学期>_<科目>.yaml`：教师数量、代号（A 起连续大写字母）-> 教师名、班级 -> 代号。成绩比较按层次/科任教师分组。

### 图表与成绩单配置

- `config/charts/config.yaml`：统计图分组、指标、颜色、字体、坐标轴（含横轴扩展系数 `xlim_factor`）、半提琴宽度（`violin.width`）等；
- `config/results/config.yaml`：个人成绩单范围/样式、班级汇总页眉页脚/字体/边框等。

### results 分组配置（个人成绩单范围与标签）

`config/results/config.yaml` 的 `personal.scope` 决定个人成绩单包含哪些班级，以及文件名中的标签：

- `mode: all`：全部班级，标签为"全部班级"；
- `mode: teacher`：按教师分组，`teachers` 填字母代号（A/B/C…，自动解析为学科配置中的教师名）或直接填教师名；每个教师生成一个文件，**标签 = 教师名**；
- `mode: custom`：自定义班级，`classes` 填班级规范名列表；标签自动判定——所选班级等于全部班级 → "全部班级"，恰好等于某位教师任教班级 → 教师名，否则 → "自定义"。

示例：

```yaml
personal:
  scope:
    mode: teacher
    teachers: [A]        # 或直接写教师名，如 [柯]
```

相关命令参数：`--summary-only` / `--strips-only` 只生成其中一种；`--no-merge-strips` 关闭多场个人成绩单合并。

### 配置文件修改注意事项

所有配置文件均为 YAML（`yaml.safe_load` 解析），字符值带不带引号会影响类型解析：

- **纯中文/英文单词可不带引号**：`name: 期中联考`、`subject: 地理`、`question_display: split`；
- **必须用双引号的值**：
  - 空字符串：`name: ""`（注意：`name:` 或省略该行等价于空，项目会将空串与 null 统一为"未设置"）；
  - 日期：`date: "2026-04-20"`（不带引号会被解析成日期对象）；
  - 含 `: `、` #` 或 `- ? : [ ] { } , & * ! | > ' " % @` 等特殊字符的值；
  - 形似数字/布尔/null 且本意是字符串的值；
- **不要带引号的值**：数值（`full_score: 100`）、布尔（`filter_by_selection: true`），带引号会被解析成字符串，可能影响校验；
- 修改配置后建议运行 `python -m grade_analyzer.cli check` 确认可正常加载。

## 使用流程

### 1. 数据准备

把原始成绩文件放入 `data/input/`（参考 `data/input/测试样例/` 的周测、联考两种格式）；名单（可选）放入 `data/roster/<学期>.xlsx`。

### 2. 录入考试条目

用 `exam add` 新增（参数式或交互式，交互会逐一提示模板全部配置项），或在 `config/exams/<学期>/` 下手动新建 yaml（模板见上节）。

### 3. 校验

```bash
python -m grade_analyzer.cli exam list               # 查看各场考试 check / results 可用状态
python -m grade_analyzer.cli exam list --checkable   # 只看可 check 的场次
python -m grade_analyzer.cli exam list --results-ready  # 只看可生成成绩单的场次
python -m grade_analyzer.cli check                   # 校验名称/文件/满分等，FAIL 需修复
```

`check` 说明：
- 首次检查后写入**已检查标记**（含原始文件与考试条目配置签名）；再次 check 且原始文件/配置未变时，**跳过该场的信息打印**，只显示一行概要（上次 PASS / FAIL n 项），减少重复输出；
- 原始文件或考试配置变化（如客观题数）会令缓存/标记失效，自动重新完整检查；
- `check --force`：忽略已检查标记，强制重新检查全部；
- `check --exam <考试名称或序号列表>`：单独检查指定场次（如 `check --exam 1,3`，序号与 `exam list` 一致）；
- 汇总显示 `X 场检查（Y 场跳过）, Z 场有问题`。

### 4. 解析与运行

```bash
python -m grade_analyzer.cli parse                   # 原始文件 -> 规范表（data/parsed/）
python -m grade_analyzer.cli run                     # 完整流程：统计/汇总/成绩单/图表/报告/质量
python -m grade_analyzer.cli run --exam <考试名称>    # 只处理指定考试
python -m grade_analyzer.cli run --exam 1,3          # 按日期升序序号选择多场合并分析
python -m grade_analyzer.cli results --exam <考试名称> # 只生成班级汇总与个人成绩单
python -m grade_analyzer.cli results --summary-only   # 只要班级成绩汇总
python -m grade_analyzer.cli results --strips-only    # 只要个人成绩单
python -m grade_analyzer.cli results --no-merge-strips # 多场时个人成绩单不合并
python -m grade_analyzer.cli charts [--exam ...]      # 单独生成统计图（多种用法详见"统计图（charts）"节）
```

`results` 与 `charts` 只读规范表，**运行前必须先 `parse`**（未解析会提示"请先运行 parse"并正常结束）；可用 `exam list --results-ready` 确认哪些场次已就绪。原始成绩文件更新、考试条目配置（如题型/客观题数）或学科/班级配置（任课教师/层次）变化，都会使规范表缓存失效，需重新 `parse`（或 `parse --reparse` 强制重解析）。一句话流程：**放数据 → exam add → check → parse → exam list --results-ready → results / charts**。

多场考试（≥2）时：merged 长表/宽表与成绩分析汇总文件名标注日期范围（如 `merged_long_20260325-20260420.csv`、`成绩分析汇总_20260325-20260420.xlsx`），单场不做 merge 落盘、报告标注该场日期；个人成绩单合并为一份（每生一个表头，每场考试一行，主观题列为各大题得分竖线合并字符串）。

### 5. 跨场合并与名单核对（可选）

```bash
python -m grade_analyzer.cli merge [--semester ...] [--types ...] [--baseline-exams ...]
python -m grade_analyzer.cli roster normalize [--semester ...]
python -m grade_analyzer.cli roster check [--semester ...] [--exam ...]
```

## 统计图（charts）

生成统计图需规范表已就绪（先 `parse`）。输出到 `data/output/charts/<学期>/`，样式由 `config/charts/config.yaml` 控制。

### 单场组合图（默认，不带 --class）

对每场选中的考试，按 `config/charts/config.yaml` 的 `group_by`（默认 `[层次, 教师]`）各生成一张组合图（半提琴图 + Q1/中位数/平均分/Q3 指标折线）：

```bash
python -m grade_analyzer.cli charts                        # 当前学期全部（按 current_exam 或全部）
python -m grade_analyzer.cli charts --semester 高一第二学期  # 指定学期
python -m grade_analyzer.cli charts --exam 高一下地理五月月考  # 指定一场
python -m grade_analyzer.cli charts --exam 1,3             # 按日期升序序号选多场
```

- 文件名：`按<分组>_<日期8位>_<考试名>.png`（如 `按层次_20260528_高一下地理五月月考.png`）；
- 单场图标题左侧显示考试日期（`YYYY年MM月DD日`，与成绩单页眉同格式），主标题右对齐；
- `group_by` 可在 `config/charts/config.yaml` 中配置为 `层次` / `教师` 的组合，`enabled: false` 时跳过生成。

### 班级×考试对比图（--class）

按指定班级在选中考试中的成绩走势绘制对比图（需多场或多班级）：

```bash
python -m grade_analyzer.cli charts --class 10,11             # 多个班级一张图对比
python -m grade_analyzer.cli charts --class 10-12             # 连续区间（含两端）
python -m grade_analyzer.cli charts --class 14-12             # 反向区间（14,13,12）
python -m grade_analyzer.cli charts --class 10,11 --per-class # 每个班级单独一张图
python -m grade_analyzer.cli charts --exam 1,3 --class 10,11  # 与 --exam 组合（多场对比）
```

- 班级用数字（年级取默认年级，如 10 → 高一10班），支持逗号分隔与 `n-m` 区间；
- 不传 `--per-class`：所选班级画在同一张图内对比；`--per-class`：每个班级单独一张图；
- 文件名：`按班级_<日期范围>_<班级标签>.png`。

### 说明

- `charts` 只读规范表，运行前需先 `parse`（未就绪会提示"请先运行 parse"）；
- `run` 完整流程也会按 charts 配置自动生成统计图；
- 单场图与班级×考试图在标题/文件名中均含日期，便于区分场次。

## 插件与批处理任务

程序启动时从 `plugins/` 目录加载插件（清单 `plugin.yaml` + 入口 `plugin.py`），可注册格式适配器、生命周期钩子与批处理任务。插件编写说明见 [plugins/README.md](plugins/README.md)。

### 批处理任务（task）

```bash
python -m grade_analyzer.cli task --list    # 列出已注册任务
python -m grade_analyzer.cli task <任务名> [--plugin-config 路径] [--input-dir 路径] [--output-dir 路径] [--baseline 值]
```

### objective_analyze（客观题得分分析）

读取一个"客观题得分明细"文件夹（各班 `N班.xls` + `全部班级.xls`），生成客观题得分汇总工作簿与得分率距平文件：

```bash
python -m grade_analyzer.cli task objective_analyze --input-dir "G:\...\限时练三(地理)客观题得分明细"
```

- 考试规范名称/学科从文件夹名推导（括号前为考试名、括号内为学科，映射项目 `subjects`/别名）；
- 汇总分组 `summary_groups`：每个分组生成一个工作簿（成员班级 sheet + 全部班级 sheet + 得分率汇总），默认不分组；
- 距平分组 `deviation_groups`：每个分组生成一个距平文件（默认按教师）；
- 基线 `baseline`（别名 `bl`，命令行 `--baseline` 优先级最高）：`全部班级` 或分组名（教师名/层次/未分层）；
- 输出默认 `data/output/task/<考试规范名称>/`；参数与分组/基线配置见 `plugins/objective_analyze/config.yaml`（未指定 `--plugin-config` 时自动读取该文件）。

## 输出位置

```text
data/output/
├─ merged/        # 合并长表/宽表
├─ reports/       # 跨场 Excel 汇总报告
├─ statistics/    # 单场统计工作簿（按学期，一场一个 xlsx）
├─ charts/        # 统计图 PNG（按<分组>_<日期8位>_<考试名>.png、按班级_<日期范围>_<班级标签>.png）
├─ quality/       # check 报告、数据质量、名单核对
├─ run-info/      # 每次 run 的配置快照/考试列表/日志（含 latest）
└─ results/       # 成绩单输出
   └─ <学期>/
      ├─ <考试>/<考试>_<教师>_班级成绩汇总.xlsx
      └─ <yyyymmdd>_<考试>_<标签>_个人成绩单.xlsx
         <日期范围>_<标签>_个人成绩单.xlsx   # 多场合并版
```

## 模板工具

模板与配置的默认值集中在 `template_tools.py` 的 `DEFAULT_*` 常量中，修改后重新生成即可。

```bash
python template_tools.py scan --mode existence      # 只补缺失的模板/配置，不覆盖已有
python template_tools.py scan --mode diff           # 模板与内置默认值不一致时重新生成
python template_tools.py generate --type all        # 全部模板重置（含配置文件缺失时生成）
python sync_templates.py                            # 把实际配置复制到模板
```

注意：`config.yaml` 等实际配置文件已存在时不会被覆盖；无参 `generate` 会重写全部模板，慎用。

## 测试

```bash
python -m pytest tests -q
```

## 数据安全与注意事项

- `data/input/`、`data/parsed/`、`data/roster/`、`data/output/` 均被 `.gitignore` 忽略，原始成绩、名单（含考号/选课）与生成结果不入库；
- `config/` 中可能含真实教师姓名等信息，仓库应保持私有；开源前需脱敏；
- 所有文本文件统一 CRLF 行尾（`.gitattributes` 已强制）；
- `config/` 下实际配置（`config.yaml`、`charts/config.yaml`、`results/config.yaml`、考试条目、班级与学科配置）均不入库，仅模板/默认值入库；新环境需先运行
  `python template_tools.py scan --mode existence` 初始化，再按需修改本地配置；新增考试用 `exam add`。
- 插件为本地 Python 代码，以完全权限执行，只应加载可信来源的插件。
