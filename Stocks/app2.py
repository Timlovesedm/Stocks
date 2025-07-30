import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import jpholiday

# --- アプリケーションの設定 ---
st.set_page_config(layout="centered", page_title="ポートフォリオ分析アプリ")

# --- データ取得関数（キャッシュ機能付き）---
@st.cache_data
def get_stock_data(tickers, start_date, end_date):
    """指定された銘柄リストの株価データをyfinanceから取得する"""
    df = yf.download(tickers, start=start_date, end=end_date)['Adj Close']
    return df

@st.cache_data
def get_jp_stock_list():
    """東証上場銘柄のリストを取得する"""
    try:
        url = 'https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls'
        df_jp_stocks = pd.read_excel(url, header=2)
        df_jp_stocks = df_jp_stocks[['コード', '銘柄名']]
        df_jp_stocks.columns = ['code', 'name']
        df_jp_stocks['code'] = df_jp_stocks['code'].astype(str) + '.T'
        df_jp_stocks['display'] = df_jp_stocks['name'] + ' (' + df_jp_stocks['code'] + ')'
        return df_jp_stocks
    except Exception:
        return pd.DataFrame() # エラー時は空のデータフレームを返す

# --- 初期化 ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}  # {'銘柄コード': {'name': '企業名', 'invest_amount': 0}}

# --- アプリ本体 ---
st.title("📊 ポートフォリオ分析アプリ")

# --- ポートフォリオ設定 ---
st.header("1. ポートフォリオ設定")

# 銘柄検索と追加
jp_stocks_df = get_jp_stock_list()
if not jp_stocks_df.empty:
    selected_stock = st.selectbox(
        "会社名または銘柄コードで検索",
        options=jp_stocks_df['display'],
        index=None,
        placeholder="銘柄を検索・選択してください"
    )
    if selected_stock:
        ticker = selected_stock.split('(')[-1].replace(')', '')
        stock_name = ' '.join(selected_stock.split(' ')[:-1])
        if ticker not in st.session_state.portfolio:
            st.session_state.portfolio[ticker] = {'name': stock_name, 'invest_amount': None}
            st.rerun()
else:
    st.warning("現在、銘柄リストを取得できません。手動で入力してください。")
    ticker_input = st.text_input("銘柄コードを手動入力 (例: 7203.T)").upper()
    if st.button("手動で追加") and ticker_input:
         st.session_state.portfolio[ticker_input] = {'name': ticker_input, 'invest_amount': None}


# 現在のポートフォリオと投資金額の設定
if st.session_state.portfolio:
    st.subheader("現在のポートフォリオ")
    for ticker, details in list(st.session_state.portfolio.items()):
        col1, col2, col3 = st.columns([4, 2, 1])
        with col1:
            st.write(f"**{details['name']}** ({ticker})")
        with col2:
            # Enterで金額を確定させるためのフォーム
            with st.form(key=f"form_{ticker}"):
                new_amount = st.number_input(
                    "投資金額 (円)",
                    value=details.get('invest_amount'),
                    placeholder="金額を入力",
                    step=10000,
                    format="%d",
                    key=f"amount_{ticker}"
                )
                if st.form_submit_button("確定"):
                    st.session_state.portfolio[ticker]['invest_amount'] = new_amount
                    st.rerun()
        with col3:
            if st.button("削除", key=f"delete_{ticker}"):
                del st.session_state.portfolio[ticker]
                st.rerun()

st.divider()

# --- シミュレーション期間設定 ---
st.header("2. シミュレーション期間設定")
today = datetime.now().date()
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("開始日", today - timedelta(days=365*1), max_value=today - timedelta(days=1))
with col2:
    end_date = st.date_input("終了日", today, max_value=today)

st.divider()

# --- 分析実行 ---
st.header("3. 分析実行")
if st.button("分析を開始する", type="primary", use_container_width=True):
    portfolio_with_investment = {t: d for t, d in st.session_state.portfolio.items() if d.get('invest_amount') is not None and d.get('invest_amount', 0) > 0}

    if not portfolio_with_investment:
        st.error("投資金額が設定された銘柄がありません。")
    else:
        tickers = list(portfolio_with_investment.keys())
        
        with st.spinner("株価データを取得・分析中です..."):
            try:
                # --- データ取得と加工 ---
                all_prices = get_stock_data(tickers, start_date, end_date)
                
                # --- ポートフォリオ価値の計算 ---
                st.subheader("シミュレーション結果")
                total_initial_investment = 0
                final_portfolio_value = 0
                
                results_data = []

                for ticker, details in portfolio_with_investment.items():
                    initial_investment = details['invest_amount']
                    stock_prices = all_prices[ticker].dropna()

                    if not stock_prices.empty:
                        # 開始日の株価を取得
                        first_valid_date = stock_prices.index[0]
                        initial_price = stock_prices.loc[first_valid_date]

                        # 終了日の株価を取得
                        last_valid_date = stock_prices.index[-1]
                        final_price = stock_prices.loc[last_valid_date]

                        if initial_price > 0:
                            shares_bought = initial_investment / initial_price
                            final_value = shares_bought * final_price
                            profit_loss = final_value - initial_investment
                            return_rate = (profit_loss / initial_investment) * 100

                            total_initial_investment += initial_investment
                            final_portfolio_value += final_value

                            results_data.append({
                                "銘柄": details['name'],
                                "初期投資額": f"{initial_investment:,.0f} 円",
                                "最終評価額": f"{final_value:,.0f} 円",
                                "損益": f"{profit_loss:,.0f} 円",
                                "リターン率": f"{return_rate:.2f} %"
                            })

                # --- 結果表示 ---
                if results_data:
                    st.dataframe(pd.DataFrame(results_data), use_container_width=True)
                    
                    st.subheader("全体のサマリー")
                    total_profit_loss = final_portfolio_value - total_initial_investment
                    total_return_rate = (total_profit_loss / total_initial_investment) * 100 if total_initial_investment > 0 else 0

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("初期投資額の合計", f"{total_initial_investment:,.0f} 円")
                        st.metric("最終評価額の合計", f"{final_portfolio_value:,.0f} 円")
                    with col2:
                        st.metric("全体の損益", f"{total_profit_loss:,.0f} 円", delta=f"{total_return_rate:.2f} %")

            except Exception as e:
                st.error(f"分析中にエラーが発生しました。期間や銘柄コードを見直してください。エラー: {e}")
