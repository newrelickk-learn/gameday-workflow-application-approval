"""表示言語の判定。Accept-Languageヘッダの形式ゆれを吸収できることを確認する。"""

from app.core.i18n import normalize_locale, set_current_locale, t


def test_normalize_locale_handles_header_variants():
    assert normalize_locale("en") == "en"
    assert normalize_locale("en-US,en;q=0.9") == "en"
    assert normalize_locale("ja-JP") == "ja"
    # 未対応の言語やヘッダ無しは日本語にする
    assert normalize_locale("fr") == "ja"
    assert normalize_locale(None) == "ja"


def test_messages_switch_by_locale():
    try:
        set_current_locale("en")
        assert t("approver_not_found") == "No approver was found"
        set_current_locale("ja")
        assert t("approver_not_found") == "承認者が見つかりません"
    finally:
        set_current_locale("ja")


def test_unknown_key_returns_the_key_itself():
    assert t("no_such_message") == "no_such_message"
