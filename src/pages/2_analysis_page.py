# 標準ライブラリ
import streamlit as st
import os
import asyncio
import logging
from datetime import datetime
import threading
import pickle

# ローカルモジュール
import utils  # utilsモジュールをインポート

# from utils.database import DataManager
from autogen_agentchat.messages import (
    TextMessage,
    ToolCallRequestEvent,
    ToolCallExecutionEvent,
)
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def load_messages_from_file():
    """ファイルからメッセージと完了状態を読み込む"""
    # メッセージファイルの読み込み
    messages_file = "tmp/chat_messages.pkl"
    if os.path.exists(messages_file):
        try:
            # ファイルが空でないことを確認
            if os.path.getsize(messages_file) > 0:
                with open(messages_file, "rb") as f:
                    messages = pickle.load(f)
                    if messages:
                        st.session_state.current_analysis["messages"] = messages
                        logger.info(
                            f"{len(messages)}件のメッセージをファイルから読み込みました。"
                        )
        except (pickle.UnpicklingError, EOFError) as e:
            logger.warning(f"メッセージファイルのデシリアライズに失敗しました: {e}")
        except Exception as e:
            logger.error(f"メッセージファイルの読み込み中に予期せぬエラー: {e}")

    # 完了フラグの確認
    completed_file = "tmp/chat_completed.txt"
    if os.path.exists(completed_file):
        st.session_state.current_analysis["running"] = False
        st.session_state.current_analysis["status"] = "完了"
        logger.info("完了フラグを検知しました。分析を停止状態に設定します。")

    # エラーファイルの確認
    error_file = "tmp/chat_error.txt"
    if os.path.exists(error_file):
        with open(error_file, "r", encoding="utf-8") as f:
            error_message = f.read()
            if error_message:
                st.session_state.current_analysis["error"] = error_message
                st.session_state.current_analysis["running"] = False
                st.session_state.current_analysis["status"] = "エラー"
                st.error(f"分析中にエラーが発生しました: {error_message}")
                logger.error(f"エラーファイルを検知: {error_message}")


def enhanced_analysis_bot_page():
    """拡張された分析ボット画面"""
    st.header("🤖 マルチエージェント分析")
    st.subheader("📝 タスク入力")

    # セッション状態の初期化を最初に行う
    if "current_analysis" not in st.session_state:
        st.session_state.current_analysis = {
            "running": False,
            "messages": [],
            "start_time": None,
            "status": "待機中",
        }

    if "multiagent_history" not in st.session_state:
        st.session_state.multiagent_history = []

    # 実行中でない場合、ファイルから状態を読み込む
    if not st.session_state.current_analysis.get("running"):
        load_messages_from_file()

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

    selected_task = st.selectbox("サンプルタスクを選択", list(sample_tasks.keys()))

    task_input = st.text_area(
        "分析タスクを入力してください:",
        value=sample_tasks[selected_task],
        height=300,
        help="マルチエージェントが協力して解決するタスクを記述してください",
    )

    # 実行設定
    col1, col2 = st.columns(2)
    with col1:
        max_turns = st.slider("最大ターン数", 5, 50, 15)
    with col2:
        max_messages = st.slider("最大メッセージ数", 5, 50, 15)

    # 実行ボタン
    if st.button(
        "🚀 マルチエージェント分析を開始",
    ):
        # セッション状態を完全にリセット
        st.session_state.current_analysis = {
            "running": True,
            "messages": [],  # メッセージ配列を空にリセット
            "start_time": datetime.now(),
            "status": "実行中",
            "error": None,  # エラー状態もリセット
        }
        st.session_state.current_task = task_input  # タスクを保存

        # リアルタイム分析を開始（rerunの前に実行）
        run_realtime_multiagent_analysis(task_input, max_turns, max_messages)

        # 古いメッセージを表示しないようにページをリロード
        st.rerun()

    # 現在の分析状況を表示
    current_analysis = st.session_state.get("current_analysis", {})
    if current_analysis.get("running"):
        # 実行中なら、ファイルから最新の状態を読み込んでみる
        load_messages_from_file()
        display_realtime_analysis_status()

        # 実行中であれば、3秒待ってから再実行して状態を更新 (ポーリング)
        import time

        time.sleep(3)
        st.rerun()
    elif current_analysis.get("messages") and not current_analysis.get("running"):
        # 分析完了時の通知と自動更新促進
        st.success("🎉 分析が完了しました！下記の結果をご確認ください。")

    # 分析結果表示エリア
    if current_analysis.get("messages"):
        st.subheader("📊 リアルタイム分析結果")

        # メッセージが新しく追加された場合の通知
        message_count = len(current_analysis["messages"])
        if message_count > 0:
            st.success(f"✨ {message_count} 件のメッセージを受信しました")

        display_multiagent_chat(current_analysis["messages"])

        # 実行中でない場合はサマリーを表示
        if not current_analysis.get("running"):
            st.subheader("📈 実行サマリー")
            display_analysis_summary()

            # 履歴に保存
            save_analysis_to_history()


# マルチエージェント関連の関数
def display_realtime_analysis_status():
    """リアルタイム分析の状況を表示"""
    if "current_analysis" not in st.session_state:
        return

    analysis = st.session_state.current_analysis

    # ステータス表示
    status_container = st.container()
    with status_container:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if analysis.get("running"):
                st.markdown("🔄 **実行中**")
            else:
                st.markdown("✅ **完了**")

        with col2:
            elapsed = 0
            if analysis.get("start_time"):
                elapsed = (datetime.now() - analysis["start_time"]).total_seconds()
            st.metric("経過時間", f"{elapsed:.1f}秒")

        with col3:
            message_count = len(analysis.get("messages", []))
            st.metric("受信メッセージ数", message_count)

        with col4:
            if analysis.get("running"):
                # 停止ボタン
                if st.button("⏹️ 停止", key="stop_analysis_status"):
                    st.session_state.current_analysis["running"] = False
                    st.rerun()


def save_analysis_to_history():
    """現在の分析結果を履歴に保存"""
    if "current_analysis" not in st.session_state:
        return

    if "multiagent_history" not in st.session_state:
        st.session_state.multiagent_history = []

    analysis = st.session_state.current_analysis
    if analysis.get("messages") and analysis.get("start_time"):
        duration = (datetime.now() - analysis["start_time"]).total_seconds()

        # 重複チェック（同じタイムスタンプの履歴があるかチェック）
        timestamp = analysis["start_time"].strftime("%Y-%m-%d %H:%M:%S")
        existing = any(
            record.get("timestamp") == timestamp
            for record in st.session_state.multiagent_history
        )

        if not existing:
            st.session_state.multiagent_history.append(
                {
                    "timestamp": timestamp,
                    "task": getattr(st.session_state, "current_task", "不明なタスク")[
                        :100
                    ],
                    "duration": duration,
                    "result": f"分析完了 ({len(analysis['messages'])} メッセージ)",
                    "messages": analysis["messages"],
                }
            )


def display_analysis_summary():
    """分析のサマリー情報を表示"""
    if "current_analysis" not in st.session_state:
        return

    analysis = st.session_state.current_analysis

    col1, col2, col3 = st.columns(3)

    with col1:
        elapsed = 0
        if analysis.get("start_time"):
            elapsed = (datetime.now() - analysis["start_time"]).total_seconds()
        st.metric("総実行時間", f"{elapsed:.1f}秒")

    with col2:
        message_count = len(analysis.get("messages", []))
        st.metric("総メッセージ数", message_count)

    with col3:
        status = "完了" if message_count > 0 else "エラー"
        st.metric("ステータス", status)


def run_realtime_multiagent_analysis(task_input, max_turns, max_messages):
    """リアルタイムマルチエージェント分析の実行"""
    try:
        # tmpディレクトリの確保
        os.makedirs("tmp", exist_ok=True)

        # 以前のファイルを確実にクリーンアップ
        for file_name in ["chat_messages.pkl", "chat_completed.txt", "chat_error.txt"]:
            file_path = f"tmp/{file_name}"
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"一時ファイルを削除しました: {file_path}")
            except Exception as e:
                logger.warning(
                    f"一時ファイルの削除に失敗しました: {file_path} - {str(e)}"
                )

        # チームセットアップ
        chat = utils.autogen_agent.setup_multiagent_team()
        if not chat:
            st.error("チームのセットアップに失敗しました")
            st.session_state.current_analysis["running"] = False
            return

        # 設定更新
        chat.max_turns = max_turns
        chat.termination_condition = TextMentionTermination(
            "TERMINATE"
        ) | MaxMessageTermination(max_messages=max_messages)

        # シンプルなバックグラウンド実行
        def execute_chat_simple():
            """チャット実行スレッド（シンプル版）"""
            try:
                # 新しいイベントループを作成
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def run_chat():
                    message_count = 0
                    messages_buffer = []
                    try:
                        async for message in chat.run_stream(task=task_input):
                            # セッション状態の安全な確認
                            if hasattr(
                                st.session_state, "current_analysis"
                            ) and not st.session_state.current_analysis.get(
                                "running", False
                            ):
                                logger.info("実行停止が要求されました")
                                break

                            message_count += 1
                            messages_buffer.append(message)

                            # メッセージを受信するたびにファイルに保存
                            try:
                                with open("tmp/chat_messages.pkl", "wb") as f:
                                    pickle.dump(messages_buffer, f)
                                logger.info(
                                    f"リアルタイムメッセージ保存: {message_count} 件目"
                                )
                            except Exception as save_error:
                                logger.error(
                                    f"メッセージのリアルタイム保存エラー: {str(save_error)}"
                                )

                            # 少し待機（UI更新のため）
                            await asyncio.sleep(0.1)

                    except Exception as e:
                        logger.error(f"チャット実行中エラー: {str(e)}")
                        with open("tmp/chat_error.txt", "w", encoding="utf-8") as f:
                            f.write(str(e))
                    finally:
                        # 完了フラグを作成
                        with open("tmp/chat_completed.txt", "w", encoding="utf-8") as f:
                            f.write(f"completed:{message_count}")
                        logger.info(
                            f"チャット実行完了。総メッセージ数: {message_count}"
                        )

                loop.run_until_complete(run_chat())

            except Exception as e:
                logger.error(f"チャット実行エラー: {str(e)}")
                # エラー情報をファイルに保存
                with open("tmp/chat_error.txt", "w", encoding="utf-8") as f:
                    f.write(str(e))

        # バックグラウンドでチャット実行開始
        chat_thread = threading.Thread(target=execute_chat_simple)
        chat_thread.daemon = True
        chat_thread.start()

        # 進行状況の表示
        progress_container = st.container()
        with progress_container:
            st.info(
                "🚀 マルチエージェント分析を開始しました。「最新状況を確認」ボタンで進捗を確認できます。"
            )

            # 手動更新ボタンと停止ボタン
            col1, col2, col3 = st.columns([1, 1, 3])

            with col1:
                # 常に表示される更新ボタン
                refresh_clicked = st.button("🔄 最新状況を確認", key="refresh_status")
                if refresh_clicked:
                    # 共通関数を使ってファイルからメッセージを読み込み
                    load_messages_from_file()
                    st.rerun()

            with col2:
                if st.session_state.current_analysis.get("running"):
                    stop_clicked = st.button("⏹️ 分析停止", key="stop_analysis_main")
                    if stop_clicked:
                        st.session_state.current_analysis["running"] = False
                        st.success("分析停止を要求しました。")
                        st.rerun()
                else:
                    # 分析が完了している場合は無効化されたボタンを表示
                    st.button(
                        "⏹️ 分析停止", key="stop_analysis_main_disabled", disabled=True
                    )

            with col3:
                current_msg_count = len(
                    st.session_state.current_analysis.get("messages", [])
                )
                if st.session_state.current_analysis.get("running"):
                    st.info(f"⏳ 分析実行中... (受信済み: {current_msg_count} 件)")
                else:
                    if current_msg_count > 0:
                        st.success(
                            f"✅ 分析完了 - {current_msg_count} 件のメッセージを受信"
                        )
                    else:
                        st.warning("⚠️ 分析は完了しましたが、メッセージがありません")

    except Exception as e:
        logger.error(f"リアルタイム分析エラー: {str(e)}")
        st.error(f"分析の開始に失敗しました: {str(e)}")
        st.session_state.current_analysis["running"] = False
        st.session_state.current_analysis["error"] = str(e)


def get_agent_info(agent_name):
    """エージェント情報を取得（アイコンと色）"""
    agent_configs = {
        "PlanningAgent": {
            "icon": "🎯",
            "color": "#FF6B6B",
            "bg_color": "#FFE8E8",
            "display_name": "計画エージェント",
        },
        "WebSearchAgent": {
            "icon": "🔍",
            "color": "#4ECDC4",
            "bg_color": "#E8F9F8",
            "display_name": "検索エージェント",
        },
        "DataAnalystAgent": {
            "icon": "📊",
            "color": "#45B7D1",
            "bg_color": "#E8F4F8",
            "display_name": "分析エージェント",
        },
        "SelectorGroupChat": {
            "icon": "🤖",
            "color": "#96CEB4",
            "bg_color": "#F0F9F4",
            "display_name": "システム",
        },
    }

    return agent_configs.get(
        agent_name,
        {
            "icon": "🤖",
            "color": "#95A5A6",
            "bg_color": "#F8F9FA",
            "display_name": agent_name or "不明",
        },
    )


def get_message_type_info(message):
    if isinstance(message, TextMessage):
        """メッセージタイプの情報を取得"""
        return {
            "type": "text",
            "icon": "💬",
            "label": "テキストメッセージ",
            "color": "#2ECC71",
        }
    elif isinstance(message, ToolCallRequestEvent):

        """ツール呼び出しの情報を取得"""
        return {
            "type": "tool_call",
            "icon": "🔧",
            "label": "ツール呼び出し",
            "color": "#F39C12",
        }
    elif isinstance(message, ToolCallExecutionEvent):
        """ツール実行結果の情報を取得"""
        return {
            "type": "tool_result",
            "icon": "📤",
            "label": "ツール実行結果",
            "color": "#8E44AD",
        }
    else:
        return {
            "type": "unknown",
            "icon": "❓",
            "label": "不明なメッセージ",
            "color": "#95A5A6",
        }


def display_multiagent_chat(messages):
    """マルチエージェントの会話をチャット形式で表示"""
    # 実行中でない場合は表示をスキップ
    if not st.session_state.current_analysis.get("running", False) and not messages:
        return

    st.markdown("### 💬 エージェント会話")

    # メッセージが空の場合
    if not messages:
        st.info("💬 分析を開始しました。メッセージが表示されるまでお待ちください...")
        return

    # メッセージ数の表示
    st.info(f"📊 総メッセージ数: {len(messages)}")

    # メッセージを順番に表示
    for i, message in enumerate(messages):
        # メッセージの属性を安全に取得
        source = getattr(message, "source", None)
        content = getattr(message, "content", "")

        # contentが空の場合は、messageを文字列化
        if not content:
            content = str(message) if message is not None else ""

        # contentが文字列でない場合は文字列化
        if not isinstance(content, str):
            content = str(content)

        # sourceが辞書の場合、nameを取得
        if isinstance(source, dict):
            agent_name = source.get("name", "Unknown")
        elif hasattr(source, "name"):
            agent_name = source.name
        elif source:
            agent_name = str(source)
        else:
            agent_name = "システム"  # デフォルトのエージェント名

        # エージェント情報を取得
        agent_info = get_agent_info(agent_name)
        message_type_info = get_message_type_info(message)

        # メッセージコンテナ
        with st.container():
            # ヘッダー部分
            col1, col2, col3 = st.columns([1, 6, 1])

            with col1:
                st.markdown(
                    f"<div style='font-size: 2em;'>{agent_info['icon']}</div>",
                    unsafe_allow_html=True,
                )

            with col2:
                st.markdown(
                    f"""
                <div style='padding: 8px; border-radius: 8px; background-color: {agent_info['bg_color']};
                           border-left: 4px solid {agent_info['color']};'>
                    <div style='display: flex; align-items: center; margin-bottom: 4px;'>
                        <strong style='color: {agent_info['color']};'>{agent_info['display_name']}</strong>
                        <span style='margin-left: 10px; background-color: {message_type_info['color']};
                                   color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;'>
                            {message_type_info['icon']} {message_type_info['label']}
                        </span>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            with col3:
                st.markdown(
                    f"<div style='text-align: right; color: #666; font-size: 0.8em;'>#{i + 1}</div>",
                    unsafe_allow_html=True,
                )

            # メッセージ内容（展開可能）
            preview_text = content[:100] if len(content) > 100 else content
            with st.expander(
                f"詳細を表示 - {preview_text}{'...' if len(content) > 100 else ''}",
                expanded=False,
            ):
                # 内容を見やすく表示
                if len(content) > 1000:
                    st.text_area("メッセージ内容", content, height=200, disabled=True)
                elif any(
                    keyword in content
                    for keyword in ["```", "def ", "import ", "print("]
                ):
                    # コードっぽい内容の場合
                    st.code(content, language="python")
                else:
                    # 通常のテキスト
                    st.markdown(content)

                # メッセージの詳細情報
                with st.container():
                    st.markdown("**📝 メッセージ詳細:**")
                    details_col1, details_col2 = st.columns(2)

                    with details_col1:
                        st.write(f"**エージェント名**: {agent_name}")
                        st.write(f"**メッセージタイプ**: {message_type_info['label']}")

                    with details_col2:
                        st.write(f"**文字数**: {len(content):,}")
                        try:
                            line_count = (
                                len(content.splitlines())
                                if isinstance(content, str)
                                else 1
                            )
                            st.write(f"**行数**: {line_count}")
                        except Exception:
                            st.write("**行数**: 計算不可")

                        if hasattr(message, "models_usage"):
                            st.write("**モデル使用**: あり")
                        else:
                            st.write("**モデル使用**: なし")

            # 区切り線
            st.markdown("---")


# このページが直接実行された場合
if __name__ == "__main__":
    enhanced_analysis_bot_page()
