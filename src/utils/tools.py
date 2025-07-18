import os
from azure.storage.blob import BlobServiceClient
import uuid
import logging
from duckduckgo_search import DDGS
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool
import pandas as pd
from typing import List, Optional
import re
import functools
import time
import streamlit as st

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def timer(func):
    """実行時間を計測するデコレータ"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger.info(f"{func.__name__} - 開始")
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(f"{func.__name__} - 完了 (実行時間: {elapsed_time:.2f}秒)")

    return wrapper


def get_work_directory():
    """OSに応じた作業ディレクトリパスを取得

    Returns:
        str: 作業ディレクトリのパス
        - Azure App Service: '/home/site/work' (永続化される)
        - ローカル開発: 'work' (相対パス)

    Notes:
        Azure App Serviceでは/home/siteディレクトリが永続化されるため、
        そのサブディレクトリとしてworkディレクトリを作成します。
    """
    # Azure App Service環境の検出
    # WEBSITE_SITE_NAME環境変数はAzure App Serviceでのみ設定される
    if os.getenv("WEBSITE_SITE_NAME"):
        # Azure App Service環境：/home/siteディレクトリ内に作業ディレクトリを作成
        # /home/siteは永続化されるため安全
        work_dir = "/home/site/work"
        # ディレクトリが存在しない場合は作成
        try:
            os.makedirs(work_dir, exist_ok=True)
        except OSError as e:
            logger.warning(f"作業ディレクトリの作成に失敗: {e}")
            # フォールバック: /tmpディレクトリを使用（一時的）
            work_dir = "/tmp/work"
            os.makedirs(work_dir, exist_ok=True)
        return work_dir
    else:
        # ローカル環境：プロジェクトディレクトリ内の相対パス
        return "work"


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
            work_dir=get_work_directory(),
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
    # コード実行エージェントの作業ディレクトリを取得
    agent_work_dir = get_work_directory()
    # file_pathを正規化し、workディレクトリ重複を排除
    normalized = os.path.normpath(file_path)
    abs_work = os.path.abspath(agent_work_dir)
    # 絶対パスでwork_dir配下を指す場合は相対パスに変換
    if os.path.isabs(normalized) and normalized.startswith(abs_work + os.path.sep):
        file_path = os.path.relpath(normalized, abs_work)
    else:
        # 相対パスで先頭にworkディレクトリ名がある場合は削除
        parts = normalized.split(os.path.sep)
        if parts and parts[0] == os.path.basename(agent_work_dir):
            file_path = os.path.sep.join(parts[1:])
        else:
            file_path = normalized

    # 絶対パスで扱うため、作業ディレクトリの絶対パスと結合
    full_path_in_agent_work_dir = os.path.join(abs_work, file_path)

    # まずエージェントの作業ディレクトリ内を探索
    if os.path.exists(full_path_in_agent_work_dir):
        path_to_use = full_path_in_agent_work_dir
    # 次に渡されたパスをそのまま探索（後方互換性または絶対パス指定の場合）
    elif os.path.exists(file_path):
        path_to_use = file_path
    else:
        return f"エラー: ファイルが見つかりません。試行したパス: {full_path_in_agent_work_dir} および {file_path}"

    try:
        connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

        if not connect_str or not container_name:
            error_msg = "環境変数にAzure Storageの接続情報が設定されていません。"
            logger.error(error_msg)
            return f"エラー: {error_msg}"

        blob_service_client = BlobServiceClient.from_connection_string(connect_str)

        # 上書きを防ぐために一意のBLOB名を生成
        blob_name = f"{uuid.uuid4()}-{os.path.basename(path_to_use)}"
        blob_client = blob_service_client.get_blob_client(
            container=container_name, blob=blob_name
        )

        logger.info(
            f"Uploading {path_to_use} to Azure Blob Storage as blob {blob_name}..."
        )
        with open(path_to_use, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        logger.info("Upload successful.")
        url = blob_client.url

        # アップロード後にローカルファイルを削除
        try:
            os.remove(path_to_use)
            logger.info(f"ローカルファイルを削除しました: {path_to_use}")
        except Exception as e:
            logger.warning(f"ローカルファイルの削除に失敗しました {path_to_use}: {e}")

        return f"画像のアップロードに成功しました。[image: {url}]"

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


def load_daily_report(month: str, keyword: Optional[str] = None) -> str:
    """
    日報データ（daily_report.csv）を読み込み、指定された月とキーワードで検索するツール。

    Args:
        month (str): フィルタする年月（例: "2024-07"）。
        keyword (Optional[str], optional): 検索するキーワード。'内容'列から部分一致で検索します。指定しない場合はキーワードでの絞り込みは行いません。

    Returns:
        str: 検索結果のCSVデータ。

    Examples:
        load_daily_report(month="2024-07", keyword="トラブル")
        load_daily_report(month="2024-06")
    """
    try:
        # daily_report.csvのパスを設定
        report_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "sampledata",
            "daily_report.csv",
        )

        if not os.path.exists(report_file_path):
            return f"エラー: 日報ファイルが見つかりません: {report_file_path}"

        # CSVファイルを読み込み
        df = pd.read_csv(report_file_path, encoding="utf-8")

        # '年月日'列をdatetime型に変換し、年月でフィルタ
        df["年月日"] = pd.to_datetime(df["年月日"])
        df_filtered = df[df["年月日"].dt.strftime("%Y-%m") == month]
        logger.info(
            f"フィルタリング後のデータ行数: {len(df_filtered)} (月: {month}, キーワード: {keyword})"
        )

        # キーワードでフィルタ（'内容'列を想定）
        if keyword and "内容" in df_filtered.columns:
            df_filtered = df_filtered[
                df_filtered["内容"].str.contains(keyword, na=False)
            ]

        if df_filtered.empty:
            return f"指定された条件（年月: {month}, キーワード: {keyword}）に該当するデータがありません。"

        # CSVの内容を文字列として返す
        csv_content = df_filtered.to_csv(index=False, encoding="utf-8")

        return csv_content

    except Exception as e:
        import traceback

        logger.error(f"日報データの読み込みエラー: {str(e)}")
        logger.error(f"エラーの詳細: {traceback.format_exc()}")
        return f"エラー: 日報データの読み込みに失敗しました: {str(e)}"


def check_content(input_str: str) -> str:
    """
    入力文字列がFunction***かどうか判定する

    Args:
        input_str (str): チェックする文字列

    Returns:
        str: 入力がFunction***の場合はパースしてname属性を取り出す
    """
    try:
        # パターン1: FunctionExecutionResult（contentベース） - リスト形式
        content_pattern = r"FunctionExecutionResult\(.*?name=['\"]([^'\"]+)['\"].*?\)"
        content_matches = re.findall(content_pattern, input_str)

        if content_matches:
            name_value = content_matches[0]
            logger.info(f"name (content形式): {name_value}")
            return name_value
        # 正規表現パターン：name を抽出
        function_call_pattern = r"FunctionCall\(.*?name='([^']*)'.*?\)"
        function_call_matches = re.findall(function_call_pattern, input_str)

        # 結果をリストに格納
        for name_value in function_call_matches:
            logger.info(f"name: {name_value}")
            return name_value
    except Exception as e:
        logger.error(f"check_contentのエラー: {str(e)}")
        return None
    return None


def display_multiagent_chat_message(message, index):
    """
    マルチエージェントのチャットメッセージを表示する関数。

    Args:
        message (TextMessage): 表示するメッセージオブジェクト。
        index (int): メッセージのインデックス。
    """
    role = "🤖 エージェント" if message.source != "user" else "👤 ユーザー"
    st.markdown(f"**{role} ({index + 1}):**")
    st.markdown(f"> {message.content}")
