# tests/utils/test_tools.py の疑似コード

# 1. 必要なライブラリをインポートする
#    - pytest: テストフレームワーク
#    - os: ファイルパスの操作
#    - unittest.mock の patch: オブジェクトをテスト中に置き換える（モックする）ため
#    - テスト対象の関数 upload_file_to_blob をインポートする

# 2. テストケース1: 正常系テスト
#    - 関数名: test_upload_file_to_blob_success
#    - pytestのtmp_pathフィクスチャを使用して、テスト用のダミーファイルを一時ディレクトリに作成する
#    - @patchデコレータを使用して、以下のオブジェクトをモックする
#      - 'src.utils.tools.os.getenv': 環境変数の読み取りをシミュレートする
#      - 'src.utils.tools.BlobServiceClient': Azure SDKのクライアントをシミュレートする
#      - 'src.utils.tools.uuid.uuid4': 一意なID生成を固定値に置き換える
#
#    - テストの準備 (Arrange)
#      - モックされたos.getenvが、テスト用の接続文字列とコンテナ名を返すように設定する
#      - モックされたuuid.uuid4が、固定のUUID文字列を返すように設定する
#      - モックされたBlobServiceClientのインスタンスと、そのメソッド(get_blob_client)、プロパティ(url)の振る舞いを定義する
#        - get_blob_clientは、モックされたblob_clientを返す
#        - blob_clientのurlプロパティは、期待されるURL文字列を返す
#      - テスト用のダミーファイルを作成し、中身を書き込む
#
#    - テストの実行 (Act)
#      - upload_file_to_blob関数を、作成したダミーファイルのパスを引数にして呼び出す
#
#    - 検証 (Assert)
#      - os.getenvが正しい引数で呼び出されたことを確認する
#      - BlobServiceClient.from_connection_stringが正しい接続文字列で呼び出されたことを確認する
#      - blob_service_client.get_blob_clientが正しいコンテナ名とBLOB名で呼び出されたことを確認する
#      - blob_client.upload_blobが呼び出されたことを確認する
#      - 関数の戻り値が、期待されるURLと一致することを確認する

# 3. テストケース2: 環境変数が設定されていない場合の異常系テスト
#    - 関数名: test_upload_file_to_blob_no_env_vars
#    - @patchデコレータを使用して 'src.utils.tools.os.getenv' をモックする
#
#    - テストの準備 (Arrange)
#      - モックされたos.getenvがNoneを返すように設定する
#
#    - テストの実行 (Act)
#      - upload_file_to_blob関数を呼び出す
#
#    - 検証 (Assert)
#      - 戻り値が期待されるエラーメッセージを含んでいることを確認する

# 4. テストケース3: ファイルアップロード時に例外が発生した場合の異常系テスト
#    - 関数名: test_upload_file_to_blob_upload_failure
#    - pytestのtmp_pathフィクスチャを使用する
#    - @patchデコレータを使用して、os.getenv, BlobServiceClient, uuid.uuid4をモックする
#
#    - テストの準備 (Arrange)
#      - 正常系テストと同様に、各モックを設定する
#      - ただし、blob_client.upload_blobが呼び出されたときにExceptionを発生させるように設定する
#      - ダミーファイルを作成する
#
#    - テストの実行 (Act)
#      - upload_file_to_blob関数を呼び出す
#
#    - 検証 (Assert)
#      - 戻り値が期待されるエラーメッセージを含んでいることを確認するimport os
import uuid
from unittest.mock import patch, MagicMock, mock_open
import pytest
from src.utils.tools import upload_file_to_blob


@patch("src.utils.tools.uuid.uuid4")
@patch("src.utils.tools.open", new_callable=mock_open, read_data=b"test data")
@patch("src.utils.tools.BlobServiceClient")
@patch("src.utils.tools.os.getenv")
def test_upload_file_to_blob_success(
    mock_getenv, mock_blob_service_client, mock_open_file, mock_uuid
):
    """
    正常系: ファイルが正常にアップロードされ、BLOBのURLが返されることをテストします。
    """
    # --- Arrange ---
    # 環境変数のモック
    mock_getenv.side_effect = [
        "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=testkey;EndpointSuffix=core.windows.net",
        "test-container",
    ]

    # uuidのモック
    mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")

    # BlobServiceClientと関連オブジェクトのモック
    mock_blob_client = MagicMock()
    mock_blob_client.url = "https://test.blob.core.windows.net/test-container/12345678-1234-5678-1234-567812345678-test.txt"
    mock_container_client = MagicMock()
    mock_container_client.get_blob_client.return_value = mock_blob_client
    mock_blob_service_client.from_connection_string.return_value.get_container_client.return_value = (
        mock_container_client
    )
    # get_blob_clientはBlobServiceClientから直接呼び出されるように修正
    mock_service_instance = mock_blob_service_client.from_connection_string.return_value
    mock_service_instance.get_blob_client.return_value = mock_blob_client

    file_path = "test.txt"

    # --- Act ---
    result = upload_file_to_blob(file_path)

    # --- Assert ---
    # 環境変数が正しく呼び出されたか
    mock_getenv.assert_any_call("AZURE_STORAGE_CONNECTION_STRING")
    mock_getenv.assert_any_call("AZURE_STORAGE_CONTAINER_NAME")

    # BlobServiceClientが正しく初期化されたか
    mock_blob_service_client.from_connection_string.assert_called_once()

    # BlobClientが正しい名前で取得されたか
    expected_blob_name = f"{mock_uuid.return_value}-{os.path.basename(file_path)}"
    mock_service_instance.get_blob_client.assert_called_once_with(
        container="test-container", blob=expected_blob_name
    )

    # ファイルが開かれ、アップロードされたか
    mock_open_file.assert_called_once_with(file_path, "rb")
    mock_blob_client.upload_blob.assert_called_once()

    # 戻り値が期待通りか
    assert result == mock_blob_client.url


@patch("src.utils.tools.os.getenv")
def test_upload_file_to_blob_no_env_vars(mock_getenv):
    """
    異常系: 環境変数が設定されていない場合にエラーが返されることをテストします。
    """
    # --- Arrange ---
    mock_getenv.return_value = None
    file_path = "test.txt"

    # --- Act ---
    result = upload_file_to_blob(file_path)

    # --- Assert ---
    assert "エラー: 環境変数にAzure Storageの接続情報が設定されていません。" in result


@patch("src.utils.tools.os.getenv")
@patch("src.utils.tools.BlobServiceClient")
def test_upload_file_to_blob_upload_failure(mock_blob_service_client, mock_getenv):
    """
    異常系: アップロード中に例外が発生した場合にエラーが返されることをテストします。
    """
    # --- Arrange ---
    mock_getenv.side_effect = ["dummy_connection_string", "dummy_container"]
    mock_blob_service_client.from_connection_string.side_effect = Exception(
        "Connection failed"
    )
    file_path = "test.txt"

    # --- Act ---
    result = upload_file_to_blob(file_path)

    # --- Assert ---
    assert "エラー: ファイルのアップロードに失敗しました。" in result
    assert "Connection failed" in result
