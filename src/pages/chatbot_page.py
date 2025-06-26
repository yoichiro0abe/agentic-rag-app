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
    from utils.chatbot_helper import ChatBotHelper
except ImportError as e:
    st.error(f"モジュールのインポートエラー: {e}")
    st.stop()


def save_current_chat():
    """現在のチャットを保存"""
    if st.session_state.chat_messages:
        data_manager = st.session_state.get("data_manager")
        if not data_manager:
            return

        # 最初のメッセージから50文字のプレビューを作成
        title = "新しいチャット"
        if st.session_state.chat_messages:
            first_message = st.session_state.chat_messages[0]["content"]
            title = (
                first_message[:20] + "..." if len(first_message) > 20 else first_message
            )

        # 既存のチャットを更新または新規追加
        if st.session_state.current_chat_id:
            data_manager.update_chat_session(
                st.session_state.current_chat_id,
                title=title,
                messages=st.session_state.chat_messages,
            )
        else:
            chat_data = data_manager.add_chat_session(
                title, st.session_state.chat_messages
            )
            st.session_state.current_chat_id = chat_data.get("id")


def enhanced_chatbot_page():
    """拡張されたチャットボット画面"""
    st.header("🤖 チャットボット")

    # データマネージャーとチャットボットヘルパーの初期化
    if "data_manager" not in st.session_state:
        DATA_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
        )
        st.session_state.data_manager = DataManager(DATA_DIR)
    if "chatbot_helper" not in st.session_state:
        st.session_state.chatbot_helper = ChatBotHelper()

    # サイドバーの設定
    with st.sidebar:
        st.subheader("⚙️ チャット設定")

        # 応答モード選択
        response_mode = st.selectbox(
            "応答モード",
            ["シンプル", "スマートモード", "プロンプト使用"],
        )

        # プロンプト選択（プロンプト使用モード時）
        selected_prompt = None
        if response_mode == "プロンプト使用":
            data_manager = st.session_state.get("data_manager")
            if data_manager:
                prompts = data_manager.load_prompts()
                if prompts:
                    prompt_options = {
                        f"{prompt['title']} ({prompt['category']})": prompt
                        for prompt in prompts
                    }
                    selected_option = st.selectbox(
                        "プロンプトを選択", list(prompt_options.keys())
                    )
                    selected_prompt = prompt_options.get(selected_option)

        # 新しいチャットボタン
        if st.button("🆕 新しいチャット", use_container_width=True):
            st.session_state.chat_messages = []
            st.session_state.current_chat_id = None
            st.rerun()

    # チャット履歴を表示
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ユーザー入力
    if prompt := st.chat_input("メッセージを入力してください..."):
        # ユーザーメッセージを追加
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # ChatBotHelperを使用して応答を生成
        chatbot_helper = st.session_state.get("chatbot_helper")
        response = ""

        if response_mode == "シンプル":
            response = f"申し訳ありませんが、現在はエコー機能のみです。あなたのメッセージ: {prompt}"

        elif response_mode == "スマートモード":
            intent = chatbot_helper.detect_intent(prompt)
            response = chatbot_helper.generate_response(prompt, intent)

            # 類似した過去の会話を表示
            data_manager = st.session_state.get("data_manager")
            if data_manager:
                similar_convs = chatbot_helper.find_similar_conversations(
                    prompt, data_manager.load_chat_history()
                )
                if similar_convs:
                    with st.expander("類似した過去の会話"):
                        for conv in similar_convs[:3]:
                            st.text(f"類似度: {conv['similarity']:.2f}")
                            st.text(f"過去の質問: {conv['user_message'][:100]}...")
                            if "assistant_response" in conv:
                                st.text(
                                    f"過去の回答: {conv['assistant_response'][:100]}..."
                                )
                            st.markdown("---")

        elif response_mode == "プロンプト使用" and selected_prompt:
            response = f"[{selected_prompt['title']}を使用]\n\n{selected_prompt['content']}\n\nユーザーの質問: {prompt}\n\n申し訳ありませんが、実際のAI応答機能は実装されていません。"

        else:
            response = "申し訳ありませんが、適切な応答を生成できませんでした。"

        # アシスタントの応答を追加
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": response}
        )
        with st.chat_message("assistant"):
            st.markdown(response)

        # チャット履歴を保存
        save_current_chat()

        # 応答候補を表示
        if response_mode == "スマートモード":
            suggestions = chatbot_helper.get_response_suggestions(prompt)
            if suggestions:
                with st.expander("他の応答候補"):
                    for suggestion in suggestions:
                        if st.button(
                            suggestion,
                            key=f"suggestion_{len(st.session_state.chat_messages)}_{suggestion[:20]}",
                        ):
                            st.session_state.chat_messages.append(
                                {"role": "assistant", "content": suggestion}
                            )
                            save_current_chat()
                            st.rerun()


# このページが直接実行された場合
if __name__ == "__main__":
    enhanced_chatbot_page()
