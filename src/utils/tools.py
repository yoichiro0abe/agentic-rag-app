import os
from azure.storage.blob import BlobServiceClient
import uuid
import logging
from datetime import datetime, timezone, timedelta
from duckduckgo_search import DDGS
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool

logger = logging.getLogger(__name__)


def get_current_time() -> str:
    """
    現在の日時を日本時間（JST）で取得するツール。

    Returns:
        str: 現在の日時を「YYYY-MM-DD HH:MM:SS JST」形式で返します。

    Examples:
        get_current_time() -> "2025-07-08 14:30:45 JST"
    """
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S JST")


def search_duckduckgo(query: str) -> str:
    """
    DuckDuckGoを使用してウェブ検索を行うツール。

    Args:
        query (str): 検索クエリ。具体的なキーワードや質問を入力してください。

    Returns:
        str: 検索結果（上位3件のタイトルと本文）。各結果は改行で区切られます。

    Examples:
        search_duckduckgo("Python machine learning")
        search_duckduckgo("2024年の日本の経済状況")
    """
    try:
        print(f"[llm_agent] DuckDuckGo検索ツールを使用: query='{query}'")
        with DDGS() as ddgs:
            results = ddgs.text(query)
            return "\n".join([f"{r['title']}: {r['body']}" for r in results[:3]])
    except Exception as e:
        return f"検索エラー: {str(e)}"


def create_execute_tool() -> PythonCodeExecutionTool:
    """
    PythonCodeExecutionToolを作成するファクトリ関数。

    Returns:
        PythonCodeExecutionTool: 設定済みのPythonコード実行ツール
    """
    return PythonCodeExecutionTool(
        LocalCommandLineCodeExecutor(
            timeout=300,
            work_dir="C:/agent-work",
            cleanup_temp_files=False,
        )
    )


def upload_image_to_blob(file_path: str) -> str:
    """
    指定されたローカルファイルパスの画像をAzure Blob Storageにアップロードし、その公開URLを返します。

    Args:
        file_path (str): アップロードする画像ファイルのローカルパス

    Returns:
        str: アップロード成功時は成功メッセージとURL、失敗時はエラーメッセージ

    Examples:
        upload_image_to_blob('C:/agent-work/my_graph.png')

    Note:
        グラフをローカルに保存した後にこのツールを呼び出して、画像をクラウドにアップロードしてください。
        アップロード後、ローカルファイルは自動的に削除されます。
    """
    if not os.path.exists(file_path):
        return f"エラー: ファイルが見つかりません {file_path}"

    try:
        connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

        if not connect_str or not container_name:
            error_msg = "環境変数にAzure Storageの接続情報が設定されていません。"
            logger.error(error_msg)
            return f"エラー: {error_msg}"

        blob_service_client = BlobServiceClient.from_connection_string(connect_str)

        # 上書きを防ぐために一意のBLOB名を生成
        blob_name = f"{uuid.uuid4()}-{os.path.basename(file_path)}"
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=blob_name
        )

        logger.info(
            f"Uploading {file_path} to Azure Blob Storage as blob {blob_name}..."
        )
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        logger.info("Upload successful.")
        url = blob_client.url

        # アップロード後にローカルファイルを削除
        try:
            os.remove(file_path)
            logger.info(f"ローカルファイルを削除しました: {file_path}")
        except Exception as e:
            logger.warning(f"ローカルファイルの削除に失敗しました {file_path}: {e}")

        return f"画像のアップロードに成功しました。URL: {url}"

    except Exception as e:
        logger.error(f"Azure Blob Storageへのファイルアップロードに失敗しました: {e}")
        return f"エラー: ファイルのアップロードに失敗しました。 {e}"
