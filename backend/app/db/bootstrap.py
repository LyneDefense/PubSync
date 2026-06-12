"""默认种子数据。

表结构由 Alembic（``alembic/versions/0001_baseline_schema.py``）基于 ORM 模型
``Base.metadata.create_all`` 创建；本模块只负责灌入两个默认工作空间所需的初始数据
（租户、用户、内容定位、公众号占位、排版、发布设置、内容分组）。

历史上这里曾混杂大量临时的 ``ALTER ... IF NOT EXISTS`` / ``UPDATE`` 补丁
（旧的 ``ensure_runtime_schema``），现已移除——schema 演进统一走 Alembic 迁移。
所有 INSERT 都带 ``ON CONFLICT DO NOTHING``，因此可重复执行、不会覆盖已有数据。
"""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config import get_settings


AI_GLOBAL_SOURCE_URLS = ",".join(
    [
        "TechCrunch AI|https://techcrunch.com/category/artificial-intelligence/feed/",
        "VentureBeat AI|https://venturebeat.com/category/ai/feed/",
        "The Verge AI|https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "InfoQ AI|https://feed.infoq.com/ai-ml-data-eng",
        "Hacker News AI|https://hnrss.org/newest?q=AI",
        "Hacker News OpenAI|https://hnrss.org/newest?q=OpenAI",
    ]
)
AI_CHINA_SOURCE_URLS = ",".join(["36Kr|https://36kr.com/feed", "InfoQ CN|https://www.infoq.cn/feed"])
PET_HEALTH_SOURCE_URLS = ",".join(
    [
        "Pet Health Network|https://www.pethealthnetwork.com/rss.xml",
        "Preventive Vet Dogs|https://www.preventivevet.com/dogs/rss.xml",
        "Preventive Vet Cats|https://www.preventivevet.com/cats/rss.xml",
        "Vet Help Direct|https://vethelpdirect.com/vetblog/feed/",
        "Veterinary Practice News|https://www.veterinarypracticenews.com/feed/",
    ]
)
PET_KNOWLEDGE_SOURCE_URLS = ",".join(
    [
        "AKC Expert Advice|https://www.akc.org/expert-advice/feed/",
        "Whole Dog Journal|https://www.whole-dog-journal.com/feed/",
        "Animal Wellness Magazine|https://animalwellnessmagazine.com/feed/",
        "Fear Free Happy Homes|https://www.fearfreehappyhomes.com/feed/",
        "Canine Journal|https://www.caninejournal.com/feed/",
        "DogTime|https://dogtime.com/feed",
        "Catster|https://www.catster.com/feed/",
        "Cats.com|https://cats.com/feed",
        "Modern Cat|https://moderncat.com/feed/",
    ]
)
PET_INDUSTRY_SOURCE_URLS = ",".join(
    [
        "DVM360|https://www.dvm360.com/rss",
        "Veterinary Practice News|https://www.veterinarypracticenews.com/feed/",
    ]
)


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def seed_statements() -> list[str]:
    """返回灌入默认数据的 SQL 列表（全部 ON CONFLICT DO NOTHING，可重复执行）。"""
    settings = get_settings()
    return [
        # —— 两个默认工作空间（租户）——
        """
        INSERT INTO tenants (id, name, slug, status, created_at)
        VALUES (1, 'AI 科技早报', 'ai-tech', 'active', NOW())
        ON CONFLICT (id) DO NOTHING
        """,
        """
        INSERT INTO tenants (id, name, slug, status, created_at)
        VALUES (2, 'EyangPet 宠物内容', 'eyangpet', 'active', NOW())
        ON CONFLICT (id) DO NOTHING
        """,
        # —— 初始用户（管理员来自配置；eyangpet 为示例账号）——
        f"""
        INSERT INTO users (username, password_hash, is_admin, tenant_id, status, created_at, updated_at)
        VALUES ({sql_literal(settings.admin_username)}, {sql_literal(settings.admin_password)}, true, 1, 'active', NOW(), NOW())
        ON CONFLICT (username) DO NOTHING
        """,
        """
        INSERT INTO users (username, password_hash, is_admin, tenant_id, status, created_at, updated_at)
        VALUES ('eyangpet', '123456', false, 2, 'active', NOW(), NOW())
        ON CONFLICT (username) DO NOTHING
        """,
        # —— 内容定位 ——
        """
        INSERT INTO content_profiles (
            tenant_id, publication_name, workspace_title, title_prefix, content_domain,
            editor_persona, audience, article_style, grouping_mode,
            categories_json, image_style, updated_at
        )
        VALUES (
            1, 'AI 科技早报', 'AI 早报', 'AI科技早报 | ', 'AI、科技、模型、算力、企业应用',
            '你是严谨的 AI 科技新闻主编', '科技从业者、产品经理、投资人与 AI 关注者',
            '信息密度高，事实准确，带行业观察', 'regional',
            '[]', '抽象科技视觉、信息图、芯片、网络、云与模型架构', NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        """
        INSERT INTO content_profiles (
            tenant_id, publication_name, workspace_title, title_prefix, content_domain,
            editor_persona, audience, article_style, grouping_mode,
            categories_json, image_style, updated_at
        )
        VALUES (
            2, 'EyangPet 宠物内容', 'EyangPet', 'EyangPet | ', '宠物健康、养宠知识、宠物行业资讯、宠物食品用品、宠物服务',
            '你是严谨、温和、实用的宠物内容主编', '养宠家庭、宠物行业从业者、宠物店和宠物服务经营者',
            '通俗易懂，实用可信，避免制造焦虑，必要时提醒咨询兽医', 'none',
            '[]', '温暖、干净、可信的宠物知识视觉，避免夸张医疗暗示和恐怖画面', NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        # —— 公众号占位（待用户填 AppID/Secret）——
        """
        INSERT INTO wechat_accounts (tenant_id, app_id, app_secret, auto_send_draft, updated_at)
        VALUES (1, '', '', false, NOW())
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        """
        INSERT INTO wechat_accounts (tenant_id, app_id, app_secret, auto_send_draft, updated_at)
        VALUES (2, '', '', false, NOW())
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        # —— 排版设置 ——
        """
        INSERT INTO layout_settings (
            tenant_id, template_name, primary_color, accent_color, text_color, heading_color,
            body_font_size, heading_font_size, line_height, section_spacing, image_radius,
            show_group_heading, show_source, show_editor_note, updated_at
        )
        VALUES (
            1, 'clean', '#0f766e', '#64748b', 'inherit', 'inherit',
            15, 19, '1.85', 28, 8, true, true, true, NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        """
        INSERT INTO layout_settings (
            tenant_id, template_name, primary_color, accent_color, text_color, heading_color,
            body_font_size, heading_font_size, line_height, section_spacing, image_radius,
            show_group_heading, show_source, show_editor_note, updated_at
        )
        VALUES (
            2, 'warm', '#b45309', '#d97706', 'inherit', 'inherit',
            15, 18, '1.9', 24, 10, false, true, true, NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        # —— 发布设置 ——
        """
        INSERT INTO publishing_settings (
            tenant_id, daily_publish_enabled, publish_frequency, publish_weekday, publish_month_day,
            publish_time_hour, publish_time_minute, auto_send_wechat_draft,
            generate_article_images, max_article_images, min_article_images,
            news_source_urls, news_per_source_limit,
            news_lookback_hours, max_news_candidates, dedup_lookback_days,
            dedup_direct_similarity, dedup_review_similarity, dedup_enable_llm_review,
            article_news_limit, article_news_lookback_hours,
            updated_at
        )
        VALUES (
            1, false, 'daily', 1, 1, 8, 0, false,
            true, 3, 1,
            '', 8,
            72, 80, 7,
            '0.82', '0.42', true,
            10, 72,
            NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        """
        INSERT INTO publishing_settings (
            tenant_id, daily_publish_enabled, publish_frequency, publish_weekday, publish_month_day,
            publish_time_hour, publish_time_minute, auto_send_wechat_draft,
            generate_article_images, max_article_images, min_article_images,
            news_source_urls, news_per_source_limit,
            news_lookback_hours, max_news_candidates, dedup_lookback_days,
            dedup_direct_similarity, dedup_review_similarity, dedup_enable_llm_review,
            article_news_limit, article_news_lookback_hours,
            updated_at
        )
        VALUES (
            2, false, 'daily', 1, 1, 8, 0, false,
            true, 2, 1,
            '', 8,
            72, 60, 7,
            '0.82', '0.42', true,
            8, 72,
            NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        # —— 内容分组（AI 工作空间：国际 / 国内）——
        f"""
        INSERT INTO content_groups (
            tenant_id, group_key, name, content_mode, source_urls, candidate_limit,
            article_min, article_target, article_max, position, enabled, created_at, updated_at
        )
        VALUES
            (1, 'global', '国际动态', 'news', '{AI_GLOBAL_SOURCE_URLS}', 40, 3, 6, 7, 0, true, NOW(), NOW()),
            (1, 'china', '国内动态', 'news', '{AI_CHINA_SOURCE_URLS}', 40, 1, 3, 4, 1, true, NOW(), NOW())
        ON CONFLICT (tenant_id, group_key) DO NOTHING
        """,
        # —— 内容分组（宠物工作空间：健康 / 知识 / 行业）——
        f"""
        INSERT INTO content_groups (
            tenant_id, group_key, name, content_mode, source_urls, candidate_limit,
            article_min, article_target, article_max, position, enabled, created_at, updated_at
        )
        VALUES
            (2, 'pet-health', '宠物健康', 'knowledge', '{PET_HEALTH_SOURCE_URLS}', 30, 0, 3, 4, 0, true, NOW(), NOW()),
            (2, 'pet-knowledge', '养宠知识', 'knowledge', '{PET_KNOWLEDGE_SOURCE_URLS}', 30, 0, 3, 4, 1, true, NOW(), NOW()),
            (2, 'pet-industry', '行业资讯', 'analysis', '{PET_INDUSTRY_SOURCE_URLS}', 20, 0, 2, 3, 2, true, NOW(), NOW())
        ON CONFLICT (tenant_id, group_key) DO NOTHING
        """,
    ]


def seed_default_data(connection: Connection) -> None:
    """在给定连接上灌入默认数据（由 Alembic baseline 迁移调用）。"""
    for statement in seed_statements():
        connection.execute(text(statement))
