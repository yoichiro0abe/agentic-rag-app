import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from datetime import datetime
import json
import os
import pandas as pd
import sys

# 現在のディレクトリをパスに追加
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# ユーティリティクラスをインポート
from utils.database import DataManager
from utils.chatbot_helper import ChatBotHelper
from utils.styles import get_custom_css

# ページ設定
st.set_page_config(
    page_title="チャットボットアプリ",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# データディレクトリのパス
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.yaml")
PROMPTS_FILE = os.path.join(DATA_DIR, "prompts.json")
CHAT_HISTORY_FILE = os.path.join(DATA_DIR, "chat_history.json")

# データディレクトリが存在しない場合は作成
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


def init_auth_config():
    """認証設定ファイルの初期化"""
    if not os.path.exists(USERS_FILE):
        # パスワードをハッシュ化
        passwords = ["123456", "abc123"]
        hasher = stauth.Hasher()
        hashed_passwords = [hasher.hash(password) for password in passwords]

        config = {
            "credentials": {
                "usernames": {
                    "admin": {
                        "email": "admin@example.com",
                        "name": "管理者",
                        "password": hashed_passwords[0],
                    },
                    "user": {
                        "email": "user@example.com",
                        "name": "ユーザー",
                        "password": hashed_passwords[1],
                    },
                }
            },
            "cookie": {
                "expiry_days": 30,
                "key": "some_signature_key",
                "name": "some_cookie_name",
            },
            "preauthorized": {"emails": ["admin@example.com"]},
        }

        with open(USERS_FILE, "w", encoding="utf-8") as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)


def init_prompts():
    """プロンプトライブラリの初期化"""
    if not os.path.exists(PROMPTS_FILE):
        default_prompts = [
            {
                "id": 1,
                "title": "一般的な質問回答",
                "content": "あなたは親切で知識豊富なアシスタントです。ユーザーの質問に対して正確で分かりやすい回答を提供してください。",
                "category": "一般",
                "created_at": datetime.now().isoformat(),
            },
            {
                "id": 2,
                "title": "技術サポート",
                "content": "あなたは技術サポートの専門家です。技術的な問題について段階的な解決方法を提供してください。",
                "category": "技術",
                "created_at": datetime.now().isoformat(),
            },
        ]
        with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_prompts, f, ensure_ascii=False, indent=2)


def init_chat_history():
    """チャット履歴の初期化"""
    if not os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def init_session_state():
    """セッション状態の初期化"""
    if "page" not in st.session_state:
        st.session_state.page = "chatbot"
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None
        st.session_state.current_chat_id = None


def save_current_chat():
    """現在のチャットを保存"""
    if st.session_state.chat_messages:
        data_manager = st.session_state.get("data_manager")
        if not data_manager:
            return

        # 最初のメッセージから50文字のプレビューを作成
        title = "新しいチャット"
        if st.session_state.chat_messages:
            first_message = st.session_state.chat_messages[0]["content"]
            title = (
                first_message[:20] + "..." if len(first_message) > 20 else first_message
            )

        # 既存のチャットを更新または新規追加
        if st.session_state.current_chat_id:
            data_manager.update_chat_session(
                st.session_state.current_chat_id,
                title=title,
                messages=st.session_state.chat_messages,
            )
        else:
            chat_data = data_manager.add_chat_session(
                title, st.session_state.chat_messages
            )
            st.session_state.current_chat_id = chat_data.get("id")


def chatbot_page():
    """チャットボット画面"""
    st.header("🤖 チャットボット")

    # チャット履歴を表示
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ユーザー入力
    if prompt := st.chat_input("メッセージを入力してください..."):
        # ユーザーメッセージを追加
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # アシスタントの応答（シンプルなエコー応答）
        response = f"申し訳ありませんが、現在はエコー機能のみです。あなたのメッセージ: {prompt}"
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": response}
        )
        with st.chat_message("assistant"):
            st.markdown(response)

        # チャット履歴を保存
        save_current_chat()


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
                        "メモリ使用量", f"{df.memory_usage(deep=True).sum():,} bytes"
                    )

                st.subheader("データプレビュー")
                st.dataframe(df.head(10))

                st.subheader("データ型情報")
                st.text(str(df.dtypes))

                st.subheader("統計情報")
                if df.select_dtypes(include=["number"]).columns.any():
                    st.dataframe(df.describe())

                # 欠損値の確認
                missing_data = df.isnull().sum()
                if missing_data.any():
                    st.subheader("欠損値")
                    st.bar_chart(missing_data[missing_data > 0])

            elif uploaded_file.type in [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ]:
                df = pd.read_excel(uploaded_file)
                st.dataframe(df.head())
                st.write(f"行数: {len(df)}, 列数: {len(df.columns)}")

            elif uploaded_file.type == "application/json":
                import json

                data = json.load(uploaded_file)
                st.json(data)

            elif uploaded_file.type == "text/plain":
                content = str(uploaded_file.read(), "utf-8")
                st.text_area("ファイル内容", content, height=300)

                # テキスト分析
                lines = content.split("\n")
                words = content.split()
                chars = len(content)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("行数", len(lines))
                with col2:
                    st.metric("単語数", len(words))
                with col3:
                    st.metric("文字数", chars)

    with tabs[1]:
        st.subheader("💬 チャット分析")

        data_manager = st.session_state.get("data_manager")
        if data_manager:
            chat_history = data_manager.load_chat_history()

            if chat_history:
                # 全体統計
                total_sessions = len(chat_history)
                total_messages = sum(
                    len(session.get("messages", [])) for session in chat_history
                )
                avg_messages_per_session = (
                    total_messages / total_sessions if total_sessions > 0 else 0
                )

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("総セッション数", total_sessions)
                with col2:
                    st.metric("総メッセージ数", total_messages)
                with col3:
                    st.metric(
                        "平均メッセージ/セッション", f"{avg_messages_per_session:.1f}"
                    )  # 日別統計
                dates = []
                for session in chat_history:
                    try:
                        date_str = session.get("date", "")[:10]  # YYYY-MM-DD部分を取得
                        dates.append(date_str)
                    except Exception:
                        continue

                if dates:
                    date_counts = pd.Series(dates).value_counts().sort_index()
                    st.subheader("日別チャット数")
                    st.bar_chart(date_counts)

                # 最も長いセッション
                longest_session = max(
                    chat_history, key=lambda x: len(x.get("messages", []))
                )
                st.subheader("最も長いセッション")
                st.write(f"タイトル: {longest_session.get('title', 'N/A')}")
                st.write(f"メッセージ数: {len(longest_session.get('messages', []))}")
                st.write(f"日付: {longest_session.get('date', 'N/A')}")

                # チャットボットヘルパーがある場合、追加の分析
                chatbot_helper = st.session_state.get("chatbot_helper")
                if chatbot_helper:
                    st.subheader("意図分析")

                    intents = []
                    for session in chat_history:
                        for message in session.get("messages", []):
                            if message.get("role") == "user":
                                intent = chatbot_helper.detect_intent(
                                    message.get("content", "")
                                )
                                intents.append(intent)

                    if intents:
                        intent_counts = pd.Series(intents).value_counts()
                        st.bar_chart(intent_counts)
            else:
                st.info("分析するチャット履歴がありません。")
        else:
            st.error("データマネージャーが初期化されていません。")

    with tabs[2]:
        st.subheader("📤 データエクスポート")

        data_manager = st.session_state.get("data_manager")
        if data_manager:
            export_type = st.selectbox(
                "エクスポートする種類", ["すべて", "チャット履歴のみ", "プロンプトのみ"]
            )

            type_mapping = {
                "すべて": "all",
                "チャット履歴のみ": "chat_history",
                "プロンプトのみ": "prompts",
            }

            if st.button("エクスポート実行"):
                export_data = data_manager.export_data(type_mapping[export_type])

                # JSONとして表示
                st.json(export_data)

                # ダウンロードリンクを提供
                import json

                json_string = json.dumps(export_data, ensure_ascii=False, indent=2)
                st.download_button(
                    label="JSONファイルとしてダウンロード",
                    data=json_string,
                    file_name=f"chatbot_export_{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                )

        # インポート機能
        st.subheader("📥 データインポート")
        uploaded_json = st.file_uploader("インポートするJSONファイル", type=["json"])

        if uploaded_json is not None:
            try:
                import_data = json.load(uploaded_json)
                st.json(import_data)

                if st.button("インポート実行"):
                    if data_manager and data_manager.import_data(import_data):
                        st.success("データのインポートが完了しました！")
                    else:
                        st.error("データのインポートに失敗しました。")
            except Exception as e:
                st.error(f"JSONファイルの読み込みに失敗しました: {e}")


def prompt_library_page():
    """プロンプトライブラリ画面"""
    st.header("📚 プロンプトライブラリ")

    # データマネージャーを取得
    data_manager = st.session_state.get("data_manager")
    if not data_manager:
        st.error("データマネージャーが初期化されていません。")
        return

    prompts = data_manager.load_prompts()

    # カテゴリフィルター
    categories = ["すべて"] + list(set(p.get("category", "一般") for p in prompts))
    selected_category = st.selectbox("カテゴリでフィルター", categories)

    # フィルタリング
    if selected_category != "すべて":
        prompts = [p for p in prompts if p.get("category") == selected_category]

    # プロンプト追加ボタン
    if st.button("➕ 新しいプロンプトを追加", use_container_width=True):
        st.session_state.show_add_prompt = True  # プロンプト追加フォーム
    if st.session_state.get("show_add_prompt", False):
        with st.form("add_prompt_form"):
            st.subheader("✨ 新しいプロンプトを追加")

            col1, col2 = st.columns([2, 1])
            with col1:
                title = st.text_input(
                    "📝 タイトル", placeholder="プロンプトのタイトルを入力"
                )
            with col2:
                category = st.selectbox(
                    "📁 カテゴリ",
                    ["一般", "技術", "創作", "分析", "営業", "教育", "その他"],
                )

            content = st.text_area(
                "💬 プロンプト内容",
                height=150,
                placeholder="プロンプトの詳細内容を入力してください...",
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("✅ 追加", use_container_width=True):
                    if title and content:
                        result = data_manager.add_prompt(title, content, category)
                        if result:
                            st.session_state.show_add_prompt = False
                            st.success("✨ プロンプトが追加されました！")
                            st.rerun()
                        else:
                            st.error("プロンプトの追加に失敗しました。")
                    else:
                        st.error("タイトルと内容を入力してください。")
            with col2:
                if st.form_submit_button("❌ キャンセル", use_container_width=True):
                    st.session_state.show_add_prompt = False
                    st.rerun()  # プロンプト一覧
    if prompts:
        st.subheader(f"📋 プロンプト一覧 (全{len(prompts)}件)")  # 検索機能
        search_term = st.text_input(
            "🔍 プロンプトを検索", placeholder="タイトルまたは内容で検索..."
        )

        if search_term:
            prompts = [
                p
                for p in prompts
                if search_term.lower() in p.get("title", "").lower()
                or search_term.lower() in p.get("content", "").lower()
            ]

        for prompt in prompts:
            with st.expander(
                f"[{prompt.get('category', '一般')}] {prompt.get('title', 'タイトルなし')}"
            ):
                st.markdown("**📄 プロンプト内容:**")
                st.text_area(
                    "内容",
                    value=prompt.get("content", ""),
                    height=100,
                    key=f"prompt_display_{prompt.get('id')}",
                    disabled=True,
                )

                # 統計情報
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"📅 作成日: {prompt.get('created_at', 'N/A')[:10]}")
                with col2:
                    usage_count = prompt.get("usage_count", 0)
                    st.info(f"📊 使用回数: {usage_count}")
                with col3:
                    st.info(f"📁 カテゴリ: {prompt.get('category', '一般')}")

                # アクションボタン
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button(
                        "✏️ 編集",
                        key=f"edit_{prompt.get('id')}",
                        use_container_width=True,
                    ):
                        st.session_state.edit_prompt_id = prompt.get("id")
                        st.session_state.show_edit_prompt = True
                        st.rerun()

                with col2:
                    if st.button(
                        "🗑️ 削除",
                        key=f"delete_{prompt.get('id')}",
                        use_container_width=True,
                    ):
                        if data_manager.delete_prompt(prompt.get("id")):
                            st.success("🗑️ プロンプトが削除されました！")
                            st.rerun()
                        else:
                            st.error("プロンプトの削除に失敗しました。")

                with col3:
                    if st.button(
                        "📋 使用",
                        key=f"use_{prompt.get('id')}",
                        use_container_width=True,
                    ):
                        # 使用回数をカウントアップ
                        data_manager.update_prompt(
                            prompt.get("id"),
                            title=prompt.get("title"),
                            content=prompt.get("content"),
                            category=prompt.get("category"),
                        )
                        st.success("プロンプトがチャットボットで使用可能になりました！")
                        st.session_state.page = "chatbot"
                        st.rerun()
    else:
        st.info(
            "📝 プロンプトがまだ登録されていません。上の「新しいプロンプトを追加」ボタンから追加してください。"
        )  # プロンプト編集フォーム
    if st.session_state.get("show_edit_prompt", False):
        edit_id = st.session_state.get("edit_prompt_id")
        edit_prompt = data_manager.get_prompt_by_id(edit_id)

        if edit_prompt:
            with st.form("edit_prompt_form"):
                st.subheader("✏️ プロンプトを編集")

                col1, col2 = st.columns([2, 1])
                with col1:
                    title = st.text_input(
                        "📝 タイトル", value=edit_prompt.get("title", "")
                    )
                with col2:
                    category = st.selectbox(
                        "📁 カテゴリ",
                        ["一般", "技術", "創作", "分析", "営業", "教育", "その他"],
                        index=[
                            "一般",
                            "技術",
                            "創作",
                            "分析",
                            "営業",
                            "教育",
                            "その他",
                        ].index(edit_prompt.get("category", "一般")),
                    )

                content = st.text_area(
                    "💬 プロンプト内容",
                    value=edit_prompt.get("content", ""),
                    height=150,
                )

                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("✅ 更新", use_container_width=True):
                        if data_manager.update_prompt(
                            edit_id, title, content, category
                        ):
                            st.session_state.show_edit_prompt = False
                            st.success("✨ プロンプトが更新されました！")
                            st.rerun()
                        else:
                            st.error("プロンプトの更新に失敗しました。")
                with col2:
                    if st.form_submit_button("❌ キャンセル", use_container_width=True):
                        st.session_state.show_edit_prompt = False
                        st.rerun()
        else:
            st.error("編集対象のプロンプトが見つかりません。")
            st.session_state.show_edit_prompt = False


def chat_history_page():
    """チャット履歴画面"""
    st.header("💬 チャット履歴")

    # データマネージャーを取得
    data_manager = st.session_state.get("data_manager")
    if not data_manager:
        st.error("データマネージャーが初期化されていません。")
        return

    chat_history = data_manager.load_chat_history()

    # 検索機能
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("🔍 検索", placeholder="チャット内容を検索...")
    with col2:
        sort_order = st.selectbox("📅 並び順", ["新しい順", "古い順"])

    if chat_history:
        # 検索フィルタリング
        filtered_history = chat_history
        if search_term:
            filtered_history = data_manager.search_chat_history(search_term)

        # ソート
        if sort_order == "新しい順":
            filtered_history = sorted(
                filtered_history, key=lambda x: x.get("date", ""), reverse=True
            )
        else:
            filtered_history = sorted(filtered_history, key=lambda x: x.get("date", ""))

        if filtered_history:
            st.subheader(f"📋 チャット履歴 ({len(filtered_history)}件)")

            for i, chat in enumerate(filtered_history):
                chat_title = chat.get("title", "タイトルなし")
                chat_preview = chat.get("preview", "")
                chat_date = chat.get("date", "N/A")
                message_count = len(chat.get("messages", []))

                # チャットカードの表示
                with st.expander(
                    f"📅 {chat_date} - {chat_title} ({message_count}メッセージ)"
                ):
                    # プレビュー表示
                    if chat_preview:
                        st.markdown(f"**📄 プレビュー:** {chat_preview}")

                    # 統計情報
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"📊 メッセージ数: {message_count}")
                    with col2:
                        st.info(f"📅 作成日: {chat_date}")
                    with col3:
                        chat_id = chat.get("id", f"unknown_{i}")
                        st.info(f"🆔 ID: {str(chat_id)[:8]}...")

                    # アクションボタン
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        new_title = st.text_input(
                            "📝 新しいタイトル",
                            value=chat_title,
                            key=f"rename_{i}",
                            placeholder="新しいタイトル",
                        )
                        if st.button(
                            "✏️ リネーム",
                            key=f"rename_btn_{i}",
                            use_container_width=True,
                        ):
                            if data_manager.update_chat_session(
                                chat.get("id"), title=new_title
                            ):
                                st.success("✅ タイトルが変更されました！")
                                st.rerun()
                            else:
                                st.error("タイトルの変更に失敗しました。")

                    with col2:
                        if st.button(
                            "🗑️ 削除", key=f"delete_chat_{i}", use_container_width=True
                        ):
                            if data_manager.delete_chat_session(chat.get("id")):
                                st.success("🗑️ チャットが削除されました！")
                                st.rerun()
                            else:
                                st.error("チャットの削除に失敗しました。")

                    with col3:
                        if st.button(
                            "▶️ 再開", key=f"resume_{i}", use_container_width=True
                        ):
                            st.session_state.chat_messages = chat.get("messages", [])
                            st.session_state.current_chat_id = chat.get("id")
                            st.session_state.page = "chatbot"
                            st.success("🚀 チャットが再開されました！")
                            st.rerun()

                    with col4:
                        if st.button(
                            "📋 詳細", key=f"details_{i}", use_container_width=True
                        ):
                            st.session_state[f"show_details_{i}"] = (
                                not st.session_state.get(f"show_details_{i}", False)
                            )
                            st.rerun()

                    # 詳細表示
                    if st.session_state.get(f"show_details_{i}", False):
                        st.markdown("**💬 メッセージ履歴:**")
                        for j, message in enumerate(chat.get("messages", [])):
                            role = message.get("role", "unknown")
                            content = message.get("content", "")
                            if role == "user":
                                st.markdown(
                                    f"**👤 ユーザー ({j + 1}):** {content[:100]}..."
                                )
                            elif role == "assistant":
                                st.markdown(
                                    f"**🤖 アシスタント ({j + 1}):** {content[:100]}..."
                                )

                            if j >= 4:  # 最初の5メッセージのみ表示
                                remaining = len(chat.get("messages", [])) - 5
                                if remaining > 0:
                                    st.markdown(f"*... 他 {remaining} メッセージ*")
                                break
        else:
            st.info("🔍 検索条件に一致するチャットが見つかりませんでした。")
    else:
        st.info("📝 チャット履歴がありません。チャットボットで会話を始めてください。")

        # チャットボットへの誘導
        if st.button("🚀 チャットボットを開始", use_container_width=True):
            st.session_state.page = "chatbot"
            st.rerun()


def display_statistics():
    """統計情報を表示"""
    if "data_manager" in st.session_state:
        data_manager = st.session_state.data_manager
        stats = data_manager.get_chat_statistics()

        # サイドバーに統計情報を表示
        with st.sidebar:
            st.markdown("### 📊 統計情報")

            # 統計カード
            col1, col2 = st.columns(2)
            with col1:
                st.metric("チャット数", stats["total_chats"])
                st.metric("プロンプト数", stats["total_prompts"])
            with col2:
                st.metric("総メッセージ数", stats["total_messages"])
                if stats["latest_chat"]:
                    st.metric("最新チャット", stats["latest_chat"][:10])


def enhanced_chatbot_page():
    """拡張されたチャットボット画面"""
    st.header("🤖 チャットボット")

    # チャットボットヘルパーを取得
    chatbot_helper = st.session_state.get("chatbot_helper")
    if not chatbot_helper:
        chatbot_helper = ChatBotHelper()
        st.session_state.chatbot_helper = chatbot_helper

    # 応答モードの選択
    col1, col2 = st.columns([3, 1])
    with col2:
        response_mode = st.selectbox(
            "応答モード", ["エコーモード", "スマートモード", "プロンプト使用"]
        )

    # プロンプト選択（プロンプト使用モードの場合）
    selected_prompt = None
    if response_mode == "プロンプト使用":
        data_manager = st.session_state.get("data_manager")
        if data_manager:
            prompts = data_manager.load_prompts()
            if prompts:
                prompt_options = {f"{p['title']} ({p['category']})": p for p in prompts}
                selected_title = st.selectbox(
                    "使用するプロンプト", list(prompt_options.keys())
                )
                selected_prompt = prompt_options[selected_title]

                with st.expander("選択されたプロンプト"):
                    st.text_area(
                        "内容",
                        value=selected_prompt["content"],
                        height=100,
                        disabled=True,
                    )

    # チャット履歴を表示
    for i, message in enumerate(st.session_state.chat_messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # メッセージの統計情報を表示（管理者のみ）
            if st.session_state.get("username") == "admin":
                with st.expander("メッセージ詳細", expanded=False):
                    st.text(f"文字数: {len(message['content'])}")
                    if message["role"] == "user":
                        intent = chatbot_helper.detect_intent(message["content"])
                        keywords = chatbot_helper.extract_keywords(message["content"])
                        st.text(f"意図: {intent}")
                        st.text(f"キーワード: {', '.join(keywords[:5])}")

    # ユーザー入力
    if prompt := st.chat_input("メッセージを入力してください..."):
        # メッセージの妥当性を検証
        is_valid, validation_message = chatbot_helper.validate_message(prompt)

        if not is_valid:
            st.error(validation_message)
            return

        # ユーザーメッセージを追加
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 応答を生成
        if response_mode == "エコーモード":
            response = f"エコー: {prompt}"
        elif response_mode == "スマートモード":
            intent = chatbot_helper.detect_intent(prompt)
            response = chatbot_helper.generate_response(prompt, intent)

            # 類似した過去の会話を表示
            data_manager = st.session_state.get("data_manager")
            if data_manager:
                similar_convs = chatbot_helper.find_similar_conversations(
                    prompt, data_manager.load_chat_history()
                )
                if similar_convs:
                    with st.expander("類似した過去の会話"):
                        for conv in similar_convs[:3]:
                            st.text(f"類似度: {conv['similarity']:.2f}")
                            st.text(f"過去の質問: {conv['user_message'][:100]}...")
                            if "assistant_response" in conv:
                                st.text(
                                    f"過去の回答: {conv['assistant_response'][:100]}..."
                                )
                            st.markdown("---")

        elif response_mode == "プロンプト使用" and selected_prompt:
            response = f"[{selected_prompt['title']}を使用]\n\n{selected_prompt['content']}\n\nユーザーの質問: {prompt}\n\n申し訳ありませんが、実際のAI応答機能は実装されていません。"

        else:
            response = "申し訳ありませんが、適切な応答を生成できませんでした。"

        # アシスタントの応答を追加
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": response}
        )
        with st.chat_message("assistant"):
            st.markdown(response)

        # チャット履歴を保存
        save_current_chat()

        # 応答候補を表示
        if response_mode == "スマートモード":
            suggestions = chatbot_helper.get_response_suggestions(prompt)
            if suggestions:
                with st.expander("他の応答候補"):
                    for suggestion in suggestions:
                        if st.button(
                            suggestion,
                            key=f"suggestion_{len(st.session_state.chat_messages)}_{suggestion[:20]}",
                        ):
                            st.session_state.chat_messages.append(
                                {"role": "assistant", "content": suggestion}
                            )
                            save_current_chat()
                            st.rerun()


def sidebar_menu():
    """サイドバーのメニュー"""
    with st.sidebar:
        st.title("🤖 チャットボットアプリ")
        st.markdown("---")

        # ログインユーザー情報
        if st.session_state.get("name"):
            st.write(f"ようこそ, {st.session_state['name']}さん！")
            st.markdown("---")

        # メニューボタン
        if st.button("🤖 チャットボット", use_container_width=True):
            st.session_state.page = "chatbot"
            st.rerun()

        if st.button("📊 分析ボット", use_container_width=True):
            st.session_state.page = "analysis"
            st.rerun()

        if st.button("💬 チャット履歴", use_container_width=True):
            st.session_state.page = "chat_history"
            st.rerun()

        if st.button("📚 プロンプトライブラリ", use_container_width=True):
            st.session_state.page = "prompt_library"
            st.rerun()

        st.markdown("---")

        # 新しいチャットボタン
        if st.button("🆕 新しいチャット", use_container_width=True):
            st.session_state.chat_messages = []
            st.session_state.current_chat_id = None
            st.session_state.page = "chatbot"
            st.rerun()

        st.markdown("---")

        # ログアウトボタン
        if st.button("🚪 ログアウト", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def main():
    """メイン関数"""
    # カスタムCSSを適用
    st.markdown(get_custom_css(), unsafe_allow_html=True)

    # データマネージャーとチャットボットヘルパーを初期化
    if "data_manager" not in st.session_state:
        st.session_state.data_manager = DataManager(DATA_DIR)
    if "chatbot_helper" not in st.session_state:
        st.session_state.chatbot_helper = ChatBotHelper()

    # 初期化
    init_auth_config()
    init_prompts()
    init_chat_history()
    init_session_state()

    # 認証設定の読み込み
    with open(USERS_FILE, encoding="utf-8") as file:
        config = yaml.load(file, Loader=SafeLoader)  # 認証器の作成
    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )  # ログイン
    authenticator.login(location="main")

    # 認証状態の確認
    if st.session_state.get("authentication_status") is False:
        st.error("ユーザー名またはパスワードが正しくありません")
    elif st.session_state.get("authentication_status") is None:
        st.warning("ユーザー名とパスワードを入力してください")

        # ログイン情報を美しく表示
        st.markdown(
            """
        <div class='custom-info'>
            <h3>📋 デフォルトのログイン情報</h3>
            <p><strong>管理者:</strong> ユーザー名: admin, パスワード: 123456</p>            <p><strong>一般ユーザー:</strong> ユーザー名: user, パスワード: abc123</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    elif st.session_state.get("authentication_status"):
        # ログイン成功時のウェルカムメッセージ
        st.markdown(
            f"""
        <div class='main-header'>
            <h1>🤖 チャットボットアプリへようこそ！</h1>
            <p>こんにちは、{st.session_state.get('name', 'ユーザー')}さん！素晴らしい一日をお過ごしください。</p>
        </div>
        """,
            unsafe_allow_html=True,
        )  # サイドバーメニューと統計情報を表示
        sidebar_menu()
        display_statistics()

        # ページルーティング
        if st.session_state.page == "chatbot":
            enhanced_chatbot_page()
        elif st.session_state.page == "analysis":
            enhanced_analysis_bot_page()
        elif st.session_state.page == "chat_history":
            chat_history_page()
        elif st.session_state.page == "prompt_library":
            prompt_library_page()


if __name__ == "__main__":
    main()
