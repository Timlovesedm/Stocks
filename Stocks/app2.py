import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- アプリケーションの設定 ---
st.set_page_config(layout="wide", page_title="ポートフォリオ分析アプリ")

st.title("📊 投資ポートフォリオ分析アプリ")

# --- サイドバー：ポートフォリオ設定 ---
st.sidebar.header("ポートフォリオ設定")

# 銘柄追加フォーム
st.sidebar.subheader("銘柄の追加")
ticker_input = st.sidebar.text_input("銘柄コードを入力 (例: 7203.T for Toyota)", "").upper()
add_stock_button = st.sidebar.button("銘柄を追加")

# セッションステートでポートフォリオを管理
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {} # {'銘柄コード': {'name': '企業名', 'invest_amount': 0}}

if add_stock_button and ticker_input:
    try:
        # yfinanceで銘柄情報を取得
        stock_info = yf.Ticker(ticker_input).info
        if 'longName' in stock_info:
            stock_name = stock_info['longName']
        elif 'shortName' in stock_info: # longNameがない場合
            stock_name = stock_info['shortName']
        else:
            stock_name = ticker_input # 名前が取得できない場合はティッカーを表示
            st.sidebar.warning(f"銘柄名が見つかりませんでした。ティッカー: {ticker_input} を追加します。")

        if ticker_input not in st.session_state.portfolio:
            st.session_state.portfolio[ticker_input] = {'name': stock_name, 'invest_amount': 0}
            st.sidebar.success(f"'{stock_name}' をポートフォリオに追加しました。")
        else:
            st.sidebar.warning(f"'{stock_name}' は既にポートフォリオにあります。")
    except Exception as e:
        st.sidebar.error(f"銘柄コード '{ticker_input}' の取得に失敗しました。正しいコードか確認してください。エラー: {e}")

# ポートフォリオの表示と投資金額設定、削除
st.sidebar.subheader("現在のポートフォリオ")
if not st.session_state.portfolio:
    st.sidebar.info("ポートフォリオに銘柄がありません。")
else:
    for ticker, details in list(st.session_state.portfolio.items()): # list()でコピーして反復中に削除できるようにする
        col1, col2, col3 = st.sidebar.columns([3, 2, 1])
        with col1:
            st.write(f"**{details['name']}** ({ticker})")
        with col2:
            current_amount = st.session_state.portfolio[ticker]['invest_amount']
            new_amount = st.number_input(
                f"金額 ({ticker})",
                min_value=0,
                value=int(current_amount),
                step=1000,
                key=f"amount_{ticker}"
            )
            st.session_state.portfolio[ticker]['invest_amount'] = new_amount
        with col3:
            if st.button("削除", key=f"delete_{ticker}"):
                del st.session_state.portfolio[ticker]
                st.rerun() # 削除を反映するために再実行

# シミュレーション期間設定
st.sidebar.subheader("シミュレーション期間")
today = datetime.now().date()
default_start_date = today - timedelta(days=365 * 3) # 3年前をデフォルトに
start_date = st.sidebar.date_input("開始日", value=default_start_date, max_value=today - timedelta(days=1))
end_date = st.sidebar.date_input("終了日", value=today - timedelta(days=1), max_value=today - timedelta(days=1)) # 前日まで

# --- メインコンテンツ ---
if not st.session_state.portfolio or sum(d['invest_amount'] for d in st.session_state.portfolio.values()) == 0:
    st.info("左のサイドバーで銘柄を追加し、投資金額を設定してください。")
else:
    total_invested_amount = sum(d['invest_amount'] for d in st.session_state.portfolio.values())
    if total_invested_amount == 0:
        st.warning("合計投資金額が0円です。投資金額を設定してください。")
    else:
        st.header("ポートフォリオ分析結果")

        # 1. ポートフォリオの金額分散（円グラフ）
        st.subheader("1. ポートフォリオの金額分散")
        portfolio_data = []
        for ticker, details in st.session_state.portfolio.items():
            if details['invest_amount'] > 0:
                portfolio_data.append({'銘柄': details['name'], '投資金額': details['invest_amount']})

        if portfolio_data:
            df_portfolio = pd.DataFrame(portfolio_data)
            fig_pie = px.pie(
                df_portfolio,
                values='投資金額',
                names='銘柄',
                title='ポートフォリオの金額構成比',
                hole=0.3 # ドーナツ型にする
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("投資金額が設定されている銘柄がありません。")

        # 2. 過去実績による運用益の推移
        st.subheader("2. 運用益の推移")

        # 株価データ取得
        stock_prices = {}
        data_load_state = st.info("株価データを取得中...")
        for ticker in st.session_state.portfolio:
            try:
                # yfinanceで過去データを取得 (close priceのみ)
                # progress_bar.progress(progress_value, text=f"取得中: {st.session_state.portfolio[ticker]['name']}")
                data = yf.download(ticker, start=start_date, end=end_date + timedelta(days=1))['Adj Close']
                if not data.empty:
                    stock_prices[ticker] = data
                else:
                    st.warning(f"銘柄 '{st.session_state.portfolio[ticker]['name']}' ({ticker}) のデータが指定期間で見つかりませんでした。")
            except Exception as e:
                st.error(f"銘柄 '{st.session_state.portfolio[ticker]['name']}' ({ticker}) のデータ取得中にエラーが発生しました: {e}")
        data_load_state.empty()

        if not stock_prices:
            st.warning("データが取得できた銘柄がありません。期間や銘柄コードを確認してください。")
        else:
            # データフレームに結合し、欠損値を補完（後方補完）
            df_prices = pd.DataFrame(stock_prices)
            df_prices = df_prices.ffill().bfill() # 念のため欠損値処理

            # TOPIXデータの取得
            topix_ticker = "^TOPIX" # TOPIXのティッカー
            try:
                topix_data = yf.download(topix_ticker, start=start_date, end=end_date + timedelta(days=1))['Adj Close']
                topix_data = topix_data.ffill().bfill()
                topix_data = topix_data / topix_data.iloc[0] * 100 # 基準化（開始日を100とする）
            except Exception as e:
                st.error(f"TOPIXデータの取得に失敗しました: {e}")
                topix_data = pd.Series([]) # エラー時は空にする

            # 各銘柄の基準化されたリターンを計算 (開始日を1とする)
            normalized_returns = df_prices / df_prices.iloc[0]

            # ポートフォリオ全体の価値推移を計算
            # ここでは「購入した株数 * その日の株価」で価値を計算（単純な初期投資を想定）
            # 後に「毎月積み立て」ロジックに置き換える
            portfolio_daily_value = pd.Series(0.0, index=df_prices.index)
            for ticker, details in st.session_state.portfolio.items():
                if ticker in normalized_returns.columns and details['invest_amount'] > 0:
                    # 初期投資金額を基準化されたリターンで成長させる
                    # これは非常にシンプルなモデルで、実際には初期の株数で計算すべき
                    # 積み立てシミュレーションでこの部分は大きく変わる
                    initial_shares = details['invest_amount'] / df_prices[ticker].iloc[0] # 初日の株価で株数を計算
                    portfolio_daily_value += initial_shares * df_prices[ticker]

            # ポートフォリオの基準化（開始日を100とする）
            if not portfolio_daily_value.empty and portfolio_daily_value.iloc[0] > 0:
                portfolio_daily_value_normalized = portfolio_daily_value / portfolio_daily_value.iloc[0] * 100
            else:
                portfolio_daily_value_normalized = pd.Series([], dtype=float)


            # グラフの作成
            fig_performance = go.Figure()

            if not portfolio_daily_value_normalized.empty:
                fig_performance.add_trace(go.Scatter(
                    x=portfolio_daily_value_normalized.index,
                    y=portfolio_daily_value_normalized,
                    mode='lines',
                    name='ポートフォリオ (基準化)'
                ))
            
            if not topix_data.empty:
                fig_performance.add_trace(go.Scatter(
                    x=topix_data.index,
                    y=topix_data,
                    mode='lines',
                    name='TOPIX (基準化)',
                    line=dict(dash='dash') # 点線で表示
                ))

            fig_performance.update_layout(
                title='ポートフォリオとTOPIXのパフォーマンス推移 (開始日を100として基準化)',
                xaxis_title='日付',
                yaxis_title='価値 (開始日を100)',
                hovermode="x unified"
            )
            st.plotly_chart(fig_performance, use_container_width=True)

            # 3. 運用益の数値表示
            st.subheader("3. 運用益のサマリー")

            if not portfolio_daily_value_normalized.empty:
                initial_value_port = portfolio_daily_value_normalized.iloc[0]
                final_value_port = portfolio_daily_value_normalized.iloc[-1]
                total_return_port = (final_value_port - initial_value_port) / initial_value_port * 100

                # 年率リターン (簡略化された計算)
                num_years = (end_date - start_date).days / 365.25
                annualized_return_port = ((1 + total_return_port / 100)**(1/num_years) - 1) * 100 if num_years > 0 else 0

                st.write(f"**ポートフォリオ トータルリターン:** `{total_return_port:.2f}%`")
                st.write(f"**ポートフォリオ 年率リターン:** `{annualized_return_port:.2f}%`")
                
                # シャープレシオ (簡略化された計算)
                # リスクフリーレートは0%と仮定し、リターンは日次変化から計算
                daily_returns_port = portfolio_daily_value.pct_change().dropna()
                if not daily_returns_port.empty:
                    average_daily_return = daily_returns_port.mean()
                    std_dev_daily_return = daily_returns_port.std()
                    
                    if std_dev_daily_return > 0:
                        sharpe_ratio_port = (average_daily_return * 252 - 0) / (std_dev_daily_return * (252**0.5)) # 252営業日で年率化
                        st.write(f"**ポートフォリオ シャープレシオ (年率):** `{sharpe_ratio_port:.2f}`")
                    else:
                        st.info("ポートフォリオのリスクがないため、シャープレシオは計算できません。")
                else:
                    st.info("日次リターンが計算できないため、シャープレシオは計算できません。")

            if not topix_data.empty:
                initial_value_topix = topix_data.iloc[0]
                final_value_topix = topix_data.iloc[-1]
                total_return_topix = (final_value_topix - initial_value_topix) / initial_value_topix * 100
                
                num_years_topix = (end_date - start_date).days / 365.25
                annualized_return_topix = ((1 + total_return_topix / 100)**(1/num_years_topix) - 1) * 100 if num_years_topix > 0 else 0

                st.write(f"**TOPIX トータルリターン:** `{total_return_topix:.2f}%`")
                st.write(f"**TOPIX 年率リターン:** `{annualized_return_topix:.2f}%`")