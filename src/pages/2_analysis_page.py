# 標準ライブラリ
import streamlit as st
import pandas as pd
import json
import os
import sys
import asyncio
import logging
import concurrent.futures
from datetime import datetime

# ローカルモジュール
from utils.database import DataManager

from autogen_agentchat.agents import (
    AssistantAgent,
)
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_core.models import ModelInfo
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from duckduckgo_search import DDGS
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def enhanced_analysis_bot_page():
    """拡張された分析ボット画面"""
    st.header("📊 分析ボット")

    tabs = st.tabs(
        ["ファイル分析", "チャット分析", "データエクスポート", "マルチエージェント分析"]
    )

    with tabs[0]:
        st.subheader("📁 ファイル分析")

        # ファイルアップロード
        uploaded_file = st.file_uploader(
            "分析するファイルをアップロードしてください",
            type=["csv", "xlsx", "json", "txt"],
        )

        if uploaded_file is not None:
            st.success(f"ファイル '{uploaded_file.name}' がアップロードされました。")

            # ファイルタイプに応じた分析
            if uploaded_file.type == "text/csv":
                df = pd.read_csv(uploaded_file)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("行数", len(df))
                    st.metric("列数", len(df.columns))
                with col2:
                    st.metric("データサイズ", f"{uploaded_file.size:,} bytes")
                    st.metric(
                        "欠損値",
                        f"{df.isnull().sum().sum():,} 個" if not df.empty else "0 個",
                    )

                # データプレビュー
                st.subheader("📋 データプレビュー")
                st.dataframe(df.head(10))

                # 基本統計情報
                if not df.empty:
                    st.subheader("📈 基本統計情報")
                    st.dataframe(df.describe())

                    # 列の詳細情報
                    st.subheader("🔍 列の詳細情報")
                    col_info = pd.DataFrame(
                        {
                            "データ型": df.dtypes,
                            "欠損値数": df.isnull().sum(),
                            "欠損値率": (df.isnull().sum() / len(df) * 100).round(2),
                            "ユニーク値数": df.nunique(),
                        }
                    )
                    st.dataframe(col_info)

            elif uploaded_file.type in ["application/json", "text/plain"]:
                try:
                    content = uploaded_file.read().decode("utf-8")
                    if uploaded_file.type == "application/json":
                        data = json.loads(content)
                        st.subheader("📋 JSON構造")
                        st.json(data)

                        st.metric("データサイズ", f"{len(content):,} 文字")
                        if isinstance(data, list):
                            st.metric("配列要素数", len(data))
                        elif isinstance(data, dict):
                            st.metric("キー数", len(data.keys()))
                    else:
                        st.subheader("📋 テキスト内容")
                        st.text_area("内容", content, height=300)

                        lines = content.split("\n")
                        st.metric("行数", len(lines))
                        st.metric("文字数", len(content))
                        st.metric("単語数", len(content.split()))

                except Exception as e:
                    st.error(f"ファイルの読み込みに失敗しました: {str(e)}")

    with tabs[1]:
        st.subheader("💬 チャット分析")

        # データマネージャーの初期化
        if "data_manager" not in st.session_state:
            DATA_DIR = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
            )
            st.session_state.data_manager = DataManager(DATA_DIR)

        data_manager = st.session_state.get("data_manager")
        if data_manager:
            chat_history = data_manager.load_chat_history()

            if chat_history:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("総チャット数", len(chat_history))
                with col2:
                    total_messages = sum(
                        len(chat.get("messages", [])) for chat in chat_history
                    )
                    st.metric("総メッセージ数", total_messages)
                with col3:
                    avg_messages = (
                        total_messages / len(chat_history) if chat_history else 0
                    )
                    st.metric("チャット当たり平均メッセージ数", f"{avg_messages:.1f}")

                # 最新のチャット活動
                st.subheader("📅 最新のチャット活動")
                recent_chats = sorted(
                    chat_history, key=lambda x: x.get("created_at", ""), reverse=True
                )[:5]

                for chat in recent_chats:
                    with st.expander(f"💬 {chat.get('title', '無題のチャット')}"):
                        st.write(f"📅 作成日時: {chat.get('created_at', '不明')}")
                        st.write(f"💬 メッセージ数: {len(chat.get('messages', []))}")

                        messages = chat.get("messages", [])
                        if messages:
                            st.write("最初のメッセージ:")
                            st.write(f"👤 {messages[0].get('content', '')[:100]}...")
            else:
                st.info("チャット履歴がありません。")

    with tabs[2]:
        st.subheader("📤 データエクスポート")

        # データマネージャーの初期化
        if "data_manager" not in st.session_state:
            DATA_DIR = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
            )
            st.session_state.data_manager = DataManager(DATA_DIR)

        data_manager = st.session_state.get("data_manager")

        export_type = st.selectbox(
            "エクスポートするデータを選択", ["チャット履歴", "プロンプトライブラリ"]
        )

        if st.button("📥 エクスポート", use_container_width=True):
            try:
                if export_type == "チャット履歴" and data_manager:
                    chat_history = data_manager.load_chat_history()
                    if chat_history:
                        # チャット履歴をCSV形式で変換
                        export_data = []
                        for chat in chat_history:
                            for message in chat.get("messages", []):
                                export_data.append(
                                    {
                                        "チャットID": chat.get("id"),
                                        "チャットタイトル": chat.get("title"),
                                        "作成日時": chat.get("created_at"),
                                        "ロール": message.get("role"),
                                        "内容": message.get("content"),
                                    }
                                )

                        if export_data:
                            df = pd.DataFrame(export_data)
                            csv = df.to_csv(index=False, encoding="utf-8-sig")
                            st.download_button(
                                label="💾 チャット履歴をCSVでダウンロード",
                                data=csv,
                                file_name="chat_history.csv",
                                mime="text/csv",
                            )
                        else:
                            st.warning("エクスポートするデータがありません。")
                    else:
                        st.warning("チャット履歴がありません。")

                elif export_type == "プロンプトライブラリ" and data_manager:
                    prompts = data_manager.load_prompts()
                    if prompts:
                        df = pd.DataFrame(prompts)
                        csv = df.to_csv(index=False, encoding="utf-8-sig")
                        st.download_button(
                            label="💾 プロンプトライブラリをCSVでダウンロード",
                            data=csv,
                            file_name="prompts.csv",
                            mime="text/csv",
                        )
                    else:
                        st.warning("プロンプトライブラリにデータがありません。")

            except Exception as e:
                st.error(f"エクスポートに失敗しました: {str(e)}")

    with tabs[3]:
        st.subheader("🤖 マルチエージェント分析")
        st.subheader("📝 タスク入力")

        # サンプルタスクの選択
        sample_tasks = {
            "生産スケジュール最適化": """以下のCSVデータは工場の生産スケジュールを表します。
L1からL5は生産ラインを、P1からP20は製品を表します。

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

このスケジュールでP19とP20の生産を停止し、P1の生産時間を最大化した場合の新しいスケジュールを提案してください。""",
            "データ分析タスク": """売上データの分析を行ってください。
1. 売上トレンドの分析
2. 季節性の検出
3. 予測モデルの作成
分析結果を日本語でレポートしてください。""",
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
            max_turns = st.slider("最大ターン数", 5, 50, 20)
        with col2:
            max_messages = st.slider("最大メッセージ数", 5, 50, 10)

        # 実行ボタン
        if st.button(
            "🚀 マルチエージェント分析を開始",
        ):
            with st.spinner("マルチエージェント分析を実行中..."):
                try:
                    result = run_multiagent_analysis(
                        task_input, max_turns, max_messages
                    )

                    st.subheader("📊 分析結果")

                    # 結果の表示
                    if isinstance(result, dict):
                        st.json(result)
                    else:
                        st.text(result)

                except Exception as e:
                    st.error(f"分析の実行中にエラーが発生しました: {str(e)}")
                    st.exception(e)

        # 実行履歴の表示
        if "multiagent_history" not in st.session_state:
            st.session_state.multiagent_history = []

        if st.session_state.multiagent_history:
            st.subheader("📋 実行履歴")
            for i, record in enumerate(
                reversed(st.session_state.multiagent_history[-5:])
            ):
                with st.expander(
                    f"実行 {len(st.session_state.multiagent_history) - i}: {record['timestamp']}"
                ):
                    st.text(f"タスク: {record['task'][:100]}...")
                    st.text(f"実行時間: {record['duration']:.1f}秒")
                    if record.get("result"):
                        st.text_area("結果", record["result"], height=200)


# マルチエージェント関連の関数
def search_duckduckgo(query: str) -> str:
    """DuckDuckGo検索関数"""
    try:
        print(f"[llm_agent] DuckDuckGo検索ツールを使用: query='{query}'")
        with DDGS() as ddgs:
            results = ddgs.text(query)
            return "\n".join([f"{r['title']}: {r['body']}" for r in results[:3]])
    except Exception as e:
        return f"検索エラー: {str(e)}"


def setup_multiagent_team():
    """マルチエージェントチームのセットアップ"""
    try:
        # 環境変数の読み込み
        load_dotenv("./.env_o4mini", override=True)

        # LLM設定（Azure OpenAI）
        model_info = ModelInfo(
            vision=False,
            function_calling=True,
            json_output=False,
            family="unknown",
            structured_output=True,
        )
        logger.info(
            f"""Azure OpenAIモデル情報: {model_info} AZURE_AI_AGENT_ENDPOINT=
                    {os.environ.get('AZURE_AI_AGENT_ENDPOINT')}  AZURE_API_KEY=
                    {os.environ.get('AZURE_API_KEY')} AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME=
                    {os.environ.get('AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME')} AZURE_API_VERSION=
                    {os.environ.get('AZURE_API_VERSION')}"""
        )

        model_client = AzureOpenAIChatCompletionClient(
            azure_endpoint=os.environ.get("AZURE_AI_AGENT_ENDPOINT"),
            api_key=os.environ.get("AZURE_API_KEY"),
            model=os.environ.get("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"),
            api_version=os.environ.get("AZURE_API_VERSION"),
            model_info=model_info,
        )

        # Reasoner（推論担当）エージェント
        planning_agent = AssistantAgent(
            name="PlanningAgent",
            description="タスクの計画と管理を行うエージェント",
            model_client=model_client,
            system_message="""あなたは計画エージェントです。
あなたの役割は複雑なタスクを小さな管理可能なサブタスクに分解し、チームメンバーに委任することです。

チームメンバー:
- WebSearchAgent: ウェブからの情報検索を専門とします
- DataAnalystAgent: データ分析、Python/SQLコードの実行を行います

計画フェーズの指示:
1. タスクを分析し、明確で実行可能なサブタスクに分解する
2. 各サブタスクを適切なエージェントに割り当てる
3. 結果を受け取った後の検証プロセスを計画する

検証フェーズ（結果受け取り後）:
- タスク要件に対して結果を検証する
- 結果が正しい場合、"TERMINATE"で終了する
- 結果が不正確な場合、具体的なフィードバックを提供する
**Critical Rule**: Do not use or reference the word "TERMINATE" in the planning phase. It is only used after verifying results.
必ず日本語で回答してください。""",
        )

        web_search_agent = AssistantAgent(
            "WebSearchAgent",
            description="ウェブ検索を行うエージェント",
            tools=[search_duckduckgo],
            model_client=model_client,
            system_message="""あなたはウェブ検索エージェントです。
search_duckduckgoツールを使用して情報を検索します。
一度に1回の検索を行い、結果に基づいた計算は行いません。
必ず日本語で回答してください。""",
        )

        execute_tool = PythonCodeExecutionTool(
            LocalCommandLineCodeExecutor(
                timeout=300, work_dir="tmp", cleanup_temp_files=False
            ),
        )

        data_analyst_agent = AssistantAgent(
            name="DataAnalystAgent",
            model_client=model_client,
            description="データ分析を行うエージェント",
            system_message="""あなたはデータ分析エージェントです。ReActフレームワーク（推論と行動）を使用してタスクを実行します。

各ターンで以下の形式に従ってください：
思考: [問題の分析、解決へのアプローチ]
行動: execute_tool([Pythonコード])
観察: [コード実行の結果]
思考: [結果の解釈と次のステップ]

複雑な問題を小さなステップに分解します。
コードを書く際は目的を明確にします。
実行結果を詳細に分析し、次の行動につなげます。
データが見えない場合は、必要なデータを明確に求めます。
必ず日本語で回答してください。""",
            tools=[execute_tool],
            reflect_on_tool_use=True,
        )

        selector_prompt = """会話の状況に応じて次のタスクを実行する role を選択することです。
## 次の話者の選択ルール

各 role の概要は以下です。
{roles}
次のタスクに選択可能な participants は以下です。

{participants}

以下のルールに従って、次のを選択してください。

- 会話履歴を確認し、次の会話に最適な role を選択します。role name のみを返してください。
- role は1つだけ選択してください。
- 他の role が作業を開始する前に、"PlannerAgent" にタスクを割り当て、サブタスクを計画してもらうことが必要です。
  - PlannerAgent はサブタスクの計画のみを行います。サブタスクの作業を依頼してはいけません。
- PlannerAgent が計画したサブタスクに応じて、role を選択します。
- タスクを完了するための必要な情報が揃ったと判断したら "SummaryAgent" に最終回答の作成を依頼します。

## 会話履歴

{history}
"""

        text_mention_termination = TextMentionTermination("TERMINATE")
        max_messages_termination = MaxMessageTermination(max_messages=10)
        termination = text_mention_termination | max_messages_termination

        # グループチャット構成
        chat = SelectorGroupChat(
            participants=[planning_agent, web_search_agent, data_analyst_agent],
            model_client=model_client,
            termination_condition=termination,
            max_turns=20,
            allow_repeated_speaker=False,
            selector_prompt=selector_prompt,
        )

        return chat

    except Exception as e:
        logger.error(f"マルチエージェントチームのセットアップ中にエラー: {str(e)}")
        st.error(f"マルチエージェントチームのセットアップエラー: {str(e)}")
        return None


async def run_multiagent_chat(chat, task):
    """マルチエージェントチャットの実行（非推奨 - run_multiagent_analysisを使用してください）"""
    # この関数は後方互換性のために残していますが、使用されません
    pass


def run_multiagent_analysis(task_input, max_turns, max_messages):
    """マルチエージェント分析のメイン実行関数"""
    try:
        start_time = datetime.now()

        # チームセットアップ
        chat = setup_multiagent_team()
        if not chat:
            return "チームのセットアップに失敗しました"

        # 最大ターン数とメッセージ数を更新
        chat.max_turns = max_turns
        chat.termination_condition = TextMentionTermination(
            "TERMINATE"
        ) | MaxMessageTermination(max_messages=max_messages)

        # 同期的にマルチエージェントチャットを実行
        def run_sync_multiagent_chat():
            """同期実行のためのラッパー関数"""

            async def async_chat():
                try:
                    messages = []
                    async for message in chat.run_stream(task=task_input):
                        messages.append(message)
                        # 進行状況をログに出力
                        logger.info(f"メッセージ受信: {len(messages)} 件目")
                    return messages
                except Exception as e:
                    logger.error(f"チャット実行エラー: {str(e)}")
                    raise e

            # 新しいイベントループで実行
            return asyncio.run(async_chat())

        # ThreadPoolExecutorを使用して非同期処理を実行
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_sync_multiagent_chat)
            try:
                messages = future.result(timeout=300)  # 5分タイムアウト
            except concurrent.futures.TimeoutError:
                st.error("処理がタイムアウトしました（5分）")
                return "タイムアウトエラー"
            except Exception as e:
                st.error(f"実行エラー: {str(e)}")
                return f"実行エラー: {str(e)}"

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 結果をセッション状態に保存
        if "multiagent_history" not in st.session_state:
            st.session_state.multiagent_history = []

        result_summary = f"分析完了 ({len(messages) if messages else 0} メッセージ)"

        st.session_state.multiagent_history.append(
            {
                "timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "task": task_input,
                "duration": duration,
                "result": result_summary,
                "messages": messages,
            }
        )

        return {
            "duration": duration,
            "message_count": len(messages) if messages else 0,
            "messages": messages,
            "summary": result_summary,
        }

    except Exception as e:
        logger.error(f"マルチエージェント分析エラー: {str(e)}")
        st.error(f"マルチエージェント分析エラー: {str(e)}")
        return f"エラー: {str(e)}"


# このページが直接実行された場合
if __name__ == "__main__":
    enhanced_analysis_bot_page()
