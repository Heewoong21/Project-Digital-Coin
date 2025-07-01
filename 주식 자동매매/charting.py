import plotly.graph_objects as go
from data_utils import format_hover_text

def plot_candle_chart(df, coin):
    hover_text = format_hover_text(df)
    fig = go.Figure(data=[
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            text=hover_text,
            hoverinfo="text"
        )
    ])
    fig.update_layout(title=f"{coin} 캔들차트", xaxis_title="날짜", yaxis_title="가격 (KRW)")
    fig.show()

def plot_line_chart(df, coin):
    fig = go.Figure()
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df[col],
            mode='lines+markers',
            name=col,
            hovertemplate=f"%{{x}}<br>{col}: %{{y:,.0f}}원<extra></extra>"
        ))
    fig.update_layout(
        title=f"{coin}/KRW 전체 지표 그래프",
        xaxis_title="Date",
        yaxis_title="Value",
        hovermode="x unified",
        legend_title="지표"
    )
    fig.show()
