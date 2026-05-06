from __future__ import annotations


def dashboard_overview() -> dict:
    return {
        "platform": "xhs",
        "today_crawls": 128,
        "saved_notes": 2460,
        "pending_publishes": 7,
        "healthy_accounts": 5,
        "at_risk_accounts": 1,
        "hot_topics": [
            {"keyword": "春夏通勤穿搭", "notes": 42, "engagement": 183400},
            {"keyword": "低卡早餐", "notes": 36, "engagement": 92110},
            {"keyword": "小户型收纳", "notes": 31, "engagement": 77420},
        ],
        "recent_activity": [
            {"type": "crawl", "title": "关键词任务完成", "status": "success"},
            {"type": "ai", "title": "生成 4 篇改写草稿", "status": "done"},
            {"type": "publish", "title": "2 个定时发布等待执行", "status": "pending"},
        ],
    }


def sample_accounts() -> list[dict]:
    return [
        {"id": 1, "platform": "xhs", "sub_type": "pc", "nickname": "品牌内容号 A", "status": "healthy"},
        {"id": 2, "platform": "xhs", "sub_type": "creator", "nickname": "矩阵发布号 B", "status": "healthy"},
    ]


def sample_notes() -> list[dict]:
    return [
        {
            "id": 101,
            "platform": "xhs",
            "title": "爆款封面拆解：3 秒抓住用户注意力",
            "author": "运营研究员",
            "cover_url": "",
            "likes": 18420,
            "collects": 6110,
            "comments": 428,
            "tags": ["封面", "选题", "增长"],
        },
        {
            "id": 102,
            "platform": "xhs",
            "title": "小红书搜索流量关键词组合方法",
            "author": "内容增长笔记",
            "cover_url": "",
            "likes": 12960,
            "collects": 8032,
            "comments": 316,
            "tags": ["SEO", "关键词", "搜索"],
        },
    ]


def sample_tasks() -> list[dict]:
    return [
        {"id": "task-crawl-001", "platform": "xhs", "type": "crawl", "status": "running", "progress": 72},
        {"id": "task-ai-004", "platform": "xhs", "type": "ai_rewrite", "status": "pending", "progress": 0},
        {"id": "task-pub-011", "platform": "xhs", "type": "publish", "status": "failed", "progress": 100},
    ]


def sample_model_configs() -> list[dict]:
    return [
        {"id": 1, "name": "默认文本模型", "model_type": "text", "provider": "openai-compatible", "is_default": True},
        {"id": 2, "name": "封面图模型", "model_type": "image", "provider": "openai-compatible", "is_default": True},
    ]
