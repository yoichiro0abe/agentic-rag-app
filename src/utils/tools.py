import os
from azure.storage.blob import BlobServiceClient
import uuid
import logging

logger = logging.getLogger(__name__)


def upload_file_to_blob(file_path: str) -> str:
    """
    ファイルをAzure Blob Storageにアップロードし、その公開URLを返します。
    接続文字列とコンテナ名は環境変数から取得します。
    """
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
        return blob_client.url
    except Exception as e:
        logger.error(f"Azure Blob Storageへのファイルアップロードに失敗しました: {e}")
        return f"エラー: ファイルのアップロードに失敗しました。 {e}"
