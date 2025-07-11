from autogen_agentchat.agents import (
    AssistantAgent,
)
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_core.models import ModelInfo
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from dotenv import load_dotenv
import logging
import os
import sys
import asyncio

# ローカルモジュールのインポート
from .tools import (
    get_work_directory,
    upload_image_to_blob,
    search_duckduckgo,
    create_execute_tool,
    load_erp_data,
    load_material_cost_breakdown,
    load_mes_total_data,
    load_mes_loss_data,
)

# OS別の設定
if sys.platform == "win32":
    # Windows環境の設定
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Windows環境でのみ環境変数ファイルを読み込み
    load_dotenv("./.env_o4mini", override=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def setup_multiagent_team():
    """マルチエージェントチームのセットアップ"""
    try:
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
            description="タスクの計画と管理と結果の検証を行うエージェント",
            model_client=model_client,
            system_message="""
    You are a planning agent.
Your job is to break down complex tasks into smaller, manageable subtasks and delegate them to team members. You do not execute tasks or verify results yourself during the planning phase.
Your team members are:
    WebSearchAgent: Specializes in information retrieval from the web.
    DataAnalystAgent: Parses instructions, converts them into mathematical or statistical formulas and Python/SQL code, executes data analysis, and delivers efficient, accurate results.

**Planning Phase Instructions**:
1. Analyze the task and break it into clear, actionable subtasks.
2. Assign each subtask to the appropriate agent using the format:
   - 1. <agent> : <task>
3. For machine learning tasks, ensure the plan includes ALL necessary steps:
   - Data loading and preprocessing (one-hot encoding, feature engineering)
   - Model training with proper hyperparameter tuning
   - Model evaluation and validation
   - Final prediction for specified conditions
   - Results summary and interpretation
4. Make sure to provide enough detail so DataAnalystAgent can complete each step independently.
5. Your plan should only include task assignments and a description of what will be verified later.

**Verification Phase** (after receiving results):
- Verify the results against the task requirements.
- Check that all requested outputs have been provided (e.g., final prediction values).
- If results are complete and correct, conclude with "TERMINATE".
- If results are incomplete or incorrect, provide specific, practical feedback to the responsible agent for completion/revisions.
- DO NOT terminate until the COMPLETE task has been accomplished.

**Critical Rule**: Do not use or reference the word "TERMINATE" in the planning phase. It is only used after verifying complete results.
必ず日本語で回答してください。
""",
            #             system_message="""あなたは計画エージェントです。
            # あなたの役割は複雑なタスクを小さな管理可能なサブタスクに分解し、チームメンバーに委任することです。
            # チームメンバー:
            # - WebSearchAgent: ウェブからの情報検索を専門とします
            # - DataAnalystAgent: データ分析、Python/SQLコードの実行を行います
            # 計画フェーズの指示:
            # 1. タスクを分析し、明確で実行可能なサブタスクに分解する
            # 2. 各サブタスクを適切なエージェントに割り当てる
            # 3. 結果を受け取った後の検証プロセスを計画する
            # 検証フェーズ（結果受け取り後）:
            # - タスク要件に対して結果を検証する
            # - 結果が正確な場合、人間にわかりやすく結果をサマリして、"TERMINATE"と発言して終了させてください。
            # - 結果が不正確な場合、具体的なフィードバックを提供する
            # **Critical Rule**: Do not use or reference the word "TERMINATE" in the planning phase. It is only used after verifying results.
            # 必ず日本語で回答してください。""",
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

        execute_tool = create_execute_tool()

        # 作業ディレクトリを取得してプロンプトに埋め込む
        work_dir = get_work_directory()

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
データが見えない場合は、必要なデータをユーザに求めます。
**重要**: ツール実行結果の `is_error` が `True` の場合は、コードが失敗しています。その原因を分析し、コードを修正して再実行してください。成功と誤認してはいけません。
**グラフ生成とアップロードのルール:**
1.  **思考**: グラフの保存先フルパスを決定します。作業ディレクトリは `{work_dir}` です。このパスとファイル名を組み合わせてください。（例: `'{work_dir}/img/my_graph.png'`）
2.  **行動 (コード実行)**: `execute_tool` を使い、決定したフルパスにグラフを保存するPythonコードを実行します。
3.  **思考**: コード実行後、`upload_image_to_blob` ツールを呼び出して、保存した画像をアップロードする計画を立てます。
4.  **行動 (ツール呼び出し)**: `upload_image_to_blob` ツールを呼び出します。引数 `file_path` には、ステップ1で決定したフルパスをそのまま指定します。
5.  **観察**: アップロードツールの実行結果から、画像の公開URLを取得します。
6.  **応答**: 応答メッセージに、取得した公開URLを `[image: 公開URL]` の形式で正確に含めてください。
matplotlibで日本語グラフを作成する際は、以下のコードを実行してください：
```python
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path

# プロジェクトに含まれるカスタムフォント（ipaexg.ttf）を使用
current_dir = Path(__file__).resolve()
for parent in current_dir.parents:
    font_path = parent / "assets" / "fonts" / "ipaexg.ttf"
    if font_path.exists():
        fm.fontManager.addfont(str(font_path))
        font_prop = fm.FontProperties(fname=str(font_path))
        plt.rcParams["font.family"] = font_prop.get_name()
        break

plt.rcParams["axes.unicode_minus"] = False
必ず日本語で回答してください。""",
            tools=[execute_tool, upload_image_to_blob],
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
- 他の role が作業を開始する前に、"PlanningAgent" にタスクを割り当て、サブタスクを計画してもらうことが必要です。
  - PlanningAgent はサブタスクの計画のみを行います。サブタスクの作業を依頼してはいけません。
- PlanningAgent が計画したサブタスクに応じて、role を選択します。
- タスクを完了するための必要な情報が揃ったと判断したら "PlanningAgent" に最終回答の作成を依頼します。

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
        return None


def setup_agent():
    """エージェントのセットアップ"""
    try:
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

        # 環境変数を取得して確認
        azure_endpoint = os.environ.get("AZURE_AI_AGENT_ENDPOINT")
        api_key = os.environ.get("AZURE_API_KEY")
        model_deployment = os.environ.get("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME")
        api_version = os.environ.get("AZURE_API_VERSION")
        logger.info(
            f"Azure endpoint={azure_endpoint}, deployment={model_deployment}, api_version={api_version}"
        )
        # 必須項目チェック
        if not azure_endpoint or not api_key or not model_deployment:
            logger.error(
                "環境変数が設定されていません: AZURE_AI_AGENT_ENDPOINT/API_KEY/MODEL_DEPLOYMENT_NAME を確認してください"
            )
            return None
        # クライアント初期化
        model_client = AzureOpenAIChatCompletionClient(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            model=model_deployment,
            api_version=api_version,
            model_info=model_info,
        )

        execute_tool = create_execute_tool()

        # 作業ディレクトリを取得してプロンプトに埋め込む
        work_dir = get_work_directory()

        data_analyst_agent = AssistantAgent(
            name="DataAnalystAgent",
            model_client=model_client,
            description="マルチステップで思考・行動するアナリストAI",
            system_message="""あなたはマルチステップで思考・行動するアナリストAIです。
ユーザーの目標を達成するために、以下のループを繰り返してください：

1. 状況を把握し、目標と制約を明確にする
2. 実行計画を立てる（必要ならユーザーに確認）
3. 計画に従ってツールを使って実行する
4. 結果を評価し、成功か失敗かを判断する
   **重要**: ツール実行結果の `is_error` が `True` の場合は、コードが失敗しています。その原因を分析し、コードを修正して再実行してください。成功と誤認してはいけません。
5. 失敗した場合は原因を分析し、改善策を立てて再実行する
6. 成功したら次のステップに進むか、完了を報告する

次のステップに進む場合はユーザに次のステップに進んでよいか確認してください。

**グラフ生成とアップロードのルール:**
1.  **思考**: グラフの保存先フルパスを決定します。作業ディレクトリは `{work_dir}` です。このパスとファイル名を組み合わせてください。（例: `'{work_dir}/img/my_graph.png'`）
2.  **行動 (コード実行)**: `execute_tool` を使い、決定したフルパスにグラフを保存するPythonコードを実行します。
3.  **思考**: コード実行後、`upload_image_to_blob` ツールを呼び出して、保存した画像をアップロードする計画を立てます。
4.  **行動 (ツール呼び出し)**: `upload_image_to_blob` ツールを呼び出します。引数 `file_path` には、ステップ1で決定したフルパスをそのまま指定します。
5.  **観察**: アップロードツールの実行結果から、画像の公開URLを取得します。
6.  **応答**: 応答メッセージに、取得した公開URLを `[image: 公開URL]` の形式で正確に含めてください。
matplotlibで日本語グラフを作成する際は、以下のコードを実行してください：
```python
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path

# プロジェクトに含まれるカスタムフォント（ipaexg.ttf）を使用
current_dir = Path(__file__).resolve()
for parent in current_dir.parents:
    font_path = parent / "assets" / "fonts" / "ipaexg.ttf"
    if font_path.exists():
        fm.fontManager.addfont(str(font_path))
        font_prop = fm.FontProperties(fname=str(font_path))
        plt.rcParams["font.family"] = font_prop.get_name()
        break

plt.rcParams["axes.unicode_minus"] = False
```
**生産費用についてのデータの取得:**
変動費、固定費が必要な場合は、`load_erp_data`ツールを使用してください。このツールは年月のリストとSKUのリストを指定してERPデータをフィルタリングし、DataFrameの情報を返します。
材料費の内訳が必要な場合は、`load_material_cost_breakdown`ツールを使用してください。このツールは年月のリストとSKUのリストを指定してERPデータをフィルタリングし、DataFrameの情報を返します。
**MESデータの取得:**
MESの総生産データが必要な場合は、`load_mes_total_data`ツールを使用してください。このツールは年月のリストとSKUのリストを指定してMESデータをフィルタリングし、DataFrameの情報を返します。
MESのロスデータが必要な場合は、`load_mes_loss_data`ツールを使用してください。このツールは年月のリストとSKUのリストを指定してMESデータをフィルタリングし、DataFrameの情報を返します。
**注意点:**
必ず日本語で回答してください。""",
            tools=[
                execute_tool,
                upload_image_to_blob,
                load_erp_data,
                load_material_cost_breakdown,
                load_mes_total_data,
                load_mes_loss_data,
            ],
            reflect_on_tool_use=True,
        )

        return data_analyst_agent

    except Exception as e:
        logger.error(f"エージェントのセットアップ中にエラー: {str(e)}")
        return None


# カスタムツールクラスの例（必要に応じて使用）
# from autogen_ext.tools import Tool
#
# class CustomSearchTool(Tool):
#     """カスタム検索ツールの例"""
#
#     def __init__(self):
#         super().__init__(
#             name="custom_search",
#             description="カスタマイズされた検索機能を提供するツール。DuckDuckGoを使用して高精度な検索を行います。",
#             parameters={
#                 "type": "object",
#                 "properties": {
#                     "query": {
#                         "type": "string",
#                         "description": "検索クエリ"
#                     }
#                 },
#                 "required": ["query"]
#             }
#         )
#
#     def execute(self, query: str) -> str:
#         return search_duckduckgo(query)
