import os
from azure.storage.blob import BlobServiceClient
import uuid
import logging
from datetime import datetime, timezone, timedelta
from duckduckgo_search import DDGS
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool
import pandas as pd
from typing import List

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
            work_dir="/agent-work",
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


def load_erp_data(year_months: List[str] = None, skus: List[str] = None) -> str:
    """
    SKUの固定費と変動費を読み込み、指定された年月とSKUに基づいてCSVデータを返すツール。

    Args:
        year_months (List[str], optional): フィルタする年月のリスト（例: ["2023-01", "2023-02"]）
        skus (List[str], optional): フィルタするSKUのリスト（例: ["SKU001", "SKU002"]）

    Returns:
        str: 指定された年月とSKUに基づいたCSVデータ

    Examples:
        load_erp_data(["2023-01"], ["SKU001", "SKU002"])
        load_erp_data(year_months=["2023-01", "2023-02"])
        load_erp_data(skus=["SKU001"])
        load_erp_data()  # 全データを取得
    """
    try:
        # ERPファイルのパスを設定
        erp_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "sampledata",
            "erp.csv",
        )

        if not os.path.exists(erp_file_path):
            return f"エラー: ERPファイルが見つかりません: {erp_file_path}"

        # CSVファイルを読み込み
        df = pd.read_csv(erp_file_path, encoding="utf-8")
        # 年月でフィルタ
        if year_months:
            df = df[df["年月"].isin(year_months)]

        # SKUでフィルタ
        if skus:
            df = df[df["SKU"].isin(skus)]
        # CSVの内容を文字列として返す
        csv_content = df.to_csv(index=True, encoding="utf-8")

        return csv_content

    except Exception as e:
        logger.error(f"ERPデータの読み込みエラー: {str(e)}")
        return f"エラー: ERPデータの読み込みに失敗しました: {str(e)}"


def load_material_cost_breakdown(year_months: List[str], sku: str) -> str:
    """
    SKUの材料費の内訳データを読み込み、指定された年月とSKUに基づいて原料別の費用内訳を返すツール。

    Args:
        year_months (List[str]): フィルタする年月のリスト（例: ["2023-01", "2023-02"]）
        sku (str): フィルタするSKU（例: "SKU001"）

    Returns:
        str: 指定された年月とSKUに基づいた材料費内訳のCSVデータ

    Examples:
        load_material_cost_breakdown(["2023-01", "2023-02"], "SKU001")
        load_material_cost_breakdown(["2024-01"], "SKU001")
    """
    try:
        # 材料費ファイルのパスを設定
        material_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "sampledata",
            "erp_material.csv",
        )

        if not os.path.exists(material_file_path):
            return f"エラー: 材料費ファイルが見つかりません: {material_file_path}"

        # CSVファイルを読み込み
        df = pd.read_csv(material_file_path, encoding="utf-8")

        # 年月でフィルタ
        if year_months:
            df = df[df["年月"].isin(year_months)]

        # SKUでフィルタ
        if sku:
            df = df[df["SKU"] == sku]

        if df.empty:
            return f"指定された条件（年月: {year_months}, SKU: {sku}）に該当するデータがありません。"

        # CSVの内容を文字列として返す
        csv_content = df.to_csv(index=False, encoding="utf-8")

        return csv_content

    except Exception as e:
        logger.error(f"材料費データの読み込みエラー: {str(e)}")
        return f"エラー: 材料費データの読み込みに失敗しました: {str(e)}"


def load_mes_total_data(year_months: List[str] = None, skus: List[str] = None) -> str:
    """
    MES総合データ（良品数・不良数）を読み込み、指定された年月とSKUに基づいてCSVデータを返すツール。

    Args:
        year_months (List[str], optional): フィルタする年月のリスト（例: ["2024-06", "2024-07"]）
        skus (List[str], optional): フィルタするSKUのリスト（例: ["SKU001", "SKU002"]）

    Returns:
        str: 指定された年月とSKUに基づいた良品数・不良数のCSVデータ

    Examples:
        load_mes_total_data(["2024-06"], ["SKU001", "SKU002"])
        load_mes_total_data(year_months=["2024-06", "2024-07"])
        load_mes_total_data(skus=["SKU001"])
        load_mes_total_data()  # 全データを取得
    """
    try:
        # MES総合データファイルのパスを設定
        mes_total_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "sampledata",
            "mes_total.csv",
        )

        if not os.path.exists(mes_total_file_path):
            return (
                f"エラー: MES総合データファイルが見つかりません: {mes_total_file_path}"
            )

        # CSVファイルを読み込み
        df = pd.read_csv(mes_total_file_path, encoding="utf-8")

        # 年月でフィルタ（年月日から年月を抽出してフィルタ）
        if year_months:
            df["年月"] = df["年月日"].str[:7]  # YYYY-MM-DD から YYYY-MM を抽出
            df = df[df["年月"].isin(year_months)]
            df = df.drop(columns=["年月"])  # 一時的に追加した年月カラムを削除

        # SKUでフィルタ
        if skus:
            df = df[df["SKU"].isin(skus)]

        if df.empty:
            return f"指定された条件（年月: {year_months}, SKU: {skus}）に該当するデータがありません。"

        # CSVの内容を文字列として返す
        csv_content = df.to_csv(index=False, encoding="utf-8")

        return csv_content

    except Exception as e:
        logger.error(f"MES総合データの読み込みエラー: {str(e)}")
        return f"エラー: MES総合データの読み込みに失敗しました: {str(e)}"


def load_mes_loss_data(year_months: List[str] = None, skus: List[str] = None) -> str:
    """
    MESロス内訳データ（加工機ロス、包装機ロス、検品ロス、フィルムロス、不明ロス）を読み込み、
    指定された年月とSKUに基づいてCSVデータを返すツール。

    Args:
        year_months (List[str], optional): フィルタする年月のリスト（例: ["2024-06", "2024-07"]）
        skus (List[str], optional): フィルタするSKUのリスト（例: ["SKU001", "SKU002"]）

    Returns:
        str: 指定された年月とSKUに基づいたロス内訳のCSVデータ

    Examples:
        load_mes_loss_data(["2024-06"], ["SKU001", "SKU002"])
        load_mes_loss_data(year_months=["2024-06", "2024-07"])
        load_mes_loss_data(skus=["SKU001"])
        load_mes_loss_data()  # 全データを取得
    """
    try:
        # MESロス内訳データファイルのパスを設定
        mes_loss_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "sampledata",
            "mes_total_err.csv",
        )

        if not os.path.exists(mes_loss_file_path):
            return f"エラー: MESロス内訳データファイルが見つかりません: {mes_loss_file_path}"

        # CSVファイルを読み込み
        df = pd.read_csv(mes_loss_file_path, encoding="utf-8")

        # 年月でフィルタ（年月日から年月を抽出してフィルタ）
        if year_months:
            df["年月"] = df["年月日"].str[:7]  # YYYY-MM-DD から YYYY-MM を抽出
            df = df[df["年月"].isin(year_months)]
            df = df.drop(columns=["年月"])  # 一時的に追加した年月カラムを削除

        # SKUでフィルタ
        if skus:
            df = df[df["SKU"].isin(skus)]

        if df.empty:
            return f"指定された条件（年月: {year_months}, SKU: {skus}）に該当するデータがありません。"

        # CSVの内容を文字列として返す
        csv_content = df.to_csv(index=False, encoding="utf-8")

        return csv_content

    except Exception as e:
        logger.error(f"MESロス内訳データの読み込みエラー: {str(e)}")
        return f"エラー: MESロス内訳データの読み込みに失敗しました: {str(e)}"
