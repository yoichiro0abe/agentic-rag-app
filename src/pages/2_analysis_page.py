# 標準ライブラリ
import streamlit as st
import os
import asyncio
import logging
from datetime import datetime
import pytz
import utils.autogen_agent
from utils.tools import display_multiagent_chat_message

from autogen_agentchat.messages import TextMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def start_new_analysis_chat():
    """新しい分析チャットを開始する"""
    st.session_state.analysis_messages = []
    st.session_state.multi_agent_team = utils.autogen_agent.setup_multiagent_team()
    logger.info("新しい分析チャットセッションを開始しました。")
    st.rerun()


def enhanced_analysis_bot_page():
    """拡張された分析ボット画面（対話形式）"""
    st.header("🤖 マルチエージェント分析")

    # --- セッション状態の初期化 ---
    if "analysis_messages" not in st.session_state:
        st.session_state.analysis_messages = []
    if "multi_agent_team" not in st.session_state:
        st.session_state.multi_agent_team = utils.autogen_agent.setup_multiagent_team()
        if not st.session_state.multi_agent_team:
            st.error("マルチエージェントチームの初期化に失敗しました。")
            return

    # --- サイドバー ---
    with st.sidebar:
        st.subheader("⚙️ 分析設定")
        if st.button("🆕 新しい分析を開始", use_container_width=True, type="primary"):
            start_new_analysis_chat()

        st.divider()
        # サンプルタスクの選択
        sample_tasks = {
            "生産スケジュール最適化": """## 以下のCSVデータは初期の生産スケジュールを表します。
### L1,L2,L3,L4,L5はラインを表す。
### P1からP20は商品を表す。

時間帯,L1,L2,L3,L4,L5
0:00-1:00,P1,P2,P3,P4,P5
1:00-2:00,P1,P2,P3,P4,P5
2:00-3:00,P1,P2,P3,P4,P5
3:00-4:00,P1,P2,P3,P4,P5
4:00-5:00,P1,P2,P3,P4,P5
5:00-6:00,P1,P2,切替,切替,切替
6:00-7:00,P1,P2,P6,P7,P8
7:00-8:00,P1,P2,P6,P7,P8
8:00-9:00,P1,P2,P6,P7,P8
9:00-10:00,P1,P2,P6,P7,P8
10:00-11:00,切替,切替,P6,P7,P8
11:00-12:00,P9,P10,切替,切替,切替
12:00-13:00,P9,P10,P11,P15,P16
13:00-14:00,P9,P10,P11,P15,P16
14:00-15:00,P9,P10,P11,P15,P16
15:00-16:00,P9,P10,P11,P15,P16
16:00-17:00,切替,切替,P11,切替,切替
17:00-18:00,P14,P12,切替,P17,P18
18:00-19:00,P14,P12,P13,P17,P18
19:00-20:00,P14,P12,P13,P17,P18
20:00-21:00,P14,P12,P13,P17,P18
21:00-22:00,P14,P12,P13,切替,切替
22:00-23:00,,,P13,P19,P20
23:00-24:00,,,,P19,P20

## データの説明
- **生産時間**:
  - P1, P2: 各10時間生産
  - P3, P4, P5,P6,P7,P8,P9,P10,P11,P12,P13,P14: 各5時間生産
  - P15, P16, P17, P18: 各4時間生産
  - P19, P20:各2時間生産
  **CSVデータ商品が入ってない枠は空いています。使用しても構いません。**
- **切替時間**: 同一ラインで商品が替わったとき、切替時間(1時間)が発生します。
  **同一ラインで同じ商品を連続して生産する場合、切替時間は発生しません。
- **ラインの割り当て**: 各ラインは24時間使用できる。

# 初期のスケジュールからP19,P20の生産をやめて、P1を生産する時間を最も長くした場合のスケジュールを考えてください。

空き時間（商品が入っていない枠）はP1の生産時間増加や他の商品の生産に活用できます。
P2からP18の生産時間は、プロンプトに記載された時間（P2: 10時間、P3-P14: 5時間、P15-P18: 4時間）を維持し、
生産時刻やライン割り当てを自由に変更可能です。
商品の生産の順番は自由に入れ替えて構いません。

変更後のスケジュールのP1の生産時間を述べてください。
変更後のスケジュールをマークダウン形式で提示してください""",
            "カスタムタスク": "",
        }
        selected_task_name = st.selectbox(
            "サンプルタスクを選択", list(sample_tasks.keys())
        )
        if st.button("サンプルタスクを適用"):
            st.session_state.sample_task_content = sample_tasks[selected_task_name]
            st.rerun()

    # --- チャット履歴の表示 ---
    if not st.session_state.analysis_messages:
        st.info(
            "分析したいタスクを下のチャット欄に入力してください。サイドバーのサンプルタスクも利用できます。"
        )

    for i, msg in enumerate(st.session_state.analysis_messages):
        display_multiagent_chat_message(msg, i)

    # --- チャット入力 ---
    prompt_value = ""
    # サンプルタスクが適用された場合は履歴に追加
    if (
        "sample_task_content" in st.session_state
        and st.session_state.sample_task_content
    ):
        sample_content = st.session_state.sample_task_content
        user_message = TextMessage(source="user", content=sample_content)
        st.session_state.analysis_messages.append(user_message)
        del st.session_state.sample_task_content
        st.rerun()

    # チャット入力欄
    prompt = st.chat_input(
        "分析タスクを入力してください...",
        key="analysis_input",
        on_submit=lambda: setattr(st.session_state, "user_input_triggered", True),
    )

    if prompt:
        # ユーザーメッセージを履歴に追加
        user_message = TextMessage(source="user", content=prompt)
        st.session_state.analysis_messages.append(user_message)
        display_multiagent_chat_message(
            user_message, len(st.session_state.analysis_messages) - 1
        )

        # タイムゾーンを日本時間に設定
        jst = pytz.timezone("Asia/Tokyo")
        current_time_str = datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S JST")
        enhanced_prompt = f"""現在の時刻は {current_time_str} です。この情報を元に、以下のタスクを実行してください。

タスク: {prompt}
"""
        # エージェントの応答をストリーミングで処理
        with st.spinner("🤖 マルチエージェントが応答を生成中です..."):
            chat = st.session_state.multi_agent_team
            try:

                async def stream_response():
                    async for message in chat.run_stream(task=enhanced_prompt):
                        logger.info(f"Received message: {message}")
                        if message.source == "user":
                            continue
                        st.session_state.analysis_messages.append(message)
                        display_multiagent_chat_message(
                            message, len(st.session_state.analysis_messages) - 1
                        )
                        await asyncio.sleep(0.1)

                asyncio.run(stream_response())
            except Exception as e:
                error_message = f"分析中にエラーが発生しました: {str(e)}"
                logger.error(error_message)
                st.error(error_message)
                error_msg_obj = TextMessage(source="システム", content=error_message)
                st.session_state.analysis_messages.append(error_msg_obj)
                display_multiagent_chat_message(
                    error_msg_obj, len(st.session_state.analysis_messages) - 1
                )
        st.rerun()


if __name__ == "__main__":
    enhanced_analysis_bot_page()
