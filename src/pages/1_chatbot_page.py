import streamlit as st
import os
import sys
import re
from utils.database import DataManager
from utils.autogen_agent import setup_agent
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# パスの設定を改善
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def display_message_with_images(content: str):
    """メッセージ内の画像パスを検出し、画像とテキストを表示する"""
    # [image: path/to/image.png] 形式のタグを検出
    image_pattern = r"\[image: (.*?)\]"

    # メッセージを画像タグで分割
    parts = re.split(image_pattern, content)

    for i, part in enumerate(parts):
        if i % 2 == 1:  # 奇数番目の要素が画像パス
            image_path = part
            if os.path.exists(image_path):
                st.image(image_path)
            else:
                st.warning(f"画像ファイルが見つかりません: {image_path}")
        else:  # 偶数番目の要素がテキスト
            if part.strip():
                st.markdown(part)


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

    # エージェントの初期化
    if "agent" not in st.session_state:
        st.session_state.agent = setup_agent()

    # データマネージャーとチャットボットヘルパーの初期化
    if "data_manager" not in st.session_state:
        DATA_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
        )
        st.session_state.data_manager = DataManager(DATA_DIR)

    # チャットメッセージの初期化
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # 現在のチャットIDの初期化
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None

    # サイドバーの設定
    with st.sidebar:
        st.subheader("⚙️ チャット設定")

        # 応答モード選択（エージェントのみ）
        response_mode = st.selectbox(
            "応答モード",
            ["エージェントモード"],
        )

    # チャット履歴を表示
    for message in st.session_state.chat_messages:
        role = message.get("role", "assistant")
        logger.info(f"Displaying message: {role} - {message['content']}")
        if role == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant"):
                display_message_with_images(message["content"])

    # ユーザー入力
    if prompt := st.chat_input("メッセージを入力してください..."):
        # ユーザーメッセージを追加（自動表示はループで行われます）
        st.session_state.chat_messages.append({"role": "user", "content": prompt})

        # ChatBotHelperを使用して応答を生成
        response = ""
        streaming = False

        if response_mode == "エージェントモード":
            agent = st.session_state.get("agent")
            if not agent:
                response = "エージェントの初期化に失敗しました。"
            else:
                # 非同期ストリーミング応答を逐次表示
                response_chunks = []
                streaming = True  # ストリーミング応答を利用
                with st.spinner("エージェント応答生成中..."):
                    try:

                        async def stream_response():
                            async for msg in agent.run_stream(task=prompt):
                                logger.info(f"Received message: {msg}")
                                content = getattr(msg, "content", "")
                                if content != "":
                                    role = getattr(msg, "source", "assistant")
                                    response_chunks.append(content)
                                    st.session_state.chat_messages.append(
                                        {"role": role, "content": content}
                                    )

                                    if role == "user":
                                        with st.chat_message("user"):
                                            st.markdown(content)
                                    else:
                                        with st.chat_message("assistant"):
                                            display_message_with_images(content)

                        # イベントループで実行
                        import asyncio as _asyncio

                        _asyncio.run(stream_response())
                        response = "".join(response_chunks)
                    except Exception as e:
                        response = f"エージェント応答生成エラー: {e}"

        else:
            response = "申し訳ありませんが、エージェントモードのみ対応しています。"

        # アシスタントの応答を追加
        if not streaming:
            st.session_state.chat_messages.append(
                {"role": "assistant", "content": response}
            )
            with st.chat_message("assistant"):
                display_message_with_images(response)

        # チャット履歴を保存
        save_current_chat()


# このページが直接実行された場合
if __name__ == "__main__":
    enhanced_chatbot_page()
