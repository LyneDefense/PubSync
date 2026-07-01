"""通用规则包(所有账号生效):广告法绝对化 / 保证承诺 / 导流 / 诱导营销 / 基线违禁。

原则:铁证词 certain(直接判);易误报词 weak(诊断降为提示、创作仍提醒),并配白名单 / 上下文降误报。
"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

COMMON_PACK = RulePack(
    id="common",
    label="通用",
    scope="universal",
    rules=(
        # 绝对化——铁证的"营销超级词"(certain)
        Rule(
            id="extreme_hard",
            category="极限词·绝对化",
            words=("全网第一", "销量第一", "排名第一", "全国第一", "世界第一", "宇宙第一", "中国第一",
                   "史无前例", "前无古人", "绝无仅有", "独一无二", "领袖品牌", "万能", "首选品牌"),
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,
            basis="广告法第9条·绝对化用语",
            hint="去掉「第一/唯一」类绝对化,改成客观描述或具体场景",
        ),
        # 绝对化——口语高频、易误报(weak + 语境白名单)
        Rule(
            id="extreme_soft",
            category="极限词·绝对化",
            words=("最佳", "最好", "最强", "最优", "最低价", "最高级", "最便宜", "最受欢迎", "最先进",
                   "顶级", "极致", "极品", "首家", "独家", "百分百", "国家级", "世界级", "世界领先"),
            allow_context=(r"最好(还是|别|不|要|在|先|等|能|趁|趁早|尽|得)",
                           r"(还是|要|得|不如|建议|最好是)最好", r"(办公|公司)"),
            severity=Severity.THROTTLE,
            confidence=Confidence.WEAK,
            basis="广告法第9条·绝对化用语",
            hint="「最好用/顶级/独家」这类改成「我用下来比较顺手」等客观说法",
        ),
        # 保证 / 承诺(certain,限流)
        Rule(
            id="guarantee",
            category="保证承诺",
            words=("保证有效", "无效退款", "100%有效", "百分百有效", "绝对安全", "绝对有效",
                   "永久有效", "永不复发", "零风险", "无任何副作用", "包过", "包好"),
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,
            basis="广告法第28条·虚假/绝对保证",
            hint="不要做绝对保证,改成「多数人反馈」「因人而异」",
        ),
        # 导流私域——铁证(certain,封号)
        Rule(
            id="diversion",
            category="导流·站外引流",
            words=("加微信", "加我微信", "微信号", "扫二维码", "扫码加", "私信领取", "私信我",
                   "vx", "v信", "薇信", "威信", "链接见主页", "主页领取", "下单链接", "购买链接",
                   "戳链接", "点击购买"),
            allow_words=("扫码支付", "扫码点餐"),
            severity=Severity.BAN,
            confidence=Confidence.CERTAIN,
            basis="交易导流商业秩序治理规则",
            hint="不要留联系方式/外链/引导私域,改成站内自然互动",
        ),
        # 导流——易误报的(weak):公众号 / 私我 mention
        Rule(
            id="diversion_soft",
            category="导流·站外引流",
            words=("公众号", "私我", "加我"),
            require_context=(r"(关注|搜|领|回复|扫|同名|置顶|简介|微信|vx|v信)",),
            severity=Severity.BAN,
            confidence=Confidence.WEAK,
            basis="交易导流商业秩序治理规则",
            hint="不要引导去站外/私域,改成站内自然互动",
        ),
        # 诱导营销——铁证(certain,限流)
        Rule(
            id="inducement_hard",
            category="诱导营销",
            words=("秒杀", "抢爆", "疯抢", "万人疯抢", "限时抢购", "清仓甩卖", "恭喜获奖",
                   "全民免单", "0元购", "刷单", "点击有惊喜"),
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,
            basis="营销违规词·过度营销",
            hint="去掉抢购/抽奖话术,改成自然分享和轻量互动",
        ),
        # 诱导营销——易误报(weak)
        Rule(
            id="inducement_soft",
            category="诱导营销",
            words=("免费领取", "免费送", "返现", "返利", "代购", "微商", "白嫖"),
            severity=Severity.THROTTLE,
            confidence=Confidence.WEAK,
            basis="营销违规词",
            hint="弱化「免费领/返现」等诱导,改成自然分享",
        ),
        # 疾病治疗 / 疗效宣称——对任何账号都违法(certain,封号),不分赛道
        Rule(
            id="medical_claim",
            category="医疗·疗效宣称",
            words=("治愈", "根治", "痊愈", "疗效", "药用", "处方药", "特效药", "消炎", "抗炎",
                   "抗癌", "防癌", "降血压", "降血糖", "壮阳", "丰胸", "包治", "药到病除"),
            allow_words=("消炎药",),  # 提到「消炎药」这个名词本身宽松些
            severity=Severity.BAN,
            confidence=Confidence.CERTAIN,
            basis="广告法·不得涉及疾病治疗/宣称疗效(适用所有品类)",
            hint="删除疗效/治病宣称,改成温和、可求证的体验表达",
        ),
        # 基线违禁(certain,封号)
        Rule(
            id="baseline",
            category="敏感违禁",
            words=("赌博", "博彩", "毒品", "走私", "诈骗", "传销", "枪支", "色情", "裸聊", "约炮", "fa轮"),
            severity=Severity.BAN,
            confidence=Confidence.CERTAIN,
            basis="社区规范·法律红线",
            hint="移除该违规内容",
        ),
    ),
)
