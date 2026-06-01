from __future__ import annotations

from typing import Any


IDENTITY_FIELDS = {
    "userid",
    "user_id",
    "userId",
    "nickname",
    "nick_name",
    "avatar",
    "images",
    "ip_location",
    "ipLocation",
    "location",
    "user",
    "userInfo",
}


def anonymize_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reader_map: dict[str, str] = {}
    reader_counter = 0

    def speaker_for(comment: dict[str, Any]) -> str:
        nonlocal reader_counter
        if is_author(comment):
            return "作者"
        user_id = extract_user_id(comment)
        if user_id and user_id in reader_map:
            return reader_map[user_id]
        reader_counter += 1
        speaker = f"读者{reader_counter}"
        if user_id:
            reader_map[user_id] = speaker
        return speaker

    def clean_one(comment: dict[str, Any]) -> dict[str, Any]:
        speaker = speaker_for(comment)
        clean = {key: value for key, value in comment.items() if key not in IDENTITY_FIELDS}
        clean["speaker"] = speaker
        clean["is_author"] = speaker == "作者"
        for key in ("sub_comments", "subComments"):
            sub_comments = comment.get(key)
            if isinstance(sub_comments, list):
                clean["sub_comments"] = [clean_one(item) for item in sub_comments if isinstance(item, dict)]
        return clean

    return [clean_one(item) for item in comments if isinstance(item, dict)]


def is_author(comment: dict[str, Any]) -> bool:
    if comment.get("is_author") is True:
        return True
    tags = str(comment.get("show_tags") or comment.get("showTags") or "")
    return "is_author" in tags


def extract_user_id(comment: dict[str, Any]) -> str:
    for key in ("userid", "user_id", "userId"):
        value = comment.get(key)
        if value:
            return str(value)
    for parent_key in ("user", "userInfo"):
        user = comment.get(parent_key)
        if isinstance(user, dict):
            for key in ("userid", "user_id", "userId"):
                value = user.get(key)
                if value:
                    return str(value)
    return ""
