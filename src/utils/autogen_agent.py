from autogen_agentchat.agents import (
    AssistantAgent,
)
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_core.models import ModelInfo
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool
from dotenv import load_dotenv
import logging
import os
from duckduckgo_search import DDGS
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ローカルモジュールのインポート
from .tools import upload_file_to_blob

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
データが見えない場合は、必要なデータをユーザに求めます。
**重要**: ツール実行結果の `is_error` が `True` の場合は、コードが失敗しています。その原因を分析し、コードを修正して再実行してください。成功と誤認してはいけません。
**グラフ生成とアップロードのルール:**
1.  **思考**: まず、グラフを保存するファイル名を決めます。（例: `my_graph.png`）
2.  **行動 (コード実行)**: `execute_tool`を使い、Pythonコードで `img` ディレクトリを作成し、そこにグラフを保存します（例: `import os; os.makedirs('img', exist_ok=True); plt.savefig('img/my_graph.png')`）。ファイルは `tmp/img/` ディレクトリに保存されます。
3.  **観察**: コード実行が成功し、ファイルが作成されたことを確認します。
4.  **行動 (アップロード)**: `upload_image_to_blob`ツールを呼び出し、`tmp/img/` を先頭に付けたパス（例: `tmp/img/my_graph.png`）で画像をアップロードします。
5.  **観察**: アップロードツールの実行結果から、画像の公開URLを取得します。
6.  **応答**: 応答メッセージに、取得した公開URLを `[image: 公開URL]` の形式で正確に含めてください。
matplotlibで日本語グラフを作成する際は、日本語フォントの設定が必要です。以下のコードを実行して、日本語フォントを設定してください。
'''
plt.rcParams["font.family"] = "IPAexGothic"
'''
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
        # 環境変数の読み込み
        load_dotenv("./.env_gpt4.1", override=True)

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

        execute_tool = PythonCodeExecutionTool(
            LocalCommandLineCodeExecutor(
                timeout=300, work_dir="tmp", cleanup_temp_files=False
            ),
        )

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

**グラフ生成とアップロードのルール:**
1.  **思考**: まず、グラフを保存するファイル名を決めます。（例: `{yyyymmdd-hhmmss}.png`）
2.  **行動 (コード実行)**: `execute_tool`を使い、
3.  **観察**: コード実行が成功し、ファイルが作成されたことを確認します。
4.  **行動 (アップロード)**: `upload_image_to_blob`ツールを呼び出し、`tmp/` を先頭に付けたパス（例: `tmp/{yyyymmdd-hhmmss}.png`）で画像をアップロードします。
5.  **観察**: アップロードツールの実行結果から、画像の公開URLを取得します。
6.  **応答**: 応答メッセージに、取得した公開URLを `[image: 公開URL]` の形式で正確に含めてください。
matplotlibで日本語グラフを作成する際は、日本語フォントの設定が必要です。以下のコードを実行して、日本語フォントを設定してください。
'''
plt.rcParams["font.family"] = "IPAexGothic"
'''
        必ず日本語で回答してください。""",
            tools=[execute_tool, upload_image_to_blob],
            reflect_on_tool_use=True,
        )

        return data_analyst_agent

    except Exception as e:
        logger.error(f"エージェントのセットアップ中にエラー: {str(e)}")
        return None


def upload_image_to_blob(file_path: str) -> str:
    """
    指定されたローカルファイルパスの画像をAzure Blob Storageにアップロードし、その公開URLを返します。
    グラフをローカルに保存した後にこのツールを呼び出して、画像をクラウドにアップロードしてください。
    例: upload_image_to_blob('tmp/img/my_graph.png')
    """
    if not os.path.exists(file_path):
        return f"エラー: ファイルが見つかりません {file_path}"

    url = upload_file_to_blob(file_path)

    # アップロード後にローカルファイルを削除
    try:
        os.remove(file_path)
        logger.info(f"ローカルファイルを削除しました: {file_path}")
    except Exception as e:
        logger.warning(f"ローカルファイルの削除に失敗しました {file_path}: {e}")

    return f"画像のアップロードに成功しました。URL: {url}"


def search_duckduckgo(query: str) -> str:
    """DuckDuckGo検索関数"""
    try:
        print(f"[llm_agent] DuckDuckGo検索ツールを使用: query='{query}'")
        with DDGS() as ddgs:
            results = ddgs.text(query)
            return "\n".join([f"{r['title']}: {r['body']}" for r in results[:3]])
    except Exception as e:
        return f"検索エラー: {str(e)}"
