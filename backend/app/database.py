from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

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
    enum_statements = [
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum
                WHERE enumlabel = 'cancel_requested'
                  AND enumtypid = 'task_status'::regtype
            ) THEN
                ALTER TYPE task_status ADD VALUE 'cancel_requested';
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum
                WHERE enumlabel = 'cancelled'
                  AND enumtypid = 'task_status'::regtype
            ) THEN
                ALTER TYPE task_status ADD VALUE 'cancelled';
            END IF;
        END $$;
        """,
    ]
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
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            password_hash VARCHAR(200) NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT false,
            tenant_id INTEGER REFERENCES tenants(id),
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'active'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
        "CREATE INDEX IF NOT EXISTS ix_users_username ON users(username)",
        "CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users(tenant_id)",
        f"""
        INSERT INTO users (username, password_hash, is_admin, tenant_id, status, created_at, updated_at)
        VALUES ({sql_literal(get_settings().admin_username)}, {sql_literal(get_settings().admin_password)}, true, 1, 'active', NOW(), NOW())
        ON CONFLICT (username) DO NOTHING
        """,
        """
        INSERT INTO users (username, password_hash, is_admin, tenant_id, status, created_at, updated_at)
        VALUES ('eyangpet', '123456', false, 2, 'active', NOW(), NOW())
        ON CONFLICT (username) DO NOTHING
        """,
        "ALTER TABLE content_profiles ADD COLUMN IF NOT EXISTS grouping_mode VARCHAR(30) NOT NULL DEFAULT 'regional'",
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'content_profiles' AND column_name = 'international_label'
            ) THEN
                ALTER TABLE content_profiles ALTER COLUMN international_label SET DEFAULT '';
                ALTER TABLE content_profiles ALTER COLUMN international_label DROP NOT NULL;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'content_profiles' AND column_name = 'domestic_label'
            ) THEN
                ALTER TABLE content_profiles ALTER COLUMN domestic_label SET DEFAULT '';
                ALTER TABLE content_profiles ALTER COLUMN domestic_label DROP NOT NULL;
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'publishing_settings' AND column_name = 'international_news_source_urls'
            ) THEN
                ALTER TABLE publishing_settings ALTER COLUMN international_news_source_urls SET DEFAULT '';
                ALTER TABLE publishing_settings ALTER COLUMN international_news_source_urls DROP NOT NULL;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'publishing_settings' AND column_name = 'domestic_news_source_urls'
            ) THEN
                ALTER TABLE publishing_settings ALTER COLUMN domestic_news_source_urls SET DEFAULT '';
                ALTER TABLE publishing_settings ALTER COLUMN domestic_news_source_urls DROP NOT NULL;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'publishing_settings' AND column_name = 'international_news_candidates'
            ) THEN
                ALTER TABLE publishing_settings ALTER COLUMN international_news_candidates SET DEFAULT 0;
                ALTER TABLE publishing_settings ALTER COLUMN international_news_candidates DROP NOT NULL;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'publishing_settings' AND column_name = 'domestic_news_candidates'
            ) THEN
                ALTER TABLE publishing_settings ALTER COLUMN domestic_news_candidates SET DEFAULT 0;
                ALTER TABLE publishing_settings ALTER COLUMN domestic_news_candidates DROP NOT NULL;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'publishing_settings' AND column_name = 'article_domestic_min'
            ) THEN
                ALTER TABLE publishing_settings ALTER COLUMN article_domestic_min SET DEFAULT 0;
                ALTER TABLE publishing_settings ALTER COLUMN article_domestic_min DROP NOT NULL;
                ALTER TABLE publishing_settings ALTER COLUMN article_domestic_target SET DEFAULT 0;
                ALTER TABLE publishing_settings ALTER COLUMN article_domestic_target DROP NOT NULL;
                ALTER TABLE publishing_settings ALTER COLUMN article_domestic_max SET DEFAULT 0;
                ALTER TABLE publishing_settings ALTER COLUMN article_domestic_max DROP NOT NULL;
                ALTER TABLE publishing_settings ALTER COLUMN article_international_min SET DEFAULT 0;
                ALTER TABLE publishing_settings ALTER COLUMN article_international_min DROP NOT NULL;
                ALTER TABLE publishing_settings ALTER COLUMN article_international_target SET DEFAULT 0;
                ALTER TABLE publishing_settings ALTER COLUMN article_international_target DROP NOT NULL;
                ALTER TABLE publishing_settings ALTER COLUMN article_international_max SET DEFAULT 0;
                ALTER TABLE publishing_settings ALTER COLUMN article_international_max DROP NOT NULL;
            END IF;
        END $$;
        """,
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
        "ALTER TABLE publishing_settings ADD COLUMN IF NOT EXISTS publish_frequency VARCHAR(20) NOT NULL DEFAULT 'daily'",
        "ALTER TABLE publishing_settings ADD COLUMN IF NOT EXISTS publish_weekday INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE publishing_settings ADD COLUMN IF NOT EXISTS publish_month_day INTEGER NOT NULL DEFAULT 1",
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
        """
        CREATE TABLE IF NOT EXISTS content_groups (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            group_key VARCHAR(80) NOT NULL,
            name VARCHAR(120) NOT NULL,
            content_mode VARCHAR(30) NOT NULL DEFAULT 'news',
            source_urls TEXT NOT NULL DEFAULT '',
            candidate_limit INTEGER NOT NULL DEFAULT 40,
            article_min INTEGER NOT NULL DEFAULT 0,
            article_target INTEGER NOT NULL DEFAULT 5,
            article_max INTEGER NOT NULL DEFAULT 8,
            position INTEGER NOT NULL DEFAULT 0,
            enabled BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_content_groups_tenant_key UNIQUE (tenant_id, group_key)
        )
        """,
        "ALTER TABLE content_groups ADD COLUMN IF NOT EXISTS content_mode VARCHAR(30) NOT NULL DEFAULT 'news'",
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
        f"""
        UPDATE content_groups
        SET source_urls = CASE group_key
            WHEN 'global' THEN '{AI_GLOBAL_SOURCE_URLS}'
            WHEN 'china' THEN '{AI_CHINA_SOURCE_URLS}'
            ELSE source_urls
        END
        WHERE tenant_id = 1
          AND group_key IN ('global', 'china')
          AND source_urls = ''
        """,
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
        """
        UPDATE content_groups
        SET content_mode = CASE group_key
            WHEN 'pet-health' THEN 'knowledge'
            WHEN 'pet-knowledge' THEN 'knowledge'
            WHEN 'pet-industry' THEN 'analysis'
            ELSE content_mode
        END
        WHERE tenant_id = 2
          AND group_key IN ('pet-health', 'pet-knowledge', 'pet-industry')
          AND content_mode = 'news'
        """,
        f"""
        UPDATE content_groups
        SET source_urls = CASE group_key
            WHEN 'pet-health' THEN '{PET_HEALTH_SOURCE_URLS}'
            WHEN 'pet-knowledge' THEN '{PET_KNOWLEDGE_SOURCE_URLS}'
            WHEN 'pet-industry' THEN '{PET_INDUSTRY_SOURCE_URLS}'
            ELSE source_urls
        END
        WHERE tenant_id = 2
          AND group_key IN ('pet-health', 'pet-knowledge', 'pet-industry')
          AND source_urls = ''
        """,
        f"""
        UPDATE content_groups
        SET source_urls = '{PET_HEALTH_SOURCE_URLS}'
        WHERE tenant_id = 2
          AND group_key = 'pet-health'
          AND source_urls NOT LIKE '%Vet Help Direct|https://vethelpdirect.com/vetblog/feed/%'
        """,
        f"""
        UPDATE content_groups
        SET source_urls = '{PET_KNOWLEDGE_SOURCE_URLS}'
        WHERE tenant_id = 2
          AND group_key = 'pet-knowledge'
          AND source_urls NOT LIKE '%Animal Wellness Magazine|https://animalwellnessmagazine.com/feed/%'
        """,
        """
        UPDATE content_groups
        SET enabled = false
        WHERE tenant_id = 2 AND group_key = 'main' AND source_urls = ''
        """,
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 1 REFERENCES tenants(id)",
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS group_key VARCHAR(80) NOT NULL DEFAULT 'global'",
        "UPDATE news_items SET group_key = CASE WHEN region = 'domestic' THEN 'china' ELSE 'global' END WHERE group_key = 'global' AND region IN ('domestic', 'international')",
        "UPDATE news_items SET group_key = 'main' WHERE tenant_id <> 1 AND group_key = 'global'",
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
        "CREATE INDEX IF NOT EXISTS ix_news_items_group_key ON news_items(group_key)",
        "CREATE INDEX IF NOT EXISTS ix_content_groups_tenant_id ON content_groups(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_news_items_dedup_status ON news_items(dedup_status)",
        "CREATE INDEX IF NOT EXISTS ix_news_items_duplicate_of_id ON news_items(duplicate_of_id)",
        "CREATE INDEX IF NOT EXISTS ix_articles_tenant_id ON articles(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_operation_tasks_tenant_id ON operation_tasks(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_operation_task_events_tenant_id ON operation_task_events(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_profiles_tenant_id ON blogger_profiles(tenant_id)",
        "ALTER TABLE blogger_profiles ADD COLUMN IF NOT EXISTS external_id VARCHAR(200)",
        "ALTER TABLE blogger_profiles ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(1000) NOT NULL DEFAULT ''",
        "ALTER TABLE blogger_profiles ADD COLUMN IF NOT EXISTS follower_count INTEGER NOT NULL DEFAULT 0",
        "CREATE INDEX IF NOT EXISTS ix_blogger_profiles_external_id ON blogger_profiles(external_id)",
        "ALTER TABLE blogger_posts ADD COLUMN IF NOT EXISTS content_type VARCHAR(30) NOT NULL DEFAULT 'image'",
        "ALTER TABLE blogger_posts ADD COLUMN IF NOT EXISTS transcript_text TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE blogger_posts ADD COLUMN IF NOT EXISTS asr_status VARCHAR(30) NOT NULL DEFAULT 'not_required'",
        "ALTER TABLE blogger_posts ADD COLUMN IF NOT EXISTS asr_error TEXT NOT NULL DEFAULT ''",
        """
        CREATE TABLE IF NOT EXISTS blogger_collection_runs (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            blogger_id INTEGER NOT NULL REFERENCES blogger_profiles(id),
            task_id VARCHAR REFERENCES operation_tasks(id),
            status VARCHAR(30) NOT NULL DEFAULT 'running',
            sample_limit INTEGER NOT NULL DEFAULT 50,
            comments_per_post INTEGER NOT NULL DEFAULT 20,
            asr_enabled BOOLEAN NOT NULL DEFAULT false,
            post_count INTEGER NOT NULL DEFAULT 0,
            hot_post_count INTEGER NOT NULL DEFAULT 0,
            comment_count INTEGER NOT NULL DEFAULT 0,
            tikhub_request_count INTEGER NOT NULL DEFAULT 0,
            tikhub_estimated_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            tikhub_cost_min_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            tikhub_cost_max_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            summary_json TEXT NOT NULL DEFAULT '{}',
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "ALTER TABLE blogger_collection_runs ADD COLUMN IF NOT EXISTS asr_enabled BOOLEAN NOT NULL DEFAULT false",
        """
        CREATE TABLE IF NOT EXISTS blogger_collection_posts (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            blogger_id INTEGER NOT NULL REFERENCES blogger_profiles(id),
            collection_run_id INTEGER NOT NULL REFERENCES blogger_collection_runs(id),
            post_id INTEGER NOT NULL REFERENCES blogger_posts(id),
            position INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_blogger_collection_posts UNIQUE (collection_run_id, post_id)
        )
        """,
        "ALTER TABLE blogger_distillation_runs ADD COLUMN IF NOT EXISTS collection_run_id INTEGER REFERENCES blogger_collection_runs(id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_posts_tenant_id ON blogger_posts(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_posts_blogger_id ON blogger_posts(blogger_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_collection_runs_tenant_id ON blogger_collection_runs(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_collection_runs_blogger_id ON blogger_collection_runs(blogger_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_collection_posts_collection_run_id ON blogger_collection_posts(collection_run_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_collection_posts_post_id ON blogger_collection_posts(post_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_distillation_runs_tenant_id ON blogger_distillation_runs(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_distillation_runs_blogger_id ON blogger_distillation_runs(blogger_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_skills_tenant_id ON blogger_skills(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_skills_blogger_id ON blogger_skills(blogger_id)",
        """
        CREATE TABLE IF NOT EXISTS xhs_publish_packages (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            blogger_id INTEGER NOT NULL REFERENCES blogger_profiles(id),
            skill_id INTEGER NOT NULL REFERENCES blogger_skills(id),
            content_type VARCHAR(40) NOT NULL,
            topic VARCHAR(300) NOT NULL,
            target_audience VARCHAR(300) NOT NULL DEFAULT '',
            content_goal VARCHAR(120) NOT NULL DEFAULT '',
            keywords VARCHAR(500) NOT NULL DEFAULT '',
            image_count_mode VARCHAR(30) NOT NULL DEFAULT 'auto',
            requested_image_count INTEGER,
            title VARCHAR(300) NOT NULL DEFAULT '',
            body_text TEXT NOT NULL DEFAULT '',
            hashtags_json TEXT NOT NULL DEFAULT '[]',
            cover_text VARCHAR(300) NOT NULL DEFAULT '',
            image_plan_json TEXT NOT NULL DEFAULT '[]',
            image_urls_json TEXT NOT NULL DEFAULT '[]',
            script_json TEXT NOT NULL DEFAULT '{}',
            status VARCHAR(30) NOT NULL DEFAULT 'generated',
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_xhs_publish_packages_tenant_id ON xhs_publish_packages(tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_xhs_publish_packages_blogger_id ON xhs_publish_packages(blogger_id)",
        "CREATE INDEX IF NOT EXISTS ix_xhs_publish_packages_skill_id ON xhs_publish_packages(skill_id)",
    ]
    with engine.begin() as connection:
        for statement in enum_statements:
            connection.execute(text(statement))
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
