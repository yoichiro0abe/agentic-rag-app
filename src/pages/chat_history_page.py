import streamlit as st
import os
import sys

# パスの設定を改善
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from utils.database import DataManager
except ImportError as e:
    st.error(f"モジュールのインポートエラー: {e}")
    st.stop()


def chat_history_page():
    """チャット履歴画面"""
    st.header("💬 チャット履歴")

    # データマネージャーの初期化
    if "data_manager" not in st.session_state:
        DATA_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
        )
        st.session_state.data_manager = DataManager(DATA_DIR)

    data_manager = st.session_state.get("data_manager")
    if not data_manager:
        st.error("データマネージャーの初期化に失敗しました。")
        return

    # チャット履歴の読み込み
    chat_history = data_manager.load_chat_history()

    if not chat_history:
        st.info("チャット履歴がありません。")
        return

    # サイドバーでフィルタリング
    with st.sidebar:
        st.subheader("🔍 フィルター")

        # 検索
        search_query = st.text_input("チャット内容で検索")

        # 日付範囲フィルター
        st.write("作成日でフィルター")
        use_date_filter = st.checkbox("日付フィルターを使用")

        if use_date_filter:
            # 日付範囲の設定（簡易版）
            all_dates = [
                chat.get("created_at", "")
                for chat in chat_history
                if chat.get("created_at")
            ]
            if all_dates:
                st.date_input("開始日")
                st.date_input("終了日")

    # 検索フィルターの適用
    filtered_chats = chat_history

    if search_query:
        filtered_chats = []
        for chat in chat_history:
            # チャットタイトルまたはメッセージ内容で検索
            if search_query.lower() in chat.get("title", "").lower():
                filtered_chats.append(chat)
                continue

            # メッセージ内容で検索
            for message in chat.get("messages", []):
                if search_query.lower() in message.get("content", "").lower():
                    filtered_chats.append(chat)
                    break

    # 統計情報の表示
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("総チャット数", len(chat_history))
    with col2:
        st.metric("表示中のチャット数", len(filtered_chats))
    with col3:
        total_messages = sum(len(chat.get("messages", [])) for chat in filtered_chats)
        st.metric("総メッセージ数", total_messages)

    # ソートオプション
    sort_option = st.selectbox(
        "並び替え",
        ["新しい順", "古い順", "メッセージ数の多い順", "メッセージ数の少ない順"],
    )

    # ソートの適用
    if sort_option == "新しい順":
        filtered_chats = sorted(
            filtered_chats, key=lambda x: x.get("created_at", ""), reverse=True
        )
    elif sort_option == "古い順":
        filtered_chats = sorted(filtered_chats, key=lambda x: x.get("created_at", ""))
    elif sort_option == "メッセージ数の多い順":
        filtered_chats = sorted(
            filtered_chats, key=lambda x: len(x.get("messages", [])), reverse=True
        )
    elif sort_option == "メッセージ数の少ない順":
        filtered_chats = sorted(
            filtered_chats, key=lambda x: len(x.get("messages", []))
        )

    # チャット履歴の表示
    st.markdown("---")
    for i, chat in enumerate(filtered_chats):
        with st.expander(
            f"💬 {chat.get('title', '無題のチャット')} "
            f"({len(chat.get('messages', []))} メッセージ)"
        ):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.write(f"📅 **作成日時:** {chat.get('created_at', '不明')}")
                st.write(f"🆔 **チャットID:** {chat.get('id', '不明')}")

            with col2:
                # チャットを読み込むボタン
                if st.button(f"📖 読み込む", key=f"load_{i}"):
                    st.session_state.chat_messages = chat.get("messages", [])
                    st.session_state.current_chat_id = chat.get("id")
                    st.success("チャットを読み込みました！")
                    st.info("チャットボットページに移動してください。")

            with col3:
                # チャットを削除するボタン
                if st.button(f"🗑️ 削除", key=f"delete_{i}"):
                    if data_manager.delete_chat_session(chat.get("id")):
                        st.success("チャットを削除しました！")
                        st.rerun()
                    else:
                        st.error("チャットの削除に失敗しました。")

            # メッセージの表示
            st.markdown("**メッセージ履歴:**")
            messages = chat.get("messages", [])

            # メッセージが多い場合は最初の数個だけ表示
            display_limit = 5
            display_messages = messages[:display_limit]

            for msg in display_messages:
                role_icon = "👤" if msg.get("role") == "user" else "🤖"
                role_name = "ユーザー" if msg.get("role") == "user" else "アシスタント"

                st.markdown(f"**{role_icon} {role_name}:**")
                content = msg.get("content", "")
                # 長いメッセージは切り詰め
                if len(content) > 200:
                    content = content[:200] + "..."
                st.markdown(f"> {content}")
                st.markdown("")

            # 残りのメッセージがある場合の表示
            if len(messages) > display_limit:
                remaining = len(messages) - display_limit
                st.info(f"他に {remaining} 件のメッセージがあります。")

    # チャット履歴が空の場合
    if not filtered_chats and search_query:
        st.warning("検索条件に一致するチャットが見つかりませんでした。")


# このページが直接実行された場合
if __name__ == "__main__":
    chat_history_page()
