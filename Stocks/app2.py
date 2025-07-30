import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- アプリケーションの設定 ---
st.set_page_config(layout="wide", page_title="ポートフォリオ分析アプリ")
st.title("📊 投資ポートフォリオ分析アプリ")

# --- データ取得関数（キャッシュ機能付き）---
@st.cache_data
def get_stock_data(tickers, start_date, end_date):
    """指定された銘柄リストの株価データをyfinanceから取得する"""
    df = yf.download(tickers, start=start_date, end=end_date)['Adj Close']
    return df.ffill().bfill() # 欠損値を前後で補完

@st.cache_data
def get_stock_name(ticker):
    """銘柄コードから企業名を取得する"""
    try:
        stock_info = yf.Ticker(ticker).info
        if 'longName' in stock_info:
            return stock_info['longName']
        elif 'shortName' in stock_info:
            return stock_info['shortName']
        return ticker
    except Exception:
        return ticker

# --- サイドバー：ポートフォリオ設定 ---
st.sidebar.header("ポートフォリオ設定")

# セッションステートでポートフォリオを管理
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}  # {'銘柄コード': {'name': '企業名', 'invest_amount': 0}}

# 銘柄追加フォーム
with st.sidebar.form("add_stock_form", clear_on_submit=True):
    ticker_input = st.text_input("銘柄コードを入力 (例: 7203.T)", "").upper()
    submitted = st.form_submit_button("銘柄を追加")
    if submitted and ticker_input:
        if ticker_input not in st.session_state.portfolio:
            stock_name = get_stock_name(ticker_input)
            st.session_state.portfolio[ticker_input] = {'name': stock_name, 'invest_amount': 0}
            st.sidebar.success(f"'{stock_name}' を追加しました。")
        else:
            st.sidebar.warning(f"'{st.session_state.portfolio[ticker_input]['name']}' は既に追加済みです。")

# ポートフォリオの表示と投資金額設定、削除
st.sidebar.subheader("現在のポートフォリオ")
if not st.session_state.portfolio:
    st.sidebar.info("ポートフォリオに銘柄がありません。")
else:
    for ticker, details in list(st.session_state.portfolio.items()):
        col1, col2, col3 = st.sidebar.columns([3, 2, 1])
        with col1:
            st.write(f"**{details['name']}** ({ticker})")
        with col2:
            new_amount = st.number_input(f"金額({ticker})", min_value=0, value=details['invest_amount'], step=10000, key=f"amount_{ticker}")
            st.session_state.portfolio[ticker]['invest_amount'] = new_amount
        with col3:
            if st.button("削除", key=f"delete_{ticker}"):
                del st.session_state.portfolio[ticker]
                st.rerun()

# シミュレーション期間設定
st.sidebar.subheader("シミュレーション期間")
today = datetime.now().date()
start_date = st.sidebar.date_input("開始日", today - timedelta(days=365*3), max_value=today - timedelta(days=1))
end_date = st.sidebar.date_input("終了日", today, max_value=today)


# --- メインコンテンツ ---
portfolio_with_investment = {t: d for t, d in st.session_state.portfolio.items() if d.get('invest_amount', 0) > 0}

if not portfolio_with_investment:
    st.info("左のサイドバーで銘柄を追加し、投資金額を設定してください。")
else:
    total_investment = sum(d['invest_amount'] for d in portfolio_with_investment.values())

    # 1. ポートフォリオの金額分散（円グラフ）
    st.header("ポートフォリオ構成")
    df_pie = pd.DataFrame([
        {'銘柄': d['name'], '投資金額': d['invest_amount']}
        for t, d in portfolio_with_investment.items()
    ])
    fig_pie = px.pie(df_pie, values='投資金額', names='銘柄', title='金額構成比', hole=0.3)
    st.plotly_chart(fig_pie, use_container_width=True)

    # 2. パフォーマンス分析
    st.header("パフォーマンス分析")
    tickers = list(portfolio_with_investment.keys())
    # TOPIXも同時に取得
    tickers_with_topix = tickers + ['^N225'] # 日経平均を比較対象に

    try:
        # --- データ取得と加工 ---
        all_prices = get_stock_data(tickers_with_topix, start_date, end_date)
        
        # ポートフォリオと日経平均のデータに分ける
        df_prices = all_prices[tickers]
        benchmark_prices = all_prices['^N225']

        # ポートフォリオ価値の計算
        portfolio_daily_value = pd.Series(0.0, index=df_prices.index)
        for ticker, details in portfolio_with_investment.items():
            first_price = df_prices[ticker].dropna().iloc[0]
            if pd.notna(first_price) and first_price > 0: # ゼロ除算エラーを回避
                initial_shares = details['invest_amount'] / first_price
                portfolio_daily_value += initial_shares * df_prices[ticker]

        # --- グラフ描画 ---
        # 基準化 (開始日を100とする)
        portfolio_norm = portfolio_daily_value / portfolio_daily_value.dropna().iloc[0] * 100
        benchmark_norm = benchmark_prices / benchmark_prices.dropna().iloc[0] * 100

        fig_performance = go.Figure()
        fig_performance.add_trace(go.Scatter(x=portfolio_norm.index, y=portfolio_norm, mode='lines', name='ポートフォリオ'))
        fig_performance.add_trace(go.Scatter(x=benchmark_norm.index, y=benchmark_norm, mode='lines', name='日経平均株価', line=dict(dash='dash')))
        fig_performance.update_layout(title='パフォーマンス推移 (開始日を100)', yaxis_title='価値')
        st.plotly_chart(fig_performance, use_container_width=True)

        # --- サマリー表示 ---
        st.header("分析サマリー")
        # リターン計算
        total_return_port = (portfolio_norm.iloc[-1] / portfolio_norm.iloc[0] - 1) * 100
        total_return_bm = (benchmark_norm.iloc[-1] / benchmark_norm.iloc[0] - 1) * 100
        
        num_years = (end_date - start_date).days / 365.25
        annualized_return_port = ((1 + total_return_port / 100)**(1/num_years) - 1) * 100 if num_years > 0 else 0
        annualized_return_bm = ((1 + total_return_bm / 100)**(1/num_years) - 1) * 100 if num_years > 0 else 0

        # リスク（標準偏差）計算
        daily_returns_port = portfolio_daily_value.pct_change().dropna()
        volatility_port = daily_returns_port.std() * (252**0.5) * 100 # 年率換算

        col1, col2 = st.columns(2)
        with col1:
            st.metric("ポートフォリオ トータルリターン", f"{total_return_port:.2f}%")
            st.metric("ポートフォリオ 年率リターン", f"{annualized_return_port:.2f}%")
            st.metric("ポートフォリオ リスク(年率)", f"{volatility_port:.2f}%")
        with col2:
            st.metric("日経平均 トータルリターン", f"{total_return_bm:.2f}%")
            st.metric("日経平均 年率リターン", f"{annualized_return_bm:.2f}%")

    except Exception as e:
        st.error(f"分析中にエラーが発生しました。期間や銘柄コードを見直してください。エラー: {e}")
