# exam-manager 学生成绩单处理与分析

用于处理、分析学生成绩单的 Python 工具：从不同格式的原始成绩表解析出规范表，完成清洗、排位、统计、班级汇总、个人成绩单、统计图与跨场合并分析，并以 Excel / CSV / PNG 形式输出。

## 功能概览

- **多格式解析**：支持周测（格式 A，含小题得分）、联考（格式 B）两类原始表，自动识别或手动指定格式；
- **清洗与排位**：考号/总分校验、班级名称规范化、学校过滤、班次/校次真实排位、客观题单选/多选区分；
- **统计报告**：单场统计工作簿（科目统计、分数段分布、个人排名、班级对比、教师对比，多 sheet + 内嵌图表）；
- **班级汇总**：按任课教师分文件、按班级分 sheet，含页眉页脚、条件格式；
- **个人成绩单**：按教师/全部班级/自定义范围生成，小题分列或按大题合并，样式可配置；
- **统计图**：按班级层次/任课教师分组的组合图（半提琴图 + 中位数/平均分/上下四分位折线）；
- **跨场分析**：合并规范表为长表/宽表，支持多学期、按考试类型筛选、基线场次对比；
- **名单核对**：名单清洗（考号/班级规范化）与考试按七选三过滤核对；
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
```

依赖：pandas、numpy、openpyxl、lxml、PyYAML、matplotlib、seaborn、pytest。

## 配置说明

### 全局配置 `config/config.yaml`

重点确认以下几项：

- `default_school`：原始表无"学校"列时填充的默认学校；
- `current_semester`：run / merge / results 默认处理的学期；
- `default_grade`：成绩文件无年级时的默认年级；
- `subjects` / `subject_aliases` / `subject_defaults`：科目词表、别名（如 英语→外语）与满分默认值；
- 各类目录：`exams_dir`、`parsed_dir`、`roster_dir`、`results_dir`、`output` 等。

### 考试条目 `config/exams/<学期>/<考试名>.yaml`

一场考试一个 yaml，复制 `config/exams/_template.yaml` 新建。常用字段：

| 字段 | 说明 |
| --- | --- |
| `name` | 考试名称，**必填**（check 校验，为空不通过） |
| `format` | `weekly` / `joint`，留空自动识别 |
| `type` | 考试类型（默认/学考/模考…），联合分析筛选用 |
| `semester` | 学期全称，省略时取子文件夹名；显式声明优先 |
| `date` | 考试日期 YYYY-MM-DD，留空取程序运行当日 |
| `folder` / `file` | 原始成绩文件所在文件夹与文件名 |
| `subject` | 科目，留空从文件名推测 |
| `full_score` 等 | 总分/客观/主观满分，留空用科目默认值 |
| `short_name` | 考试简称，**必填**（个人成绩单内使用） |
| `question_display` | `split`=小题分列 / `merged`=按大题合并 |
| `show_big_questions` | 是否额外显示主观大题汇总列 |

### 班级与学科配置

- `config/classes/<学期>.yaml`：班级 -> `level`（A/B）+ `course`（选科，自由文本）；
- `config/subjects/<学期>_<科目>.yaml`：教师数量、代号（A 起连续大写字母）-> 教师名、班级 -> 代号。成绩比较按层次/科任教师分组。

### 图表与成绩单配置

- `config/charts/config.yaml`：统计图分组、指标、颜色、字体、坐标轴等；
- `config/results/config.yaml`：个人成绩单范围/样式、班级汇总页眉页脚/字体/边框等。

## 使用流程

### 1. 数据准备

把原始成绩文件放入 `data/input/`（参考 `data/input/测试样例/` 的周测、联考两种格式）；名单（可选）放入 `data/roster/<学期>.xlsx`。

### 2. 录入考试条目

手动在 `config/exams/<学期>/` 下新建 yaml（模板见上节）。

### 3. 校验

```bash
python -m grade_analyzer.cli exam list               # 查看各场考试 check / results 可用状态
python -m grade_analyzer.cli exam list --checkable   # 只看可 check 的场次
python -m grade_analyzer.cli exam list --results-ready  # 只看可生成成绩单的场次
python -m grade_analyzer.cli check                   # 校验名称/文件/满分等，FAIL 需修复
```

### 4. 解析与运行

```bash
python -m grade_analyzer.cli parse                   # 原始文件 -> 规范表（data/parsed/）
python -m grade_analyzer.cli run                     # 完整流程：统计/汇总/成绩单/图表/报告/质量
python -m grade_analyzer.cli run --exam <考试名称>    # 只处理指定考试
python -m grade_analyzer.cli results --exam <考试名称> # 只生成班级汇总与个人成绩单
```

### 5. 跨场合并与名单核对（可选）

```bash
python -m grade_analyzer.cli merge [--semester ...] [--types ...] [--baseline-exams ...]
python -m grade_analyzer.cli roster normalize [--semester ...]
python -m grade_analyzer.cli roster check [--semester ...] [--exam ...]
```

## 输出位置

```text
data/output/
├─ merged/        # 合并长表/宽表
├─ reports/       # 跨场 Excel 汇总报告
├─ statistics/    # 单场统计工作簿（按学期，一场一个 xlsx）
├─ charts/        # 统计图 PNG
├─ quality/       # check 报告、数据质量、名单核对
├─ run-info/      # 每次 run 的配置快照/考试列表/日志（含 latest）
└─ results/       # 成绩单输出
   └─ <学期>/
      ├─ <考试>/<考试>_<教师>_班级成绩汇总.xlsx
      └─ <yyyymmdd>_<考试>_<标签>_个人成绩单.xlsx
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
- `exam add / update / remove` 目前为占位未实现，新增考试请手动复制模板 yaml。
