import pandas as pd
import os
from datetime import datetime
from typing import Dict, List, Tuple


class DefectRateCalculator:
    """不良率計算クラス"""

    def __init__(self, data_file_path: str):
        """
        初期化

        Args:
            data_file_path (str): CSVファイルのパス
        """
        self.data_file_path = data_file_path
        self.df = None

    def load_data(self) -> pd.DataFrame:
        """
        CSVデータを読み込み

        Returns:
            pd.DataFrame: 読み込まれたデータフレーム
        """
        try:
            self.df = pd.read_csv(self.data_file_path)
            # 年月日列を日付型に変換
            self.df["年月日"] = pd.to_datetime(self.df["年月日"])
            return self.df
        except Exception as e:
            raise Exception(f"データの読み込みに失敗しました: {e}")

    def calculate_daily_defect_rate(
        self, sku: str, year: int, month: int
    ) -> pd.DataFrame:
        """
        指定されたSKUの指定月の日別不良率を計算

        Args:
            sku (str): SKU番号
            year (int): 年
            month (int): 月

        Returns:
            pd.DataFrame: 日別不良率データ
        """
        if self.df is None:
            self.load_data()

        # 指定年月のデータをフィルタリング
        filtered_df = self.df[
            (self.df["年月日"].dt.year == year)
            & (self.df["年月日"].dt.month == month)
            & (self.df["SKU"] == sku)
        ].copy()

        if filtered_df.empty:
            raise ValueError(f"{year}年{month}月の{sku}のデータが見つかりません")

        # 不良率を計算
        filtered_df["総生産数"] = filtered_df["良品数"] + filtered_df["不良数"]
        filtered_df["不良率(%)"] = (
            filtered_df["不良数"] / filtered_df["総生産数"] * 100
        ).round(3)

        # 日付順にソート
        filtered_df = filtered_df.sort_values("年月日")

        # 必要な列のみを選択
        result_df = filtered_df[
            ["年月日", "良品数", "不良数", "総生産数", "不良率(%)"]
        ].copy()
        result_df["日"] = result_df["年月日"].dt.day

        return result_df

    def get_monthly_summary(self, sku: str, year: int, month: int) -> Dict[str, float]:
        """
        月間サマリーを取得

        Args:
            sku (str): SKU番号
            year (int): 年
            month (int): 月

        Returns:
            Dict[str, float]: 月間サマリー
        """
        daily_data = self.calculate_daily_defect_rate(sku, year, month)

        total_good = daily_data["良品数"].sum()
        total_defect = daily_data["不良数"].sum()
        total_production = total_good + total_defect
        overall_defect_rate = (
            (total_defect / total_production * 100) if total_production > 0 else 0
        )

        return {
            "月間総良品数": total_good,
            "月間総不良数": total_defect,
            "月間総生産数": total_production,
            "月間平均不良率(%)": round(overall_defect_rate, 3),
            "最高不良率(%)": daily_data["不良率(%)"].max(),
            "最低不良率(%)": daily_data["不良率(%)"].min(),
            "生産日数": len(daily_data),
        }

    def display_results(self, sku: str, year: int, month: int) -> None:
        """
        結果を表示

        Args:
            sku (str): SKU番号
            year (int): 年
            month (int): 月
        """
        daily_data = self.calculate_daily_defect_rate(sku, year, month)
        monthly_summary = self.get_monthly_summary(sku, year, month)

        print(f"\n=== {year}年{month}月の{sku}日別不良率分析 ===\n")

        # 日別データ表示
        print("【日別データ】")
        print(
            daily_data[["日", "良品数", "不良数", "総生産数", "不良率(%)"]].to_string(
                index=False
            )
        )

        print(f"\n【月間サマリー】")
        for key, value in monthly_summary.items():
            if isinstance(value, float):
                print(f"{key}: {value:,.3f}")
            else:
                print(f"{key}: {value:,}")


def main():
    """メイン実行関数"""
    # データファイルのパス
    data_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "sampledata",
        "mes_total.csv",
    )

    try:
        # 不良率計算器を初期化
        calculator = DefectRateCalculator(data_file_path)

        # 2024年6月のSKU001の日別不良率を計算・表示
        calculator.display_results("SKU001", 2025, 6)

    except Exception as e:
        print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    main()
