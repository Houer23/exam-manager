"""题型配置：解析、层级（子题型）与二分配置方案。

考试条目 `question_types` 配置格式：
    question_types:
      客观题: 20        # 第一行可用数量式（1-20 题）
      单选: 1-10        # 子题型：范围完全含于 客观题
      多选: 11-20
      主观题: 21-25

规则：
- 值 = 纯数字（数量式）：允许前面若干行为数量式（按顺序从 1 起连续分配）；
  一旦出现列表式，其后不允许再出现数量式；
- 值 = 逗号/短横线列表（列表式），如 "1,2,3-5"、"20,"（"20," 表示题号 20）；
- 列表项除数字题号外还支持“得分列列名”：
    * 整项无法按题号形式解析时自动视为列名（如 语法填空56-65、应用文）；
    * 需要强制按列名（含纯数字/范围外观，如 "56-65"）时加前缀 @，如 "@56-65"；
- 范围完全包含 -> 小范围为子题型；部分重叠（非完全包含）-> 报错；
- 顶层题型 = 未被其他题型包含者；每题题型 = 包含该题号的最深子题型；
- 列名项归属其所在题型（顶层客观/主观判定按题号层级推导）；
- 内部规范名：客观题 -> 客观，主观题 -> 主观（兼容现有 客观/主观 口径）；
- 二分配置项 binary_split=true 且顶层题型数 <= 2 时：
    客观/主观范围由最大客观题数（objective_question_count）确定，
    配置题型作为客观/主观范围内的子题型（用法同现有 单选/多选）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def _canonical(name: str) -> str:
    """内部规范名：客观题 -> 客观；主观题 -> 主观；其余原样。"""
    if name == "客观题":
        return "客观"
    if name == "主观题":
        return "主观"
    return name


_WIDTH_MAP = str.maketrans(
    {"，": ",", "；": ";", "－": "-", "　": " ", "：": ":"}
)

_QUESTION_COLUMN_MARKER = "@"
_RANGE_RE = re.compile(r"^(\d+)-(\d+)$")
_NUMERIC_SUFFIX_RE = re.compile(r"^(\d+)[\u4e00-\u9fff]+$")


def _normalize_width(text: str) -> str:
    """全角标点转半角（，；－　：），便于解析兼容。"""
    return text.translate(_WIDTH_MAP)


def _split_list_items(text: str) -> list[str]:
    """按逗号切分题型值列表；先做全半角归一化（支持中文全角逗号）。"""
    normalized = _normalize_width(str(text))
    return [p.strip() for p in normalized.split(",") if p.strip()]


def parse_question_types_text(text: str) -> dict[str, int | str] | None:
    """解析交互输入题型文本：'题型名,数量或题号列表;题型名,数量或题号列表'。

    兼容全半角分隔符（，；与 ,;）、多余空格；
    返回 {题型名: 数量(int) 或 题号列表(str)}，空输入返回 None。
    """
    if text is None:
        return None
    text = _normalize_width(str(text)).strip()
    if not text:
        return None
    result: dict[str, int | str] = {}
    seen_list = False
    for segment in text.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        if "," not in segment:
            raise ValueError(
                f"题型项格式应为 题型名,数量或题号列表: {segment!r}"
            )
        name, _, value = segment.partition(",")
        name = name.strip()
        value = re.sub(r"\s+", "", value.strip())
        if not name:
            raise ValueError(f"题型名不能为空: {segment!r}")
        if not value:
            raise ValueError(f"题型 {name}: 数量或题号列表不能为空")
        if re.fullmatch(r"\d+", value):
            if seen_list:
                raise ValueError(
                    f"{name}: 列表式后不允许出现数量式（数量式只能放在前面若干行）"
                )
            result[name] = int(value)
        else:
            seen_list = True
            result[name] = value
    if not result:
        raise ValueError(f"题型配置无法解析: {text!r}")
    return result


def _parse_question_list(text: str) -> list[int] | None:
    """解析题号列表（逗号/短横线）；纯数字（数量式）返回 None。"""
    text = text.strip()
    if not text:
        return None
    if re.fullmatch(r"\d+", text):
        return None  # 数量式
    nums: list[int] = []
    for part in text.rstrip(",").split(","):
        part = part.strip()
        if not part:
            continue
        if re.fullmatch(r"\d+", part):
            nums.append(int(part))
            continue
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if not m:
            raise ValueError(f"题号列表格式错误: {part!r}（应为数字或 a-b）")
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            raise ValueError(f"题号区间应为升序 a<=b: {part!r}")
        nums.extend(range(a, b + 1))
    if not nums:
        raise ValueError(f"题号列表为空: {text!r}")
    return nums


def parse_question_types(value) -> dict[str, list[int | str]]:
    """把 question_types 配置解析为 题型名 -> 数字题号/列名列表。"""
    if not value:
        return {}
    if not isinstance(value, dict):
        raise ValueError("question_types 应为映射（题型名 -> 数量或题号列表）")
    result: dict[str, list[int | str]] = {}
    next_start = 1
    seen_list = False
    for name, raw in value.items():
        name = _canonical(str(name).strip())
        if not name:
            raise ValueError("question_types 存在空题型名")
        text = _normalize_width(str(raw)).strip()
        if not text:
            raise ValueError(f"{name}: 数量或题号列表不能为空")
        if re.fullmatch(r"\d+", text):
            if seen_list:
                raise ValueError(
                    f"{name}: 列表式后不允许出现数量式（数量式只能放在前面若干行）"
                )
            n = int(text)
            if n <= 0:
                raise ValueError(f"{name}: 数量应为正整数，当前为 {n}")
            result[name] = list(range(next_start, next_start + n))
            next_start += n
            continue
        seen_list = True
        items: list[int | str] = []
        for item in _split_list_items(text):
            if item.startswith(_QUESTION_COLUMN_MARKER):
                token = item[len(_QUESTION_COLUMN_MARKER):].strip()
                if not token:
                    raise ValueError(
                        f"{name}: 列名标记 '@' 后不能为空"
                    )
                items.append(token)
                continue
            if re.fullmatch(r"\d+", item):
                items.append(int(item))
                continue
            m = _RANGE_RE.fullmatch(item)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if a > b:
                    raise ValueError(f"题号区间应为升序 a<=b: {item!r}")
                items.extend(range(a, b + 1))
                continue
            m = _NUMERIC_SUFFIX_RE.fullmatch(item)
            if m:
                # 与表头识别一致：23作文 视为题号 23
                items.append(int(m.group(1)))
                continue
            # 其余（中文开头、整列大题名等）作为得分列列名
            items.append(item)
        if not items:
            raise ValueError(f"{name}: 题型题号列表为空")
        result[name] = items
    return result


def _contains(a: list[int], b: list[int]) -> bool:
    return bool(b) and set(b) <= set(a)


def _partial_overlap(a: list[int], b: list[int]) -> bool:
    sa, sb = set(a), set(b)
    return bool(sa & sb) and not (sa <= sb or sb <= sa)


@dataclass
class QuestionTypePlan:
    """解析后的题型方案。"""

    mode: str                        # binary / config
    top_level: list[str]             # 顶层题型（有序，内部规范名）
    parent: dict[str, str]           # 子题型 -> 父题型
    question_type: dict[int, str]    # 题号 -> 最终题型（最深子题型）
    ranges: dict[str, list[int]]     # 题型名 -> 题号列表
    columns: dict[str, list[str]]    # 题型名 -> 得分列列名（中文大题列）
    column_type: dict[str, str]      # 得分列列名 -> 所属题型（规范名）
    objective_count: int | None = None  # binary 模式使用的最大客观题数
    covered: set[int] = field(default_factory=set)  # 配置覆盖的题号

    def type_for(self, qid: int) -> str | None:
        """返回题号的最深题型；未覆盖时 binary 模式返回顶层，config 模式返回 None。"""
        if qid in self.question_type:
            return self.question_type[qid]
        if self.mode == "binary":
            return self._binary_parent(qid)
        return None

    def _binary_parent(self, qid: int) -> str:
        if self.objective_count is not None:
            return "客观" if qid <= self.objective_count else "主观"
        return "客观" if "-" not in str(qid) else "主观"

    def top_of(self, qid: int) -> str:
        """返回题号所属顶层题型（用于客观/主观分聚合）。"""
        qtype = self.type_for(qid)
        if qtype is None:
            return ""
        return self._top_of_type(qtype)

    def _top_of_type(self, qtype: str) -> str:
        """沿题型层级上溯到顶层题型。"""
        seen: set[str] = set()
        while qtype in self.parent and qtype not in seen:
            seen.add(qtype)
            qtype = self.parent[qtype]
        return qtype

    def column_names(self) -> list[str]:
        """返回全部得分列列名（按题型配置顺序去重）。"""
        names: list[str] = []
        for tokens in self.columns.values():
            for token in tokens:
                if token not in names:
                    names.append(token)
        return names

    def type_for_column(self, token: str) -> str | None:
        """返回得分列列名的最深所属题型。"""
        return self.column_type.get(token)

    def top_of_column(self, token: str) -> str:
        """返回得分列列名所属顶层题型（用于客观/主观分聚合）。"""
        qtype = self.column_type.get(token)
        if qtype is None:
            return ""
        return self._top_of_type(qtype)


def resolve_question_types(
    question_types: dict[str, list[int | str]],
    binary_split: bool,
    objective_count: int | None,
) -> QuestionTypePlan | None:
    """解析题型配置为方案；配置为空返回 None（使用默认客观/主观判定）。"""
    if not question_types:
        return None
    ranges: dict[str, list[int]] = {}
    columns: dict[str, list[str]] = {}
    for raw_name, items in question_types.items():
        name = _canonical(str(raw_name).strip())
        nums: list[int] = []
        tokens: list[str] = []
        for item in items:
            if isinstance(item, bool):
                raise ValueError(f"{name}: 题型值类型错误: {item!r}")
            if isinstance(item, int):
                nums.append(item)
            elif isinstance(item, str) and item.isdigit():
                nums.append(int(item))
            elif isinstance(item, str) and item.startswith(_QUESTION_COLUMN_MARKER):
                token = item[len(_QUESTION_COLUMN_MARKER):].strip()
                if not token:
                    raise ValueError(f"{name}: 列名标记 '@' 后不能为空")
                tokens.append(token)
            elif isinstance(item, str):
                tokens.append(item)
            else:
                raise ValueError(f"{name}: 题型值类型错误: {item!r}")
        if nums:
            ranges[name] = sorted(set(nums))
        if tokens:
            seen: set[str] = set()
            uniq: list[str] = []
            for token in tokens:
                if token not in seen:
                    seen.add(token)
                    uniq.append(token)
            columns[name] = uniq
    names = list(dict.fromkeys([*ranges, *columns]))
    # 每个题型“覆盖面” = 数字题号 ∪ 列名（用于父子层级判定）
    cover = {
        name: set(ranges.get(name, [])) | set(columns.get(name, []))
        for name in names
    }

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if _partial_overlap(
                ranges.get(names[i], []), ranges.get(names[j], [])
            ):
                raise ValueError(
                    f"题型范围部分重叠（应为完全包含或互不重叠）: "
                    f"{names[i]} 与 {names[j]}"
                )
            common_tokens = set(columns.get(names[i], [])) & set(
                columns.get(names[j], [])
            )
            if common_tokens and not (
                cover[names[i]] <= cover[names[j]]
                or cover[names[j]] <= cover[names[i]]
            ):
                raise ValueError(
                    f"得分列列名同时出现在互不包含的题型: "
                    f"{names[i]} 与 {names[j]}"
                )

    top_level: list[str] = []
    parent: dict[str, str] = {}
    for name in names:
        containers = [
            o
            for o in names
            if o != name
            and cover[name]
            and cover[name] <= cover[o]
        ]
        if containers:
            parent[name] = min(containers, key=lambda o: len(cover[o]))
        else:
            top_level.append(name)
    # 列名归属其最深的包含题型（与数字题号规则一致）
    column_type: dict[str, str] = {}
    for tokens in columns.values():
        for token in tokens:
            containers = [
                n for n in names if token in cover[n]
            ]
            column_type[token] = min(
                containers, key=lambda n: len(cover[n])
            )

    if binary_split and len(top_level) <= 2:
        return _resolve_binary(
            ranges, columns, column_type, objective_count, parent
        )
    return _resolve_config(ranges, columns, column_type, top_level, parent)


def _resolve_config(
    ranges: dict[str, list[int]],
    columns: dict[str, list[str]],
    column_type: dict[str, str],
    top_level: list[str],
    parent: dict[str, str],
) -> QuestionTypePlan:
    """完全按配置划分题型。"""
    qmap: dict[int, str] = {}
    for qid in sorted({q for v in ranges.values() for q in v}):
        deepest = min(
            (name for name, qids in ranges.items() if qid in qids),
            key=lambda name: len(ranges[name]),
        )
        qmap[qid] = deepest
    return QuestionTypePlan(
        mode="config",
        top_level=[_canonical(t) for t in top_level],
        parent={_canonical(k): _canonical(v) for k, v in parent.items()},
        question_type=qmap,
        ranges=ranges,
        columns=columns,
        column_type=column_type,
        covered=set(qmap),
    )


def _resolve_binary(
    ranges: dict[str, list[int]],
    columns: dict[str, list[str]],
    column_type: dict[str, str],
    objective_count: int | None,
    parent: dict[str, str],
) -> QuestionTypePlan:
    """二分配置：客观/主观范围由最大客观题数确定，配置题型作为子题型。"""
    sub_parent: dict[str, str] = {}
    qmap: dict[int, str] = {}
    for name, qids in ranges.items():
        if objective_count is not None:
            parents = {"客观" if q <= objective_count else "主观" for q in qids}
        else:
            parents = {"客观" if "-" not in str(q) else "主观" for q in qids}
        if len(parents) != 1:
            raise ValueError(
                f"二分配置下题型 {name} 的范围跨越客观/主观"
                f"（objective_question_count={objective_count}）"
            )
        parent_name = next(iter(parents))
        if name != parent_name:
            sub_parent[name] = parent_name
        for q in qids:
            if q not in qmap:
                qmap[q] = name
            elif len(ranges[name]) < len(ranges[qmap[q]]):
                qmap[q] = name  # 取包含该题号的最深（最小范围）子题型
    # 纯列名题型（无数字题号）沿用覆盖关系中的父子归属，
    # 如 填空(填空题12-14) -> 主观；有数字范围的题型仍按二分配置判定
    for name, tokens in columns.items():
        if not ranges.get(name) and name in parent:
            sub_parent[name] = parent[name]
    return QuestionTypePlan(
        mode="binary",
        top_level=["客观", "主观"],
        parent=sub_parent,
        question_type=qmap,
        ranges=ranges,
        columns=columns,
        column_type=column_type,
        objective_count=objective_count,
        covered=set(qmap),
    )
