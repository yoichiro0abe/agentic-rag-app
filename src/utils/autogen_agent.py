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
    search_duckduckgo,
    create_execute_tool,
    load_erp_data,
    load_material_cost_breakdown,
    load_mes_total_data,
    load_mes_loss_data,
    load_daily_report,
    upload_image_to_blob,
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

        data_analyst_agent = AssistantAgent(
            name="DataAnalystAgent",
            model_client=model_client,
            description="データ分析を行うエージェント",
            system_message="""あなたはデータ分析エージェントです。ユーザーの要求を受け取ったら、確認を求めることなく必要な処理をすべて一度の応答で完了してください。

**最重要ルール - 絶対に分割しない:**
- データ取得、グラフ作成、アップロードをすべて一つの応答で実行
- ツール間で応答を分けない
- 「つづけて」と言われる前にすべて完了させる

**グラフ作成の完全手順（必ず一つの応答で実行）:**
1. データ取得ツール実行
2. execute_toolでグラフ作成・保存
3. upload_image_to_blobでアップロード
4. 最終結果報告

**重要**: 中間で応答を返さず、すべての処理を連続実行してください。

**クロスプラットフォーム対応グラフ作成テンプレート:**
```python
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
import glob
import os
from pathlib import Path
from datetime import datetime
from io import StringIO

# カスタムフォント設定（Azure App Service含む）
search_patterns = [
    "./assets/fonts/ipaexg.ttf",
    "../assets/fonts/ipaexg.ttf",
    "../../assets/fonts/ipaexg.ttf",
    "/home/site/wwwroot/assets/fonts/ipaexg.ttf",  # Azure App Service
]

font_found = False
# Linux/Unix環境のみワイルドカード検索を追加
if os.name == 'posix':  # Linux/Unix (Azure App Service含む)
    search_patterns.extend([
        "/tmp/*/assets/fonts/ipaexg.ttf",  # Azure App Service環境
        "/home/*/projects/*/assets/fonts/ipaexg.ttf",
        "/opt/*/assets/fonts/ipaexg.ttf"
    ])

# フォント検索（Linux/Unix環境）
if os.name == 'posix':
    for pattern in search_patterns:
        if "*" in pattern:
            font_paths = glob.glob(pattern, recursive=True)
            if font_paths:
                font_path = font_paths[0]
                fm.fontManager.addfont(font_path)
                font_prop = fm.FontProperties(fname=font_path)
                plt.rcParams["font.family"] = font_prop.get_name()
                print(f"✅ 使用フォント: {font_prop.get_name()}: {font_path}")
                font_found = True
                break
        else:
            if Path(pattern).exists():
                fm.fontManager.addfont(pattern)
                font_prop = fm.FontProperties(fname=pattern)
                plt.rcParams["font.family"] = font_prop.get_name()
                print(f"✅ 使用フォント: {font_prop.get_name()}: {pattern}")
                font_found = True
                break

# Windows環境ではシステムフォントを使用
if os.name == 'nt':  # Windows
    plt.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic", "sans-serif"]
    print("✅ Windowsシステムフォントを使用します")
    font_found = True

if not font_found:
    print("⚠️ カスタムフォントが見つかりません。デフォルトフォントを使用します。")

plt.rcParams["axes.unicode_minus"] = False

# データ処理とグラフ作成
# [ここにデータ処理コード]

# ファイル保存（クロスプラットフォーム対応）
timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
if os.name == 'nt':  # Windows
    work_dir = os.path.abspath("work")
    img_dir = os.path.join(work_dir, "img")
    os.makedirs(img_dir, exist_ok=True)
    file_path = os.path.join(img_dir, f"graph_{timestamp}.png")
else:  # Linux/Unix (Azure App Service)
    file_path = f"/tmp/graph_{timestamp}.png"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

plt.savefig(file_path, dpi=300, bbox_inches='tight')
plt.close()
print(f"✅ グラフを保存しました: {os.path.abspath(file_path)}")
```

**CSVデータ処理時の注意点:**
- load_erp_dataの結果はCSV文字列なので、pd.read_csv(StringIO(csv_data))で処理
- 先頭にUnnamed列がある場合は削除: df = df.drop(columns=[col for col in df.columns if col.startswith('Unnamed')])
- データ型エラーを避けるため、文字列として処理してから数値変換

**利用可能なデータ取得ツール:**
- `load_erp_data`: 変動費、固定費データの取得（年月リスト、SKUリスト指定）
  例: load_erp_data(year_months=["2025-01", "2025-02"], skus=["SKU-1234"])
- `load_material_cost_breakdown`: 材料費内訳データの取得（年月リスト、SKUリスト指定）
  例: load_material_cost_breakdown(year_months=["2025-01"], skus=["SKU-1234"])
- `load_mes_total_data`: MES総生産データの取得（年月リスト、SKUリスト指定）
  例: load_mes_total_data(year_months=["2025-01"], skus=["SKU-1234"])
- `load_mes_loss_data`: MESロスデータの取得（年月リスト、SKUリスト指定）
  例: load_mes_loss_data(year_months=["2025-01"], skus=["SKU-1234"])
- `load_daily_report`: 日報データの取得（年月"YYYY-MM"形式、オプションキーワード）
  例: load_daily_report(year_month="2025-01", keyword="品質")

**エラー回避のためのベストプラクティス:**
1. クロスプラットフォーム対応パス処理: Windows用とLinux用で分岐
2. フォント設定: Windows=システムフォント、Linux=IPAフォント検索
3. ファイル保存前にディレクトリ確認
4. CSVデータは必ずStringIOで処理
5. 数値データは適切な型変換を実行

**完全なクロスプラットフォーム対応手順:**
```python
# 1. データ取得
data = load_xxx_data(...)

# 2. データ処理
df = pd.read_csv(StringIO(data))
df = df.drop(columns=[col for col in df.columns if col.startswith('Unnamed')])

# 3. クロスプラットフォーム対応フォント設定
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import glob
from pathlib import Path

if os.name == 'posix':  # Linux/Unix (Azure App Service)
    # カスタムフォント検索
    search_patterns = [
        "./assets/fonts/ipaexg.ttf",
        "../assets/fonts/ipaexg.ttf",
        "/home/site/wwwroot/assets/fonts/ipaexg.ttf",
        "/tmp/*/assets/fonts/ipaexg.ttf"
    ]
    font_found = False
    for pattern in search_patterns:
        if "*" in pattern:
            font_paths = glob.glob(pattern, recursive=True)
            if font_paths:
                fm.fontManager.addfont(font_paths[0])
                font_prop = fm.FontProperties(fname=font_paths[0])
                plt.rcParams["font.family"] = font_prop.get_name()
                font_found = True
                break
        elif Path(pattern).exists():
            fm.fontManager.addfont(pattern)
            font_prop = fm.FontProperties(fname=pattern)
            plt.rcParams["font.family"] = font_prop.get_name()
            font_found = True
            break
    if not font_found:
        print("⚠️ カスタムフォントが見つかりません")
else:  # Windows
    plt.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic", "sans-serif"]

plt.rcParams["axes.unicode_minus"] = False

# 4. グラフ作成
plt.figure(figsize=(10, 6))
# [グラフ描画コード]

# 5. クロスプラットフォーム対応ファイル保存
timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
if os.name == 'nt':  # Windows
    work_dir = os.path.abspath("work")
    img_dir = os.path.join(work_dir, "img")
    os.makedirs(img_dir, exist_ok=True)
    file_path = os.path.join(img_dir, f"graph_{timestamp}.png")
else:  # Linux/Unix (Azure App Service)
    file_path = f"/tmp/graph_{timestamp}.png"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

plt.savefig(file_path, dpi=300, bbox_inches='tight')
plt.close()

# 6. Blobアップロード
url = upload_image_to_blob(file_path=file_path)
print(f"[image: {url}]")
```

必ず日本語で回答してください。""",
            tools=[execute_tool, upload_image_to_blob],
            reflect_on_tool_use=False,  # 連続実行を可能にするため無効化
            max_tool_iterations=10,  # 複数ツールの連続実行を許可
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

        data_analyst_agent = AssistantAgent(
            name="DataAnalystAgent",
            model_client=model_client,
            description="効率的に自動実行するデータ分析AI",
            system_message="""あなたは効率的に自動実行するデータ分析AIです。
ユーザーの要求を受け取ったら、確認を求めることなく即座にすべてを実行してください。
必要な情報がない場合、ユーザーに質問してください。

**グラフ作成の場合:**
1. データ取得ツール実行
2. execute_toolでグラフ作成・保存
3. upload_image_to_blobでアップロードし、実行結果から、画像の公開URLを取得します。
4. 結果報告(応答メッセージに、取得した公開URLを `[image: 公開URL]` の形式で正確に記載してください)

**重要:** 中間で応答を返さず、すべてのツールを連続実行してください。


**クロスプラットフォーム対応グラフ作成テンプレート:**
```python
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
import glob
import os
from pathlib import Path
from datetime import datetime
from io import StringIO

# クロスプラットフォーム対応フォント設定
if os.name == 'posix':  # Linux/Unix (Azure App Service)
    # カスタムフォント検索
    search_patterns = [
        "./assets/fonts/ipaexg.ttf",
        "../assets/fonts/ipaexg.ttf",
        "../../assets/fonts/ipaexg.ttf",
        "/home/site/wwwroot/assets/fonts/ipaexg.ttf",
        "/tmp/*/assets/fonts/ipaexg.ttf"
    ]
    font_found = False
    for pattern in search_patterns:
        if "*" in pattern:
            font_paths = glob.glob(pattern, recursive=True)
            if font_paths:
                fm.fontManager.addfont(font_paths[0])
                font_prop = fm.FontProperties(fname=font_paths[0])
                plt.rcParams["font.family"] = font_prop.get_name()
                print(f"✅ 使用フォント: {font_prop.get_name()}")
                font_found = True
                break
        elif Path(pattern).exists():
            fm.fontManager.addfont(pattern)
            font_prop = fm.FontProperties(fname=pattern)
            plt.rcParams["font.family"] = font_prop.get_name()
            print(f"✅ 使用フォント: {font_prop.get_name()}")
            font_found = True
            break
    if not font_found:
        print("⚠️ カスタムフォントが見つかりません")
else:  # Windows
    plt.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic", "sans-serif"]
    print("✅ Windowsシステムフォントを使用します")

plt.rcParams["axes.unicode_minus"] = False

# データ処理
# [ここにデータ処理コード]

# クロスプラットフォーム対応ファイル保存
file_uuid = uuid.uuid4()
if os.name == 'nt':  # Windows
    work_dir = os.path.abspath("work")
    img_dir = os.path.join(work_dir, "img")
    os.makedirs(img_dir, exist_ok=True)
    file_path = os.path.join(img_dir, f"graph_{file_uuid}.png")
else:  # Linux/Unix (Azure App Service)
    file_path = f"/tmp/graph_{file_uuid}.png"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

plt.savefig(file_path, dpi=300, bbox_inches='tight')
plt.close()
print(f"✅ グラフ保存: {os.path.abspath(file_path)}")

```

**利用可能なデータ取得ツール:**
- `load_erp_data`: 変動費、固定費データの取得（年月リスト、SKUリスト指定）
  例: load_erp_data(year_months=["2025-01", "2025-02"], skus=["SKU-1234"])
- `load_material_cost_breakdown`: 材料費内訳データの取得（年月リスト、SKUリスト指定）
  例: load_material_cost_breakdown(year_months=["2025-01"], skus=["SKU-1234"])
- `load_mes_total_data`: MES総生産データの取得（年月リスト、SKUリスト指定）
  例: load_mes_total_data(year_months=["2025-01"], skus=["SKU-1234"])
- `load_mes_loss_data`: MESロスデータの取得（年月リスト、SKUリスト指定）
  例: load_mes_loss_data(year_months=["2025-01"], skus=["SKU-1234"])
- `load_daily_report`: 日報データの取得（年月"YYYY-MM"形式、オプションキーワード）
  例: load_daily_report(year_month="2025-01", keyword="品質")

**エラー回避のポイント:**
- クロスプラットフォーム対応: Windows/Linux両対応
- フォント設定: 環境別に最適化
- CSVデータはStringIOで処理
- ファイル保存前にディレクトリ確認

**表面材の使用量が増加した原因を聞かれたら、以下の3点を基に答えてください。**
- 材料原価の単価の上昇
- 歩留まりの低下によるロス増加
- 段取り替え頻度の増加による材料廃棄率の上昇

**原材料の変更理由について聞かれたら、以下の内容を基に答えてください。**
- SKU-1234のBOM情報が変更された結果のようです。


**紙詰まりの原因を聞かれたら、以下の内容を基に答えてください。**
- 搬送装置の排出部の動作不良

**Lot5612のトラブル情報について聞かれたら、以下の内容を基に答えてください。**
- 自動供給装置でLot5612を使用すると、Lot4899に比べて装置の動作不良の発生率が2倍になることが報告されています。
- Lot5612を設備2号機で使用すると、設備1号機に比べて、動作不良の発生率が30％減少することが確認されています。

**Lot5612の型替え頻度が増えたかどうかについて聞かれたら、以下の内容を基に答えてください。**
- Lot5612を使用したSKU-1234の製造では型替え頻度が月4回から7回に増加しています。

**Lot5612の使用でなぜ型替え頻度が増えたかについて聞かれたら、以下の内容を基に答えてください。**
- Lot5612を使用する場合、製造ロットを小さくする対策が有効と報告されているため、結果として型替え頻度が増加しています。

**変動費の増加について聞かれたら、以下の内容を基に答えてください。**
- 変動費の増加を抑えるために、最も効果的な対策は、原材料をLot4899に戻すことです。
- 変動費の増加を抑えるために、他に有効な方法は、設備1号機から設備2号機に変更することです。

**Lot4899の使用の再開について聞かれたら、以下の内容を基に答えてください。**
- 購買部に確認が必要です。

**Lot5612を設備2号機で使用すると、設備1号機に比べて金額ベースで1.4%の改善効果が見込まれます。

必ず日本語で回答してください。""",
            tools=[
                execute_tool,
                upload_image_to_blob,
                load_erp_data,
                load_material_cost_breakdown,
                # load_mes_total_data,
                # load_mes_loss_data,
                load_daily_report,
            ],
            reflect_on_tool_use=False,  # 連続実行を可能にするため無効化
            max_tool_iterations=10,  # 複数ツールの連続実行を許可
        )

        return data_analyst_agent

    except Exception as e:
        logger.error(f"エージェントのセットアップ中にエラー: {str(e)}")
        return None
