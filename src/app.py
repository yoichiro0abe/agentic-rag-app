import streamlit as st
import os
import sys

# 現在のディレクトリをパスに追加
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from common import (
    setup_authentication,
    show_welcome_message,
    display_statistics,
    initialize_managers,
    apply_custom_styles,
)

# ページ設定
st.set_page_config(
    page_title="チャットボットアプリ",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    """メイン関数"""
    # カスタムCSSを適用
    apply_custom_styles()

    # データマネージャーとチャットボットヘルパーを初期化
    initialize_managers()

    # 認証の設定
    authenticator = setup_authentication()

    # 認証状態の確認
    auth_status = st.session_state.get("authentication_status", False)
    if auth_status is not True:
        st.error("ユーザー名とパスワードを入力してください")
        # ログイン UI を表示（引数は setup_authentication の実装に合わせてください）
        authenticator.login("main")
        return
    else:
        # ログイン成功時の処理
        show_welcome_message()

        # サイドバーにログアウトボタンを追加
        with st.sidebar:
            st.title("🤖 チャットボットアプリ")
            st.write(f"ようこそ, {st.session_state['name']}さん！")
            st.markdown("---")

            if st.button("🚪 ログアウト", use_container_width=True):
                # 認証ステータスをクリアして再実行
                st.logout()

        # 統計情報を表示
        display_statistics()  # ページナビゲーションの設定（絶対パスを使用）
        pages_dir = os.path.join(current_dir, "pages")
        chatbot_page = st.Page(
            os.path.join(pages_dir, "chatbot_page.py"),
            title="チャットボット",
            icon="🤖",
            default=True,
        )
        analysis_page = st.Page(
            os.path.join(pages_dir, "analysis_page.py"), title="分析ボット", icon="📊"
        )
        chat_history_page = st.Page(
            os.path.join(pages_dir, "chat_history_page.py"),
            title="チャット履歴",
            icon="💬",
        )
        prompt_library_page = st.Page(
            os.path.join(pages_dir, "prompt_library_page.py"),
            title="プロンプトライブラリ",
            icon="📚",
        )  # ナビゲーションの設定
        try:
            pg = st.navigation(
                [chatbot_page, analysis_page, chat_history_page, prompt_library_page]
            )
            # 選択されたページを実行
            pg.run()
        except Exception as e:
            st.error(f"ページの読み込み中にエラーが発生しました: {e}")
            st.info("ページを再読み込みしてください。")


if __name__ == "__main__":
    main()
