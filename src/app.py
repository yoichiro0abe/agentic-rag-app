import streamlit as st
import os
import sys
import logging

from opentelemetry.trace import NoOpTracerProvider
from autogen_core import SingleThreadedAgentRuntime

runtime = SingleThreadedAgentRuntime(tracer_provider=NoOpTracerProvider())

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# 現在のディレクトリをパスに追加
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from common import (
    setup_authentication,
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
        # ログイン画面では、サイドバーを非表示にする
        st.markdown(
            """
            <style>
                /* サイドバーのみ非表示に */
                section[data-testid="stSidebar"] {display: none}
                .stSidebar {display: none}
            </style>
            """,
            unsafe_allow_html=True,
        )

        # ログインページのタイトルとメッセージを中央に配置
        st.markdown(
            """
            <div style="text-align: center; padding: 2rem 0;">
                <h1>🤖 チャットボットアプリ</h1>
                <p>ログインしてご利用ください</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ログイン UI を表示し、戻り値を受け取ってセッションに保存
        login_result = authenticator.login("main")

        # login() の戻り値がNoneでないことを確認
        if login_result is not None:
            name, authentication_status, username = login_result

            # 認証が成功した場合
            if authentication_status:
                st.session_state["name"] = name
                st.session_state["authentication_status"] = authentication_status
                st.session_state["username"] = username
                st.rerun()
            elif authentication_status is False:
                st.error("🚫 ユーザー名またはパスワードが正しくありません")
                st.info("💡 再度ログイン情報を入力してください")
                # セッション状態をクリアしてログインページに戻る
                if "authentication_status" in st.session_state:
                    del st.session_state["authentication_status"]
                if "name" in st.session_state:
                    del st.session_state["name"]
                if "username" in st.session_state:
                    del st.session_state["username"]
                st.rerun()
    else:
        # サイドバーにログアウトボタンを追加
        with st.sidebar:
            authenticator.logout("🚪 ログアウト", "sidebar")

        # 統計情報を表示
        display_statistics()  # ページナビゲーションの設定（絶対パスを使用）
        pages_dir = os.path.join(current_dir, "pages")
        chatbot_page = st.Page(
            os.path.join(pages_dir, "1_chatbot_page.py"),
            title="チャットボット",
            icon="🤖",
            default=True,
        )
        analysis_page = st.Page(
            os.path.join(pages_dir, "2_analysis_page.py"), title="分析ボット", icon="📊"
        )
        chat_history_page = st.Page(
            os.path.join(pages_dir, "3_chat_history_page.py"),
            title="チャット履歴",
            icon="💬",
        )
        prompt_library_page = st.Page(
            os.path.join(pages_dir, "4_prompt_library_page.py"),
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
