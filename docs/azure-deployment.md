# Azure App Service デプロイメント設定

## 必要な環境変数設定

Azure App Serviceでアプリケーションを実行する際は、以下の環境変数を設定してください：

### 必須設定
```bash
# 永続ストレージの有効化（Linuxカスタムコンテナの場合）
az webapp config appsettings set \
  --resource-group <your-resource-group> \
  --name <your-app-name> \
  --settings WEBSITES_ENABLE_APP_SERVICE_STORAGE=true

# その他の環境変数
AZURE_AI_AGENT_ENDPOINT=<your-azure-openai-endpoint>
AZURE_API_KEY=<your-azure-openai-key>
AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME=<your-model-deployment-name>
AZURE_API_VERSION=<api-version>
```

### ストレージ設定について
- `/home/site`ディレクトリは永続化されます
- 作業ディレクトリは`/home/site/work`に自動作成されます
- App Service Planのストレージクォータに含まれます

### トラブルシューティング
1. **ディスク容量不足エラー**:
   - `/home`ディレクトリ以外にファイルを書き込んでいないか確認
   - 不要なファイルを削除

2. **権限エラー**:
   - `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`が設定されているか確認

3. **パフォーマンス問題**:
   - 大量のファイル操作は避ける
   - 一時ファイルは適切にクリーンアップ
