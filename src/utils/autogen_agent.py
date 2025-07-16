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
    load_daily_report,
    timer,
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
データが見えない場合は、必要なデータをユーザに求めます。        **重要**: ツール実行結果の `is_error` が `True` の場合は、コードが失敗しています。その原因を分析し、コードを修正して再実行してください。成功と誤認してはいけません。
        **グラフ生成とアップロードのルール:**
        グラフ作成の指示を受けた場合は、以下のステップを**一回の応答で連続実行**してください：
        1. **思考**: グラフの保存先パスを決定します。作業ディレクトリは `{work_dir}` です。
        2. **行動**: `execute_tool` でグラフ保存とアップロードのPythonコードを実行
        3. **応答**: 取得した公開URLを `[image: 公開URL]` 形式で含めて完了報告

        **重要**: グラフ作成とアップロードは必ず同一の応答内で連続実行し、分割しないでください。
matplotlibで日本語グラフを作成する際は、以下のコードを実行してください：
```python
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import glob
from pathlib import Path

# カスタムフォント設定
search_patterns = [
    "/tmp/*/assets/fonts/ipaexg.ttf",
    "/home/site/wwwroot/assets/fonts/ipaexg.ttf",
    "./assets/fonts/ipaexg.ttf",
    "../assets/fonts/ipaexg.ttf",
    "../../assets/fonts/ipaexg.ttf",
]
font_found = False
for pattern in search_patterns:
    if "*" in pattern:
        font_paths = glob.glob(pattern)
        if font_paths:
            font_path = font_paths[0]
            fm.fontManager.addfont(font_path)
            font_prop = fm.FontProperties(fname=font_path)
            plt.rcParams["font.family"] = font_prop.get_name()
            print(f"✅ 使用フォント: {{font_prop.get_name()}}: {{font_path}}")
            font_found = True
            break
    else:
        if Path(pattern).exists():
            fm.fontManager.addfont(pattern)
            font_prop = fm.FontProperties(fname=pattern)
            plt.rcParams["font.family"] = font_prop.get_name()
            print(f"✅ 使用フォント: {{font_prop.get_name()}}: {{pattern}}")
            font_found = True
            break

plt.rcParams["axes.unicode_minus"] = False

# [ここにグラフ作成コード]

# 画像保存とアップロード
file_path = "img/graph_name.png"
plt.savefig(file_path, dpi=300, bbox_inches='tight')
plt.close()
url = upload_image_to_blob(file_path=file_path)
print(f"[image: {url}]")
```
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


@timer
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
            description="効率的に自動実行するデータ分析AI",
            system_message=f"""あなたは効率的に自動実行するデータ分析AIです。
ユーザーの要求を受け取ったら、確認を求めることなく即座に実行してください。

**実行方針:**
1. ユーザーの要求を理解し、必要なデータと処理を特定する
2. 必要なツールを連続して実行し、一度のやりとりで完結させる
3. ユーザーに確認を求めず、自動的に最適な判断で進める
4. 最終結果のみを報告する

**自動実行ルール:**
- データ取得、処理、分析、結果出力を一連の流れで実行
- 中間確認は行わず、エラーが発生した場合のみ修正して再実行
- 完了時は結果を簡潔に報告

**エラーハンドリング:**
ツール実行結果の `is_error` が `True` の場合は、コードが失敗しています。その原因を分析し、コードを修正して再実行してください。成功と誤認してはいけません。

**タスク別実行ルール:**

**データ分析・計算タスク:**
1. 必要なデータを取得
2. `execute_tool` で分析・計算を実行
3. 結果を簡潔に報告

**グラフ作成タスク:**
1. 必要なデータを取得
2. `execute_tool` でグラフ作成・保存・アップロードを実行
3. 取得した公開URLを `[image: 公開URL]` 形式で含めて完了報告

**重要**: 全ての処理を一つの応答内で連続実行し、分割しないでください。

**グラフ作成時のコードテンプレート:**
matplotlibでグラフを作成する際は、以下のコードテンプレートを使用してください：
```python
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
import glob
from pathlib import Path

# カスタムフォント設定
search_patterns = [
    "/tmp/*/assets/fonts/ipaexg.ttf",
    "/home/site/wwwroot/assets/fonts/ipaexg.ttf",
    "./assets/fonts/ipaexg.ttf",
    "../assets/fonts/ipaexg.ttf",
    "../../assets/fonts/ipaexg.ttf",
]
font_found = False
for pattern in search_patterns:
    if "*" in pattern:
        font_paths = glob.glob(pattern)
        if font_paths:
            font_path = font_paths[0]
            fm.fontManager.addfont(font_path)
            font_prop = fm.FontProperties(fname=font_path)
            plt.rcParams["font.family"] = font_prop.get_name()
            print(f"✅ 使用フォント: {{font_prop.get_name()}}: {{font_path}}")
            font_found = True
            break
    else:
        if Path(pattern).exists():
            fm.fontManager.addfont(pattern)
            font_prop = fm.FontProperties(fname=pattern)
            plt.rcParams["font.family"] = font_prop.get_name()
            print(f"✅ 使用フォント: {{font_prop.get_name()}}: {{pattern}}")
            font_found = True
            break

plt.rcParams["axes.unicode_minus"] = False

# [ここにグラフ作成コード]

# 画像保存（ファイル名は内容に応じて適切に設定）
file_path = "img/graph_name.png"
plt.savefig(file_path, dpi=300, bbox_inches='tight')
plt.close()

# 画像をBlob Storageにアップロード
url = upload_image_to_blob(file_path=file_path)
print(f"[image: {url}]")
```
**データ取得ツール:**
- `load_erp_data`: 変動費、固定費データの取得（年月リスト、SKUリスト指定）
- `load_material_cost_breakdown`: 材料費内訳データの取得（年月リスト、SKUリスト指定）
- `load_mes_total_data`: MES総生産データの取得（年月リスト、SKUリスト指定）
- `load_mes_loss_data`: MESロスデータの取得（年月リスト、SKUリスト指定）
- `load_daily_report`: 日報データの取得（年月"YYYY-MM"形式、オプションキーワード）

**応答形式:**
簡潔に結果のみを報告し、冗長な説明は避けてください。
必ず日本語で回答してください。""",
            tools=[
                execute_tool,
                load_erp_data,
                load_material_cost_breakdown,
                load_mes_total_data,
                load_mes_loss_data,
                load_daily_report,
            ],
            reflect_on_tool_use=True,
        )

        return data_analyst_agent

    except Exception as e:
        logger.error(f"エージェントのセットアップ中にエラー: {str(e)}")
        return None
