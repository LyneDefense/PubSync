from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_db_and_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()


def ensure_runtime_schema() -> None:
    statements = [
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
        "ALTER TABLE content_profiles ADD COLUMN IF NOT EXISTS grouping_mode VARCHAR(30) NOT NULL DEFAULT 'regional'",
        """
        INSERT INTO content_profiles (
            tenant_id, publication_name, workspace_title, title_prefix, content_domain,
            editor_persona, audience, article_style, grouping_mode, international_label, domestic_label,
            categories_json, image_style, updated_at
        )
        VALUES (
            1, 'AI 科技早报', 'AI 早报', 'AI科技早报 | ', 'AI、科技、模型、算力、企业应用',
            '你是严谨的 AI 科技新闻主编', '科技从业者、产品经理、投资人与 AI 关注者',
            '信息密度高，事实准确，带行业观察', 'regional', '国际动态', '国内动态',
            '[]', '抽象科技视觉、信息图、芯片、网络、云与模型架构', NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        """
        INSERT INTO content_profiles (
            tenant_id, publication_name, workspace_title, title_prefix, content_domain,
            editor_persona, audience, article_style, grouping_mode, international_label, domestic_label,
            categories_json, image_style, updated_at
        )
        VALUES (
            2, 'EyangPet 宠物内容', 'EyangPet', 'EyangPet | ', '宠物健康、养宠知识、宠物行业资讯、宠物食品用品、宠物服务',
            '你是严谨、温和、实用的宠物内容主编', '养宠家庭、宠物行业从业者、宠物店和宠物服务经营者',
            '通俗易懂，实用可信，避免制造焦虑，必要时提醒咨询兽医', 'none', '精选资讯', '养宠知识',
            '[]', '温暖、干净、可信的宠物知识视觉，避免夸张医疗暗示和恐怖画面', NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
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
        """
        INSERT INTO publishing_settings (
            tenant_id, daily_publish_enabled, publish_time_hour, publish_time_minute, auto_send_wechat_draft,
            generate_article_images, max_article_images, min_article_images,
            news_source_urls, international_news_source_urls, domestic_news_source_urls,
            news_per_source_limit, international_news_candidates, domestic_news_candidates,
            news_lookback_hours, max_news_candidates, dedup_lookback_days,
            dedup_direct_similarity, dedup_review_similarity, dedup_enable_llm_review,
            article_news_limit, article_news_lookback_hours,
            article_domestic_min, article_domestic_target, article_domestic_max,
            article_international_min, article_international_target, article_international_max,
            updated_at
        )
        VALUES (
            1, false, 8, 0, false,
            true, 3, 1,
            '', '', '',
            8, 40, 40,
            72, 80, 7,
            '0.82', '0.42', true,
            10, 72,
            1, 3, 4,
            3, 6, 7,
            NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        """
        INSERT INTO publishing_settings (
            tenant_id, daily_publish_enabled, publish_time_hour, publish_time_minute, auto_send_wechat_draft,
            generate_article_images, max_article_images, min_article_images,
            news_source_urls, international_news_source_urls, domestic_news_source_urls,
            news_per_source_limit, international_news_candidates, domestic_news_candidates,
            news_lookback_hours, max_news_candidates, dedup_lookback_days,
            dedup_direct_similarity, dedup_review_similarity, dedup_enable_llm_review,
            article_news_limit, article_news_lookback_hours,
            article_domestic_min, article_domestic_target, article_domestic_max,
            article_international_min, article_international_target, article_international_max,
            updated_at
        )
        VALUES (
            2, false, 8, 0, false,
            true, 2, 1,
            '', '', '',
            8, 20, 40,
            72, 60, 7,
            '0.82', '0.42', true,
            8, 72,
            0, 0, 0,
            0, 8, 8,
            NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1 REFERENCES tenants(id)",
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(200)",
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS dedup_status VARCHAR(30) NOT NULL DEFAULT 'unique'",
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS duplicate_of_id INTEGER REFERENCES news_items(id)",
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS dedup_reason TEXT",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1 REFERENCES tenants(id)",
        "ALTER TABLE article_news_items ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1 REFERENCES tenants(id)",
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1 REFERENCES tenants(id)",
        "ALTER TABLE news_sources ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1 REFERENCES tenants(id)",
        "ALTER TABLE operation_tasks ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1 REFERENCES tenants(id)",
        "ALTER TABLE operation_task_events ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1 REFERENCES tenants(id)",
        "ALTER TABLE news_items DROP CONSTRAINT IF EXISTS news_items_url_key",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_news_items_tenant_url ON news_items(tenant_id, url)",
        "CREATE INDEX IF NOT EXISTS ix_news_items_tenant_id ON news_items(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_news_items_dedup_status ON news_items(dedup_status)",
        "CREATE INDEX IF NOT EXISTS ix_news_items_duplicate_of_id ON news_items(duplicate_of_id)",
        "CREATE INDEX IF NOT EXISTS ix_articles_tenant_id ON articles(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_operation_tasks_tenant_id ON operation_tasks(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_operation_task_events_tenant_id ON operation_task_events(tenant_id)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
