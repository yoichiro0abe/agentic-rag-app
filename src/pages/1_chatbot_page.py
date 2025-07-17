import streamlit as st
import os
import sys
import re
import uuid
import asyncio as _asyncio
from utils.database import DataManager
from utils.autogen_agent import setup_agent
from utils.tools import timer
from datetime import datetime
import pytz
import logging
from utils.tools import check_content

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# パスの設定を改善
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@timer
def display_custom_chat_message(role: str, content: str):
    """カスタムアイコンでチャットメッセージを表示"""
    # ユーザーの場合のみカスタム画像を使用、その他は元のままの表示
    if role == "user":
        # ユーザーのみ花王のマークを使用
        with st.chat_message(role, avatar="demo_kao.jpeg"):
            display_message_with_images(content)
    else:
        type_of_content = check_content(content)
        logger.info(f"Content type: {type_of_content}")
        if type_of_content:
            with st.expander("📋 Agent呼び出しの詳細", expanded=False):
                st.write(content)
        else:
            with st.chat_message(role, avatar="avanade.png"):
                display_message_with_images(content)


@timer
def display_message_with_images(content: str):
    """メッセージ内の画像パスを検出し、画像とテキストを表示する"""
    # [image: path/to/image.png] 形式のタグを検出
    image_pattern = r"\[image: (.*?)\]"

    # メッセージを画像タグで分割
    parts = re.split(image_pattern, content)

    for i, part in enumerate(parts):
        if i % 2 == 1:  # 奇数番目の要素が画像パス
            image_path = part.strip()
            # URLかローカルパスかを判定
            if image_path.startswith("http"):
                st.image(image_path, width=600)  # URLの場合は直接表示
            elif os.path.exists(image_path):
                st.image(image_path)
            else:
                st.markdown(part)
        else:  # 偶数番目の要素がテキスト
            if part.strip():
                st.markdown(part)


@timer
def start_new_chat():
    """新しい会話を開始する"""
    # 現在のチャットを保存してから新しい会話を開始
    if st.session_state.chat_messages:
        save_current_chat()

    # チャット状態をリセット
    st.session_state.chat_messages = []
    st.session_state.current_chat_id = None

    # エージェントを完全にリセット
    reset_success = reset_agent_state()

    if not reset_success:
        st.error("エージェントのリセットに失敗しました。")
        return

    # 画面を再読み込みして新しい会話状態を反映
    st.rerun()


@timer
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


@timer
def enhanced_chatbot_page():
    """拡張されたチャットボット画面"""
    # セッション状態の初期化を最初に実行
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # 現在のチャットIDの初期化
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None

    # エージェントの初期化（セッション固有）
    if "agent" not in st.session_state:
        # セッション固有のエージェント識別子を生成
        import uuid

        if "session_id" not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())

        st.session_state.agent = setup_agent()
        logger.info(
            f"新しいエージェントを初期化しました。セッションID: {st.session_state.session_id}"
        )

    # データマネージャーとチャットボットヘルパーの初期化
    if "data_manager" not in st.session_state:
        DATA_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
        )
        st.session_state.data_manager = DataManager(DATA_DIR)

    st.header("🤖 チャットボット")

    # ヘッダー部分にボタンを配置
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        # 現在のチャット状態を表示
        if st.session_state.chat_messages:
            message_count = len(st.session_state.chat_messages)
            st.caption(f"💬 メッセージ数: {message_count}")
        else:
            st.caption("💭 新しい会話を開始してください")
    with col3:
        if st.button("🆕 新しい会話", key="header_new_chat", type="secondary"):
            start_new_chat()

    # サイドバーの設定
    with st.sidebar:
        st.subheader("⚙️ チャット設定")

        # 新しい会話ボタン
        if st.button("🆕 新しい会話", use_container_width=True, type="primary"):
            start_new_chat()

        st.divider()

        # 応答モード選択（エージェントのみ）
        response_mode = st.selectbox(
            "応答モード",
            ["エージェントモード"],
        )

    # チャット履歴を表示
    for message in st.session_state.chat_messages:
        role = message.get("role", "assistant")
        content = message.get("content", "")
        logger.info(f"Displaying message: {role} - {content}")

        display_custom_chat_message(role, content)

    # チャット入力セクション
    st.divider()

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
                logger.error("エージェントが初期化されていません。")
                response = "エージェントの初期化に失敗しました。"
            else:
                logger.info(
                    f"エージェントを使用して応答生成開始。セッションID: {st.session_state.get('session_id', 'unknown')}"
                )
                # タイムゾーンを日本時間に設定
                # jst = pytz.timezone("Asia/Tokyo")
                # current_time_str = datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S JST")
                current_time_str = "2025-06-20 12:00:00 JST"  # デバッグ用の固定時間

                # ユーザーのプロンプトに現在時刻の情報を付与
                enhanced_prompt = f"""{prompt}

######現在の時刻: {current_time_str}######"""
                # 非同期ストリーミング応答を逐次表示
                response_chunks = []
                streaming = True  # ストリーミング応答を利用
                with st.spinner("エージェント応答生成中..."):
                    try:

                        async def stream_response():
                            async for msg in agent.run_stream(task=enhanced_prompt):
                                logger.info(f"Received message: {msg}")
                                content = getattr(msg, "content", "")
                                # contentがJSONシリアライズ不可能なオブジェクトの場合、文字列に変換
                                # FunctionCallオブジェクトなどが含まれるリストを安全に処理するため
                                if not isinstance(
                                    content, (str, int, float, bool, type(None))
                                ):
                                    content = str(content)

                                if content != "":
                                    role = getattr(msg, "source", "assistant")
                                    response_chunks.append(content)
                                    if (
                                        role != "user"
                                    ):  # userのメッセージは発話時に格納している
                                        st.session_state.chat_messages.append(
                                            {"role": role, "content": content}
                                        )

                                    if role == "user":
                                        display_custom_chat_message("user", content)
                                    else:
                                        display_custom_chat_message(
                                            "assistant", content
                                        )

                        # イベントループで実行
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
            display_custom_chat_message("assistant", response)

        # チャット履歴を保存
        save_current_chat()


@timer
def reset_agent_state():
    """エージェントの状態を完全にリセット"""
    try:
        if "agent" in st.session_state:
            old_session_id = st.session_state.get("session_id", "unknown")
            logger.info(f"古いエージェント削除中。セッションID: {old_session_id}")
            del st.session_state.agent

        # 新しいセッションIDを生成
        st.session_state.session_id = str(uuid.uuid4())

        # 新しいエージェントを作成
        st.session_state.agent = setup_agent()
        logger.info(
            f"新しいエージェントを作成しました。セッションID: {st.session_state.session_id}"
        )

        return True
    except Exception as e:
        logger.error(f"エージェントリセット中にエラー: {e}")
        return False


# このページが直接実行された場合
if __name__ == "__main__":
    enhanced_chatbot_page()

# use context7
