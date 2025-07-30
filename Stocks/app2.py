import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- アプリケーションの設定 ---
st.set_page_config(layout="wide", page_title="ポートフォリオ分析アプリ")

# --- データ取得関数（キャッシュ機能付き）---
@st.cache_data
def get_stock_data(tickers, start_date, end_date):
    """指定された銘柄リストの株価データをyfinanceから取得する"""
    # yfinanceは週末や祝日のデータを自動で直近の営業日にしてくれるが、期間を少し広めに取る
    df = yf.download(tickers, start=start_date - timedelta(days=7), end=end_date)
    if df.empty:
        return pd.DataFrame()
    # 指定された期間内のデータのみを返す
    return df['Adj Close'][start_date:end_date]

@st.cache_data
def get_jp_stock_list():
    """東証上場銘柄のリストを取得する"""
    try:
        url = 'https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls'
        df_jp_stocks = pd.read_excel(url, header=2, usecols=['コード', '銘柄名'])
        df_jp_stocks.columns = ['code', 'name']
        df_jp_stocks['code'] = df_jp_stocks['code'].astype(str) + '.T'
        df_jp_stocks['display'] = df_jp_stocks['name'] + ' (' + df_jp_stocks['code'] + ')'
        return df_jp_stocks.dropna()
    except Exception:
        return pd.DataFrame()

# --- 初期化 ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

# --- アプリ本体 ---
st.title("📊 ポートフォリオ分析アプリ")

# --- ポートフォリオ設定 ---
st.header("1. ポートフォリオ設定")

# --- ポートフォリオ登録欄 ---
st.subheader("銘柄の追加")

# 方法1：リストから検索して追加
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
    st.warning("現在、銘柄リストを自動取得できません。下のフォームから手動で追加してください。")

# 方法2：手動で追加（常に表示）
with st.form("manual_add_form", clear_on_submit=True):
    ticker_input = st.text_input("銘柄コードを手動入力 (例: 7203.T, AAPLなど)").upper()
    submitted = st.form_submit_button("手動で追加")
    if submitted and ticker_input:
        if ticker_input not in st.session_state.portfolio:
            # yfinanceで銘柄名を取得試行
            try:
                stock_name = yf.Ticker(ticker_input).info.get('longName', ticker_input)
            except Exception:
                stock_name = ticker_input # 取得失敗時はティッカーを名前とする
            st.session_state.portfolio[ticker_input] = {'name': stock_name, 'invest_amount': None}
            st.rerun()

# --- 現在のポートフォリオと投資金額の設定 ---
if st.session_state.portfolio:
    st.subheader("現在のポートフォリオ")
    for ticker, details in list(st.session_state.portfolio.items()):
        col1, col2, col3 = st.columns([5, 3, 1])
        with col1:
            st.write(f"**{details['name']}** ({ticker})")
        with col2:
            with st.form(key=f"form_{ticker}"):
                new_amount = st.number_input(
                    "投資金額 (円)",
                    value=details.get('invest_amount'),
                    placeholder="金額を入力し「確定」",
                    step=10000,
                    format="%d",
                    key=f"amount_{ticker}"
                )
                if st.form_submit_button("確定"):
                    st.session_state.portfolio[ticker]['invest_amount'] = new_amount
                    st.rerun()
        with col3:
            if st.button("削除", key=f"delete_{ticker}", use_container_width=True):
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
        
        with st.spinner("株価データを取得・分析中です... しばらくお待ちください。"):
            try:
                all_prices = get_stock_data(tickers, start_date, end_date)
                
                if all_prices.empty:
                    st.error("指定された期間の株価データを取得できませんでした。期間を変更して再度お試しください。")
                else:
                    st.subheader("シミュレーション結果")
                    total_initial_investment = 0
                    final_portfolio_value = 0
                    results_data = []

                    for ticker, details in portfolio_with_investment.items():
                        initial_investment = details['invest_amount']
                        
                        # DataFrameにtickerが存在するか確認
                        if ticker in all_prices.columns:
                            stock_prices = all_prices[ticker].dropna()
                            if not stock_prices.empty:
                                initial_price = stock_prices.iloc[0]
                                final_price = stock_prices.iloc[-1]

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

                    if results_data:
                        st.dataframe(pd.DataFrame(results_data), use_container_width=True, hide_index=True)
                        
                        st.subheader("全体のサマリー")
                        total_profit_loss = final_portfolio_value - total_initial_investment
                        total_return_rate = (total_profit_loss / total_initial_investment) * 100 if total_initial_investment > 0 else 0

                        col1, col2, col3 = st.columns(3)
                        col1.metric("初期投資額の合計", f"{total_initial_investment:,.0f} 円")
                        col2.metric("最終評価額の合計", f"{final_portfolio_value:,.0f} 円")
                        col3.metric("全体の損益", f"{total_profit_loss:,.0f} 円", delta=f"{total_return_rate:.2f} %")
                    else:
                        st.warning("分析可能なデータがありませんでした。各銘柄のデータが指定期間内に存在するか確認してください。")

            except Exception as e:
                st.error(f"分析中に予期せぬエラーが発生しました: {e}")
