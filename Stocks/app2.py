import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- アプリ設定 ---
st.set_page_config(layout="wide", page_title="ポートフォリオ分析アプリ")

# --- 株価取得関数 ---
@st.cache_data
def get_stock_data(tickers, start_date, end_date):
    all_data = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start_date - timedelta(days=7), end=end_date)
            if not df.empty:
                all_data[ticker] = df['Adj Close']
        except Exception as e:
            st.warning(f"{ticker} の取得に失敗: {e}")
    return pd.DataFrame(all_data)

@st.cache_data
def get_jp_stock_list():
    try:
        url = 'https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls'
        df = pd.read_excel(url, header=2, usecols=['コード', '銘柄名'])
        df.columns = ['code', 'name']
        df['code'] = df['code'].astype(str) + '.T'
        df['display'] = df['name'] + ' (' + df['code'] + ')'
        return df.dropna()
    except:
        return pd.DataFrame()

# --- 初期化 ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

# --- タイトル ---
st.title("📊 ポートフォリオ分析アプリ")

# --- 1. ポートフォリオ設定 ---
st.header("1. ポートフォリオ設定")
jp_stocks_df = get_jp_stock_list()

# --- 銘柄追加 ---
st.subheader("銘柄の追加")
if not jp_stocks_df.empty:
    selected_stock = st.selectbox(
        "会社名または銘柄コードで検索",
        options=jp_stocks_df['display'],
        index=None,
        placeholder="銘柄を選択"
    )
    if selected_stock:
        ticker = selected_stock.split('(')[-1].replace(')', '')
        name = ' '.join(selected_stock.split(' ')[:-1])
        if ticker not in st.session_state.portfolio:
            st.session_state.portfolio[ticker] = {'name': name, 'invest_amount': None}
            st.rerun()
else:
    st.warning("銘柄リストを取得できません。手動で追加してください。")

# 手動追加
with st.form("manual_add", clear_on_submit=True):
    ticker_input = st.text_input("銘柄コードを入力 (例: AAPL, 7203.T)").upper()
    submitted = st.form_submit_button("追加")
    if submitted and ticker_input:
        if ticker_input not in st.session_state.portfolio:
            try:
                stock_name = yf.Ticker(ticker_input).info.get('longName', ticker_input)
            except:
                stock_name = ticker_input
            st.session_state.portfolio[ticker_input] = {'name': stock_name, 'invest_amount': None}
            st.rerun()

# --- ポートフォリオ表示 ---
if st.session_state.portfolio:
    st.subheader("現在のポートフォリオ")
    for ticker, detail in list(st.session_state.portfolio.items()):
        col1, col2, col3 = st.columns([5, 3, 1])
        col1.write(f"**{detail['name']}** ({ticker})")
        with col2.form(key=f"form_{ticker}"):
            amount = st.number_input("投資金額 (円)", value=detail.get('invest_amount') or 0, step=10000, format="%d", key=f"amount_{ticker}")
            if st.form_submit_button("確定"):
                st.session_state.portfolio[ticker]['invest_amount'] = amount
                st.rerun()
        if col3.button("削除", key=f"del_{ticker}"):
            del st.session_state.portfolio[ticker]
            st.rerun()

# --- 2. 期間設定 ---
st.header("2. シミュレーション期間設定")
today = datetime.now().date()
col1, col2 = st.columns(2)
start_date = col1.date_input("開始日", today - timedelta(days=365))
end_date = col2.date_input("終了日", today)

# --- 3. 分析実行 ---
st.header("3. 分析実行")
if st.button("分析を開始", type="primary", use_container_width=True):
    portfolio = {k: v for k, v in st.session_state.portfolio.items() if v['invest_amount']}
    if not portfolio:
        st.error("投資金額が設定されていません。")
    else:
        tickers = list(portfolio.keys())
        with st.spinner("株価データを取得中..."):
            df_prices = get_stock_data(tickers, start_date, end_date)

        if df_prices.empty:
            st.error("株価データが取得できませんでした。")
        else:
            # 分析開始
            st.subheader("📈 分析結果")
            initial_total = 0
            final_total = 0
            summary = []
            weights = {}

            for ticker, detail in portfolio.items():
                amount = detail['invest_amount']
                prices = df_prices[ticker].dropna()
                if prices.empty:
                    continue
                shares = amount / prices.iloc[0]
                final_value = shares * prices.iloc[-1]
                pl = final_value - amount
                ret = (pl / amount) * 100
                summary.append({
                    "銘柄": detail['name'],
                    "初期投資額": f"{amount:,.0f} 円",
                    "最終評価額": f"{final_value:,.0f} 円",
                    "損益": f"{pl:,.0f} 円",
                    "リターン率": f"{ret:.2f} %"
                })
                initial_total += amount
                final_total += final_value
                weights[ticker] = amount

            if summary:
                st.dataframe(pd.DataFrame(summary), use_container_width=True)

                st.subheader("全体サマリー")
                pl_total = final_total - initial_total
                ret_total = (pl_total / initial_total) * 100 if initial_total > 0 else 0

                col1, col2, col3 = st.columns(3)
                col1.metric("初期合計", f"{initial_total:,.0f} 円")
                col2.metric("最終評価額", f"{final_total:,.0f} 円")
                col3.metric("損益", f"{pl_total:,.0f} 円", f"{ret_total:.2f} %")

                # --- チャート追加 ---
                st.subheader("📊 ポートフォリオ評価額の推移")
                weights = {k: v / initial_total for k, v in weights.items()}
                norm = df_prices / df_prices.iloc[0]
                portfolio_value = norm.mul(pd.Series(weights)).sum(axis=1) * initial_total
                st.line_chart(portfolio_value)

                # リスク・リターン分析
                st.subheader("📉 ポートフォリオのリスクとリターン")
                daily_returns = df_prices.pct_change().dropna()
                weighted_returns = daily_returns.mul(pd.Series(weights), axis=1).sum(axis=1)
                mean_daily = weighted_returns.mean()
                std_daily = weighted_returns.std()
                sharpe_ratio = (mean_daily / std_daily) * np.sqrt(252)

                st.write(f"📌 **年間リターン（期待値）:** {mean_daily * 252:.2%}")
                st.write(f"📌 **年間リスク（標準偏差）:** {std_daily * np.sqrt(252):.2%}")
                st.write(f"📌 **シャープレシオ:** {sharpe_ratio:.2f}")
            else:
                st.warning("分析可能なデータがありません。")
