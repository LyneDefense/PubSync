"""风格指纹 + StyleDist 相似度(纯 stdlib、确定性、不调 LLM)。

设计见 docs/Skill优化_方案设计.md §4。核心:
- 风格指纹 = 一组数值化文体特征(句长/标点/emoji/人称/列表/标签…)。
- StyleDist 相似度(0-100,越高越像)= 字符 n-gram 重叠(对模态错配敏感)+ 文体特征接近度。
- 归属判别 = 在多个画像里取相似度最高者。
- gap_closed% = (候选 − floor)/(ceiling − floor),回答「离以假乱真还差多少」。

PoC 教训(问题清单 #10):图文 vs 视频口播两种文体 n-gram 几乎不重叠 → 相似度天然极低,
正好被本指标抓到;评委却会被骗。所以训练奖励用本客观指标、不用 LLM 评委。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

# 特征向量里参与「特征接近度」的键(顺序固定,保证确定性)。
FEATURE_KEYS = (
    "avg_sent_len",
    "exclaim_per100",
    "question_per100",
    "ellipsis_per100",
    "comma_per100",
    "emoji_per100",
    "digit_per100",
    "first_person_per100",
    "hashtag_per100",
    "bullet_ratio",
    "question_sent_ratio",
)

_SENT_SPLIT = re.compile(r"[。！？!?\n]+")
_EMOJI = re.compile("[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]")
_FIRST_PERSON = re.compile(r"我|咱|俺")
_BULLET = re.compile(r"^\s*([0-9]+[.、)]|[-*·•‣]|[①-⑩])")
_WORD = re.compile(r"\s+")


def _sentences(text: str) -> list[str]:
    return [s for s in (p.strip() for p in _SENT_SPLIT.split(text or "")) if s]


def extract_features(text: str) -> dict[str, float]:
    """把一段文本压成数值化文体指纹。空文本返回全 0。"""
    text = text or ""
    n = len(text)
    feats = {k: 0.0 for k in FEATURE_KEYS}
    if n == 0:
        return feats
    sents = _sentences(text)
    sent_n = max(len(sents), 1)
    per100 = 100.0 / n

    feats["avg_sent_len"] = sum(len(s) for s in sents) / sent_n
    feats["exclaim_per100"] = (text.count("！") + text.count("!")) * per100
    feats["question_per100"] = (text.count("？") + text.count("?")) * per100
    feats["ellipsis_per100"] = (text.count("…") + text.count("...")) * per100
    feats["comma_per100"] = (text.count("，") + text.count("、") + text.count(",")) * per100
    feats["emoji_per100"] = len(_EMOJI.findall(text)) * per100
    feats["digit_per100"] = sum(c.isdigit() for c in text) * per100
    feats["first_person_per100"] = len(_FIRST_PERSON.findall(text)) * per100
    feats["hashtag_per100"] = text.count("#") * per100

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines:
        feats["bullet_ratio"] = sum(1 for ln in lines if _BULLET.match(ln)) / len(lines)
    # 分句时标点已被切掉,用问号数/句数近似「疑问句占比」(钳到 1)。
    q_marks = text.count("？") + text.count("?")
    feats["question_sent_ratio"] = min(1.0, q_marks / sent_n)
    return feats


def char_ngrams(text: str, n: int = 3) -> Counter:
    """字符 n-gram 计数(去空白)。对词汇/文体重叠敏感。"""
    clean = _WORD.sub("", text or "")
    if len(clean) < n:
        return Counter([clean]) if clean else Counter()
    return Counter(clean[i : i + n] for i in range(len(clean) - n + 1))


@dataclass
class StyleProfile:
    """一个博主(或一组文本)的风格画像。"""

    n: int = 3
    sample_count: int = 0
    centroid: dict[str, float] = field(default_factory=dict)
    std: dict[str, float] = field(default_factory=dict)
    ngram_freq: dict[str, float] = field(default_factory=dict)  # 归一化频率


def build_profile(texts: list[str], n: int = 3) -> StyleProfile:
    """由一组文本(博主真笔记)建画像:特征均值/标准差 + 归一化 n-gram 频率。"""
    clean_texts = [t for t in texts if t and t.strip()]
    if not clean_texts:
        return StyleProfile(n=n)

    feat_list = [extract_features(t) for t in clean_texts]
    centroid: dict[str, float] = {}
    std: dict[str, float] = {}
    m = len(feat_list)
    for key in FEATURE_KEYS:
        vals = [f[key] for f in feat_list]
        mean = sum(vals) / m
        var = sum((v - mean) ** 2 for v in vals) / m
        centroid[key] = mean
        std[key] = math.sqrt(var)

    total = Counter()
    for t in clean_texts:
        total += char_ngrams(t, n)
    grand = sum(total.values()) or 1
    ngram_freq = {g: c / grand for g, c in total.items()}

    return StyleProfile(n=n, sample_count=m, centroid=centroid, std=std, ngram_freq=ngram_freq)


def _ngram_cosine(text: str, profile: StyleProfile) -> float:
    if not profile.ngram_freq:
        return 0.0
    counts = char_ngrams(text, profile.n)
    total = sum(counts.values())
    if not total:
        return 0.0
    text_freq = {g: c / total for g, c in counts.items()}
    dot = sum(freq * profile.ngram_freq.get(g, 0.0) for g, freq in text_freq.items())
    norm_a = math.sqrt(sum(v * v for v in text_freq.values()))
    norm_b = math.sqrt(sum(v * v for v in profile.ngram_freq.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _feature_closeness(text: str, profile: StyleProfile) -> float:
    if not profile.centroid:
        return 0.0
    feats = extract_features(text)
    closes = []
    for key in FEATURE_KEYS:
        std = profile.std.get(key, 0.0)
        scale = std if std > 1e-6 else max(abs(profile.centroid.get(key, 0.0)), 1.0)
        z = abs(feats[key] - profile.centroid.get(key, 0.0)) / scale
        closes.append(1.0 / (1.0 + z))  # z=0→1, 越远越接近 0
    return sum(closes) / len(closes)


def style_similarity(text: str, profile: StyleProfile, *, ngram_weight: float = 0.6) -> float:
    """文本与画像的风格相似度(0-100,越高越像)。"""
    if not text or not text.strip() or profile.sample_count == 0:
        return 0.0
    ngram = _ngram_cosine(text, profile)
    feat = _feature_closeness(text, profile)
    score = ngram_weight * ngram + (1.0 - ngram_weight) * feat
    return round(100.0 * score, 2)


def attribution(text: str, profiles: dict[str, StyleProfile]) -> str | None:
    """把文本归到相似度最高的画像名下;无画像返回 None。"""
    best_name = None
    best_score = -1.0
    for name, profile in profiles.items():
        score = style_similarity(text, profile)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name


def gap_closed(candidate: float, floor: float, ceiling: float) -> float:
    """离「以假乱真」还差多少(0-100%)。candidate/floor/ceiling 都是相似度分。"""
    span = ceiling - floor
    if span <= 1e-6:
        return 0.0
    pct = (candidate - floor) / span * 100.0
    return round(max(0.0, min(100.0, pct)), 1)
