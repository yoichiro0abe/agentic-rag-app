import streamlit as st
import pandas as pd
import json
import os
import sys

# パスの設定を改善
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from utils.database import DataManager
except ImportError as e:
    st.error(f"モジュールのインポートエラー: {e}")
    st.stop()


def enhanced_analysis_bot_page():
    """拡張された分析ボット画面"""
    st.header("📊 分析ボット")

    tabs = st.tabs(["ファイル分析", "チャット分析", "データエクスポート"])

    with tabs[0]:
        st.subheader("📁 ファイル分析")

        # ファイルアップロード
        uploaded_file = st.file_uploader(
            "分析するファイルをアップロードしてください",
            type=["csv", "xlsx", "json", "txt"],
        )

        if uploaded_file is not None:
            st.success(f"ファイル '{uploaded_file.name}' がアップロードされました。")

            # ファイルタイプに応じた分析
            if uploaded_file.type == "text/csv":
                df = pd.read_csv(uploaded_file)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("行数", len(df))
                    st.metric("列数", len(df.columns))
                with col2:
                    st.metric("データサイズ", f"{uploaded_file.size:,} bytes")
                    st.metric(
                        "欠損値",
                        f"{df.isnull().sum().sum():,} 個" if not df.empty else "0 個",
                    )

                # データプレビュー
                st.subheader("📋 データプレビュー")
                st.dataframe(df.head(10))

                # 基本統計情報
                if not df.empty:
                    st.subheader("📈 基本統計情報")
                    st.dataframe(df.describe())

                    # 列の詳細情報
                    st.subheader("🔍 列の詳細情報")
                    col_info = pd.DataFrame(
                        {
                            "データ型": df.dtypes,
                            "欠損値数": df.isnull().sum(),
                            "欠損値率": (df.isnull().sum() / len(df) * 100).round(2),
                            "ユニーク値数": df.nunique(),
                        }
                    )
                    st.dataframe(col_info)

            elif uploaded_file.type in ["application/json", "text/plain"]:
                try:
                    content = uploaded_file.read().decode("utf-8")
                    if uploaded_file.type == "application/json":
                        data = json.loads(content)
                        st.subheader("📋 JSON構造")
                        st.json(data)

                        st.metric("データサイズ", f"{len(content):,} 文字")
                        if isinstance(data, list):
                            st.metric("配列要素数", len(data))
                        elif isinstance(data, dict):
                            st.metric("キー数", len(data.keys()))
                    else:
                        st.subheader("📋 テキスト内容")
                        st.text_area("内容", content, height=300)

                        lines = content.split("\n")
                        st.metric("行数", len(lines))
                        st.metric("文字数", len(content))
                        st.metric("単語数", len(content.split()))

                except Exception as e:
                    st.error(f"ファイルの読み込みに失敗しました: {str(e)}")

    with tabs[1]:
        st.subheader("💬 チャット分析")

        # データマネージャーの初期化
        if "data_manager" not in st.session_state:
            DATA_DIR = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
            )
            st.session_state.data_manager = DataManager(DATA_DIR)

        data_manager = st.session_state.get("data_manager")
        if data_manager:
            chat_history = data_manager.load_chat_history()

            if chat_history:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("総チャット数", len(chat_history))
                with col2:
                    total_messages = sum(
                        len(chat.get("messages", [])) for chat in chat_history
                    )
                    st.metric("総メッセージ数", total_messages)
                with col3:
                    avg_messages = (
                        total_messages / len(chat_history) if chat_history else 0
                    )
                    st.metric("チャット当たり平均メッセージ数", f"{avg_messages:.1f}")

                # 最新のチャット活動
                st.subheader("📅 最新のチャット活動")
                recent_chats = sorted(
                    chat_history, key=lambda x: x.get("created_at", ""), reverse=True
                )[:5]

                for chat in recent_chats:
                    with st.expander(f"💬 {chat.get('title', '無題のチャット')}"):
                        st.write(f"📅 作成日時: {chat.get('created_at', '不明')}")
                        st.write(f"💬 メッセージ数: {len(chat.get('messages', []))}")

                        messages = chat.get("messages", [])
                        if messages:
                            st.write("最初のメッセージ:")
                            st.write(f"👤 {messages[0].get('content', '')[:100]}...")
            else:
                st.info("チャット履歴がありません。")

    with tabs[2]:
        st.subheader("📤 データエクスポート")

        # データマネージャーの初期化
        if "data_manager" not in st.session_state:
            DATA_DIR = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
            )
            st.session_state.data_manager = DataManager(DATA_DIR)

        data_manager = st.session_state.get("data_manager")

        export_type = st.selectbox(
            "エクスポートするデータを選択", ["チャット履歴", "プロンプトライブラリ"]
        )

        if st.button("📥 エクスポート", use_container_width=True):
            try:
                if export_type == "チャット履歴" and data_manager:
                    chat_history = data_manager.load_chat_history()
                    if chat_history:
                        # チャット履歴をCSV形式で変換
                        export_data = []
                        for chat in chat_history:
                            for message in chat.get("messages", []):
                                export_data.append(
                                    {
                                        "チャットID": chat.get("id"),
                                        "チャットタイトル": chat.get("title"),
                                        "作成日時": chat.get("created_at"),
                                        "ロール": message.get("role"),
                                        "内容": message.get("content"),
                                    }
                                )

                        if export_data:
                            df = pd.DataFrame(export_data)
                            csv = df.to_csv(index=False, encoding="utf-8-sig")
                            st.download_button(
                                label="💾 チャット履歴をCSVでダウンロード",
                                data=csv,
                                file_name="chat_history.csv",
                                mime="text/csv",
                            )
                        else:
                            st.warning("エクスポートするデータがありません。")
                    else:
                        st.warning("チャット履歴がありません。")

                elif export_type == "プロンプトライブラリ" and data_manager:
                    prompts = data_manager.load_prompts()
                    if prompts:
                        df = pd.DataFrame(prompts)
                        csv = df.to_csv(index=False, encoding="utf-8-sig")
                        st.download_button(
                            label="💾 プロンプトライブラリをCSVでダウンロード",
                            data=csv,
                            file_name="prompts.csv",
                            mime="text/csv",
                        )
                    else:
                        st.warning("プロンプトライブラリにデータがありません。")

            except Exception as e:
                st.error(f"エクスポートに失敗しました: {str(e)}")


# このページが直接実行された場合
if __name__ == "__main__":
    enhanced_analysis_bot_page()
