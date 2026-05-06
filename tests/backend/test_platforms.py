from backend.app.core.platforms import PlatformId, get_platforms


def test_platform_registry_marks_xhs_enabled_and_others_coming_soon():
    platforms = get_platforms()
    by_id = {platform.id: platform for platform in platforms}

    assert by_id[PlatformId.XHS].enabled is True
    assert by_id[PlatformId.XHS].accent_color == "#ff2442"
    assert by_id[PlatformId.DOUYIN].enabled is False
    assert by_id[PlatformId.KUAISHOU].status == "coming_soon"
    assert set(by_id) == {
        PlatformId.XHS,
        PlatformId.DOUYIN,
        PlatformId.KUAISHOU,
        PlatformId.WEIBO,
        PlatformId.XIANYU,
        PlatformId.TAOBAO,
    }
