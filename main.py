import os
from datetime import datetime
import pandas as pd
from pykrx import stock
from telegram import Bot

DATE_FMT = "%Y%m%d"


def get_business_day() -> str:
    today = datetime.now().strftime(DATE_FMT)
    return stock.get_nearest_business_day_in_a_week(today)


def pick_top10(date: str, market: str) -> pd.DataFrame:
    # ✅ 여기서 OHLCV를 가져오면, 보통 거래대금(거래대금/거래대금(원))이 같이 들어있음
    df = stock.get_market_ohlcv_by_ticker(date, market=market)
    if df is None or df.empty:
        return pd.DataFrame()

    # 등락률 컬럼 확인
    if "등락률" not in df.columns:
        return pd.DataFrame()

    # 거래대금 컬럼명은 버전에 따라 다를 수 있어서 자동 탐색
    value_candidates = ["거래대금", "거래대금(원)", "거래대금(백만)"]
    value_col = next((c for c in value_candidates if c in df.columns), None)
    if value_col is None:
        raise RuntimeError(f"{market}: 거래대금 컬럼을 못 찾았어. columns={list(df.columns)}")

    # 10% 이상 필터 + 거래대금 TOP10
    df = df[df["등락률"] >= 10].sort_values(value_col, ascending=False).head(10)

    if df.empty:
        return pd.DataFrame()

    df["종목명"] = [stock.get_market_ticker_name(t) for t in df.index]
    df = df.reset_index().rename(columns={"index": "티커"})
    df = df.rename(columns={"등락률": "chg_pct", value_col: "거래대금"})
    return df[["티커", "종목명", "chg_pct", "거래대금", "종가"]]


def format_block(title: str, df: pd.DataFrame) -> str:
    if df.empty:
        return f"\n[{title}] 해당 없음"

    lines = [f"\n[{title}] 10%↑ 거래대금 TOP10"]
    for i, row in df.iterrows():
        lines.append(
            f"{i+1}. {row['종목명']}({row['티커']}) | "
            f"{row['chg_pct']:.2f}% | "
            f"거래대금 {int(row['거래대금']):,} | "
            f"종가 {int(row['종가']):,}"
        )
    return "\n".join(lines)


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    date = get_business_day()

    kospi = pick_top10(date, "KOSPI")
    kosdaq = pick_top10(date, "KOSDAQ")

    message = (
        f"📌 {date} 장마감 요약\n"
        f"기준: 전일 대비 10% 이상 상승 + 거래대금 상위 10\n"
        + format_block("KOSPI", kospi)
        + format_block("KOSDAQ", kosdaq)
    )

    bot = Bot(token=token)
    bot.send_message(chat_id=chat_id, text=message)


if __name__ == "__main__":
    main()
