"""manage 脚本无统一 SKILL_MANIFEST，此处声明参数表单元数据。"""

from __future__ import annotations

from typing import Any, TypedDict


class Field(TypedDict, total=False):
    name: str
    type: str  # string | integer | boolean | json
    label: str
    description: str
    required: bool
    enum: list[Any]
    default: Any
    widget: str  # textarea | file


def _f(
    name: str,
    typ: str,
    label: str,
    *,
    description: str = "",
    required: bool = False,
    enum: list[Any] | None = None,
    default: Any = None,
    widget: str | None = None,
) -> Field:
    d: Field = {
        "name": name,
        "type": typ,
        "label": label,
        "description": description,
        "required": required,
    }
    if enum is not None:
        d["enum"] = enum
    if default is not None:
        d["default"] = default
    if widget:
        d["widget"] = widget
    return d


# 每项: id, path, category, fields
MANAGE_TOOLS: list[dict[str, Any]] = [
    {
        "id": "scripts/manage/read/get_share_info.py",
        "path": "scripts/manage/read/get_share_info.py",
        "category": "manage-read",
        "label": "解析分享链接 get_share_info",
        "fields": [
            _f("url", "string", "分享 URL", required=True, description="pd.qq.com 分享链接"),
        ],
    },
    {
        "id": "scripts/manage/read/get_guild_info.py",
        "path": "scripts/manage/read/get_guild_info.py",
        "category": "manage-read",
        "label": "频道资料 get_guild_info",
        "fields": [_f("guild_id", "string", "频道 ID", required=True)],
    },
    {
        "id": "scripts/manage/read/get_guild_channel_list.py",
        "path": "scripts/manage/read/get_guild_channel_list.py",
        "category": "manage-read",
        "label": "版块列表 get_guild_channel_list",
        "fields": [_f("guild_id", "string", "频道 ID", required=True)],
    },
    {
        "id": "scripts/manage/read/get_guild_member_list.py",
        "path": "scripts/manage/read/get_guild_member_list.py",
        "category": "manage-read",
        "label": "成员列表 get_guild_member_list",
        "fields": [
            _f("guild_id", "string", "频道 ID", required=True),
            _f("next_page_token", "string", "翻页 token", required=False),
        ],
    },
    {
        "id": "scripts/manage/read/guild_member_search.py",
        "path": "scripts/manage/read/guild_member_search.py",
        "category": "manage-read",
        "label": "搜索成员 guild_member_search",
        "fields": [
            _f("guild_id", "string", "频道 ID", required=True),
            _f("keyword", "string", "关键词", required=False),
            _f("num", "integer", "返回数量", required=False, default=20),
            _f("pos", "string", "分页位置", required=False, default="0"),
        ],
    },
    {
        "id": "scripts/manage/read/get_user_info.py",
        "path": "scripts/manage/read/get_user_info.py",
        "category": "manage-read",
        "label": "用户资料 get_user_info",
        "fields": [
            _f("guild_id", "string", "频道 ID（查频道内成员时填）", required=False),
            _f("member_tinyid", "string", "成员 tiny_id", required=False),
        ],
    },
    {
        "id": "scripts/manage/read/get_join_guild_setting.py",
        "path": "scripts/manage/read/get_join_guild_setting.py",
        "category": "manage-read",
        "label": "加入设置 get_join_guild_setting",
        "fields": [_f("guild_id", "string", "频道 ID", required=True)],
    },
    {
        "id": "scripts/manage/read/search_guild_content.py",
        "path": "scripts/manage/read/search_guild_content.py",
        "category": "manage-read",
        "label": "搜索频道内容 search_guild_content",
        "fields": [
            _f("keyword", "string", "关键词", required=True),
            _f(
                "scope",
                "string",
                "范围",
                required=False,
                default="channel",
                enum=[
                    "all",
                    "channel",
                    "feed",
                    "author",
                    "全部",
                    "频道",
                    "帖子",
                    "作者",
                ],
                description="频道/帖子/作者等",
            ),
            _f(
                "rank_type",
                "string",
                "排序类型",
                required=False,
                default="CHANNEL_RANK_TYPE_SMART",
            ),
            _f("session_info", "string", "会话信息（翻页）", required=False),
            _f("disable_correction_query", "boolean", "禁用纠错", required=False, default=False),
        ],
    },
    {
        "id": "scripts/manage/read/get_my_join_guild_info.py",
        "path": "scripts/manage/read/get_my_join_guild_info.py",
        "category": "manage-read",
        "label": "我的频道列表 get_my_join_guild_info",
        "fields": [],
    },
    {
        "id": "scripts/manage/read/get_guild_share_url.py",
        "path": "scripts/manage/read/get_guild_share_url.py",
        "category": "manage-read",
        "label": "频道分享短链 get_guild_share_url",
        "fields": [_f("guild_id", "string", "频道 ID", required=True)],
    },
    {
        "id": "scripts/manage/read/preview_theme_private_guild.py",
        "path": "scripts/manage/read/preview_theme_private_guild.py",
        "category": "manage-read",
        "label": "预览创建主题频道编码 preview_theme_private_guild",
        "fields": [
            _f(
                "community_type",
                "string",
                "公开/私密",
                required=False,
                default="public",
                enum=["public", "private", "公开", "私密", "1", "2"],
            ),
            _f("theme", "string", "主题", required=False, description="与名称/简介二选一必填组合见脚本"),
            _f("guild_name", "string", "频道名", required=False),
            _f("guild_profile", "string", "简介", required=False, widget="textarea"),
            _f("image_path", "string", "封面图路径", required=True, widget="file"),
            _f("create_src", "string", "来源", required=False, default="pd-mcp"),
        ],
    },
    {
        "id": "scripts/manage/read/verify_qq_ai_connect_token.py",
        "path": "scripts/manage/read/verify_qq_ai_connect_token.py",
        "category": "manage-read",
        "label": "校验 Token / MCP verify",
        "fields": [],
    },
    {
        "id": "scripts/manage/write/join_guild.py",
        "path": "scripts/manage/write/join_guild.py",
        "category": "manage-write",
        "label": "加入频道 join_guild",
        "fields": [
            _f("guild_id", "string", "频道 ID", required=True),
            _f(
                "join_guild_comment",
                "string",
                "附言（部分验证方式）",
                required=False,
                widget="textarea",
            ),
            _f(
                "join_guild_answers",
                "json",
                "答案列表 JSON",
                required=False,
                widget="textarea",
                description='例如 [{"question":"...","answer":"..."}] 以脚本为准',
            ),
        ],
    },
    {
        "id": "scripts/manage/write/kick_guild_member.py",
        "path": "scripts/manage/write/kick_guild_member.py",
        "category": "manage-write",
        "label": "踢出成员 kick_guild_member",
        "fields": [
            _f("guild_id", "string", "频道 ID", required=True),
            _f("member_tinyid", "string", "单个成员 tiny_id", required=False),
            _f(
                "member_tinyids",
                "json",
                "多个 tiny_id JSON 数组",
                required=False,
                widget="textarea",
            ),
        ],
    },
    {
        "id": "scripts/manage/write/modify_member_shut_up.py",
        "path": "scripts/manage/write/modify_member_shut_up.py",
        "category": "manage-write",
        "label": "禁言/解禁 modify_member_shut_up",
        "fields": [
            _f("guild_id", "string", "频道 ID", required=True),
            _f("tiny_id", "string", "成员 tiny_id", required=True),
            _f(
                "time_stamp",
                "string",
                "禁言到期 Unix 秒（0 表示解禁）",
                required=True,
            ),
        ],
    },
    {
        "id": "scripts/manage/write/update_guild_info.py",
        "path": "scripts/manage/write/update_guild_info.py",
        "category": "manage-write",
        "label": "修改频道资料 update_guild_info",
        "fields": [
            _f("guild_id", "string", "频道 ID", required=True),
            _f("guild_name", "string", "新名称", required=False),
            _f("guild_profile", "string", "新简介", required=False, widget="textarea"),
        ],
    },
    {
        "id": "scripts/manage/write/upload_guild_avatar.py",
        "path": "scripts/manage/write/upload_guild_avatar.py",
        "category": "manage-write",
        "label": "上传频道头像 upload_guild_avatar",
        "fields": [
            _f("guild_id", "string", "频道 ID", required=True),
            _f("image_path", "string", "图片文件", required=True, widget="file"),
        ],
    },
    {
        "id": "scripts/manage/write/push_qq_msg.py",
        "path": "scripts/manage/write/push_qq_msg.py",
        "category": "manage-write",
        "label": "QQ 任务通知 push_qq_msg",
        "fields": [
            _f("task_name", "string", "任务名称", required=True),
            _f(
                "status",
                "string",
                "状态",
                required=True,
                enum=["success", "failed", "partial"],
            ),
            _f("detail", "string", "详情", required=False, widget="textarea"),
            _f("dry_run", "boolean", "仅预览", required=False, default=False),
        ],
    },
    {
        "id": "scripts/manage/write/create_theme_private_guild.py",
        "path": "scripts/manage/write/create_theme_private_guild.py",
        "category": "manage-write",
        "label": "创建主题频道 create_theme_private_guild",
        "fields": [
            _f(
                "community_type",
                "string",
                "公开/私密",
                required=False,
                default="public",
                enum=["public", "private", "公开", "私密", "1", "2"],
            ),
            _f("theme", "string", "主题", required=False),
            _f("guild_name", "string", "频道名", required=False),
            _f("guild_profile", "string", "简介", required=False, widget="textarea"),
            _f("image_path", "string", "封面图", required=True, widget="file"),
            _f("create_src", "string", "来源", required=False, default="pd-mcp"),
        ],
    },
]


def load_manage_tools() -> list[dict[str, Any]]:
    return list(MANAGE_TOOLS)
