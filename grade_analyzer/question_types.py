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
- 范围完全包含 -> 小范围为子题型；部分重叠（非完全包含）-> 报错；
- 顶层题型 = 未被其他题型包含者；每题题型 = 包含该题号的最深子题型；
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


def _normalize_width(text: str) -> str:
    """全角标点转半角（，；－　：），便于解析兼容。"""
    return text.translate(_WIDTH_MAP)


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


def parse_question_types(value) -> dict[str, list[int]]:
    """把 question_types 配置解析为 题型名 -> 题号列表。"""
    if not value:
        return {}
    if not isinstance(value, dict):
        raise ValueError("question_types 应为映射（题型名 -> 数量或题号列表）")
    result: dict[str, list[int]] = {}
    next_start = 1
    seen_list = False
    for name, raw in value.items():
        name = _canonical(str(name).strip())
        if not name:
            raise ValueError("question_types 存在空题型名")
        text = str(raw).strip()
        nums = _parse_question_list(text)
        if nums is None:
            if seen_list:
                raise ValueError(
                    f"{name}: 列表式后不允许出现数量式（数量式只能放在前面若干行）"
                )
            n = int(text)
            nums = list(range(next_start, next_start + n))
            next_start += n
        else:
            seen_list = True
        if not nums:
            raise ValueError(f"{name}: 题型题号列表为空")
        result[name] = sorted(set(nums))
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
        seen: set[str] = set()
        while qtype in self.parent and qtype not in seen:
            seen.add(qtype)
            qtype = self.parent[qtype]
        return qtype


def resolve_question_types(
    question_types: dict[str, list[int]],
    binary_split: bool,
    objective_count: int | None,
) -> QuestionTypePlan | None:
    """解析题型配置为方案；配置为空返回 None（使用默认客观/主观判定）。"""
    if not question_types:
        return None
    ranges = {_canonical(name): sorted(set(v)) for name, v in question_types.items()}
    names = list(ranges)

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if _partial_overlap(ranges[names[i]], ranges[names[j]]):
                raise ValueError(
                    f"题型范围部分重叠（应为完全包含或互不重叠）: "
                    f"{names[i]} 与 {names[j]}"
                )

    top_level: list[str] = []
    parent: dict[str, str] = {}
    for name in names:
        containers = [
            o for o in names if o != name and _contains(ranges[o], ranges[name])
        ]
        if containers:
            parent[name] = min(containers, key=lambda o: len(ranges[o]))
        else:
            top_level.append(name)

    if binary_split and len(top_level) <= 2:
        return _resolve_binary(ranges, objective_count)
    return _resolve_config(ranges, top_level, parent)


def _resolve_config(
    ranges: dict[str, list[int]],
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
        covered=set(qmap),
    )


def _resolve_binary(
    ranges: dict[str, list[int]],
    objective_count: int | None,
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
    return QuestionTypePlan(
        mode="binary",
        top_level=["客观", "主观"],
        parent=sub_parent,
        question_type=qmap,
        ranges=ranges,
        objective_count=objective_count,
        covered=set(qmap),
    )
