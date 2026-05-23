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
        INSERT INTO content_profiles (
            tenant_id, publication_name, workspace_title, title_prefix, content_domain,
            editor_persona, audience, article_style, international_label, domestic_label,
            categories_json, image_style, updated_at
        )
        VALUES (
            1, 'AI 科技早报', 'AI 早报', 'AI科技早报 | ', 'AI、科技、模型、算力、企业应用',
            '你是严谨的 AI 科技新闻主编', '科技从业者、产品经理、投资人与 AI 关注者',
            '信息密度高，事实准确，带行业观察', '国际动态', '国内动态',
            '[]', '抽象科技视觉、信息图、芯片、网络、云与模型架构', NOW()
        )
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        """
        INSERT INTO wechat_accounts (tenant_id, app_id, app_secret, auto_send_draft, updated_at)
        VALUES (1, '', '', false, NOW())
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
