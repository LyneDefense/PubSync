"""一次性维护:重算 note_key + 归并重复笔记。

背景:早期 extract_note_key 在 biz_id 为空时回退到 external_id(note_id),而 note_id 会随端点漂移
—— 同一篇笔记在多次采集里被当成两篇入库(重复)。修好 extract_note_key(改用笔记卡规范 id)后,
本脚本把存量数据一并修正:

1. 对所有笔记,用 raw_json 里的笔记卡规范 id 重算 note_key;
2. 按 (blogger_id, note_key) 分组,重复组保留"最完整"的一条(有转写/图内文字 > 更新更晚 > id 更大),
   其余作为冗余删除:先重指向快照 post_ids、删采集批次成员(FK),再删冗余笔记行;
3. 重算每个博主 sample_count = 未排除(excluded)的笔记数。

用法(容器内):docker compose exec -T worker python - < scripts/merge_duplicate_posts.py
幂等:跑过一次后再跑,重复组为 0、note_key 已稳定,不会有额外改动。
"""

from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import delete, func, select

from app.blogger_distillation.service.extract.post import extract_note_key, normalize_detail_payload
from app.blogger_distillation.tikhub_client import unwrap_payload
from app.database import SessionLocal
from app.models import BloggerCollectionPost, BloggerPost, BloggerProfile, BloggerSnapshot


def _quality(post: BloggerPost):
    return (
        1 if (post.transcript_text or "").strip() else 0,
        1 if (post.image_text or "").strip() else 0,
        post.updated_at or post.created_at,
        post.id,
    )


def main() -> None:
    db = SessionLocal()
    try:
        posts = list(db.scalars(select(BloggerPost)))
        recomputed = 0
        for post in posts:
            try:
                detail = json.loads(post.raw_json or "{}")
            except json.JSONDecodeError:
                detail = {}
            if not detail:
                continue
            card = normalize_detail_payload(unwrap_payload(detail), detail)
            new_key = extract_note_key(card, detail, post.external_id or "")
            if new_key and new_key != (post.note_key or ""):
                post.note_key = new_key
                recomputed += 1
        db.flush()

        groups: dict[tuple[int, str], list[BloggerPost]] = defaultdict(list)
        for post in posts:
            key = (post.note_key or "").strip()
            if key:
                groups[(post.blogger_id, key)].append(post)

        drop_ids: list[int] = []
        remap: dict[int, int] = {}
        for rows in groups.values():
            if len(rows) < 2:
                continue
            rows.sort(key=_quality, reverse=True)
            keep = rows[0]
            for dup in rows[1:]:
                drop_ids.append(dup.id)
                remap[dup.id] = keep.id

        print(f"recomputed note_key: {recomputed}; duplicate rows to remove: {len(drop_ids)}")

        if drop_ids:
            for snap in db.scalars(select(BloggerSnapshot)):
                try:
                    ids = json.loads(snap.post_ids_json or "[]")
                except json.JSONDecodeError:
                    ids = []
                out: list[int] = []
                seen: set[int] = set()
                changed = False
                for raw in ids:
                    mapped = remap.get(int(raw), int(raw))
                    if mapped in seen:
                        changed = True
                        continue
                    seen.add(mapped)
                    out.append(mapped)
                    if mapped != int(raw):
                        changed = True
                if changed:
                    snap.post_ids_json = json.dumps(out, ensure_ascii=False)
            db.execute(delete(BloggerCollectionPost).where(BloggerCollectionPost.post_id.in_(drop_ids)))
            db.execute(delete(BloggerPost).where(BloggerPost.id.in_(drop_ids)))
            db.flush()

        fixed_counts = 0
        for blogger in db.scalars(select(BloggerProfile)):
            count = db.scalar(
                select(func.count())
                .select_from(BloggerPost)
                .where(BloggerPost.blogger_id == blogger.id, BloggerPost.status != "excluded")
            )
            if blogger.sample_count != count:
                blogger.sample_count = count
                fixed_counts += 1
        db.commit()
        print(f"removed duplicates: {len(drop_ids)}; bloggers with corrected sample_count: {fixed_counts}; done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
