from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from flask import Flask, jsonify, render_template, request

try:
    import instaloader
except ImportError:  # pragma: no cover
    instaloader = None


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "analytics.db"

app = Flask(__name__)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                followers INTEGER NOT NULL,
                follows INTEGER NOT NULL,
                media_count INTEGER NOT NULL,
                captured_at TEXT NOT NULL
            )
            """
        )


def extract_username(instagram_url_or_username: str) -> str:
    text = instagram_url_or_username.strip()

    if re.fullmatch(r"[A-Za-z0-9._]+", text):
        return text

    match = re.search(r"instagram\.com/([A-Za-z0-9._]+)/?", text)
    if not match:
        raise ValueError("InstagramのURLまたはユーザー名が不正です。")

    username = match.group(1)
    if username.lower() in {"reel", "p", "explore", "stories"}:
        raise ValueError("プロフィールURLを入力してください。")

    return username


def save_snapshot(username: str, followers: int, follows: int, media_count: int) -> None:
    captured_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO profile_snapshots (username, followers, follows, media_count, captured_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username.lower(), followers, follows, media_count, captured_at),
        )


def get_previous_snapshot(username: str) -> dict[str, Any] | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT followers, follows, media_count, captured_at
            FROM profile_snapshots
            WHERE username = ?
            ORDER BY captured_at DESC
            LIMIT 1 OFFSET 1
            """,
            (username.lower(),),
        ).fetchone()

    if not row:
        return None

    return {
        "followers": row["followers"],
        "follows": row["follows"],
        "media_count": row["media_count"],
        "captured_at": row["captured_at"],
    }


def build_instaloader() -> Any:
    if instaloader is None:
        raise RuntimeError(
            "instaloaderが未インストールです。`pip install -r requirements.txt` を実行してください。"
        )

    loader = instaloader.Instaloader(
        download_comments=False,
        download_geotags=False,
        download_pictures=False,
        download_videos=False,
        save_metadata=False,
        quiet=True,
    )

    session_id = os.getenv("INSTAGRAM_SESSIONID")
    if session_id:
        loader.context._session.cookies.set("sessionid", session_id)

    return loader


def fetch_profile_metrics(username: str, post_limit: int = 12) -> dict[str, Any]:
    loader = build_instaloader()
    profile = instaloader.Profile.from_username(loader.context, username)

    posts = []
    for index, post in enumerate(profile.get_posts()):
        if index >= post_limit:
            break

        posts.append(
            {
                "shortcode": post.shortcode,
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "caption": (post.caption or "")[:120],
                "timestamp": post.date_utc.isoformat(),
                "likes": post.likes,
                "comments": post.comments,
            }
        )

    avg_likes = round(mean([p["likes"] for p in posts]), 2) if posts else 0
    avg_comments = round(mean([p["comments"] for p in posts]), 2) if posts else 0
    engagement_rate = (
        round(((avg_likes + avg_comments) / profile.followers) * 100, 2)
        if profile.followers
        else 0
    )

    save_snapshot(
        username=profile.username,
        followers=profile.followers,
        follows=profile.followees,
        media_count=profile.mediacount,
    )

    previous = get_previous_snapshot(profile.username)
    follower_growth = None
    if previous:
        follower_growth = {
            "absolute": profile.followers - previous["followers"],
            "since": previous["captured_at"],
        }

    return {
        "profile": {
            "username": profile.username,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "followers": profile.followers,
            "following": profile.followees,
            "posts": profile.mediacount,
            "is_verified": profile.is_verified,
            "profile_url": f"https://www.instagram.com/{profile.username}/",
        },
        "metrics": {
            "engagement_rate_percent": engagement_rate,
            "avg_likes": avg_likes,
            "avg_comments": avg_comments,
            "sampled_posts": len(posts),
            "follower_growth": follower_growth,
            "note": "フォロワー増加数は本アプリで保存した前回スナップショットとの差分です。",
        },
        "posts": posts,
    }


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze() -> Any:
    payload = request.get_json(silent=True) or {}
    raw = payload.get("url_or_username", "")

    try:
        username = extract_username(raw)
        result = fetch_profile_metrics(username)
        return jsonify({"ok": True, "data": result})
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc)}), 400


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
