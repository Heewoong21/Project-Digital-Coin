import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from keras.models import Model
from keras.layers import Input, RepeatVector, TimeDistributed, LSTM as LSTM_Keras

def predict_rnn(df):
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(df[["Close"]])
    x, y = [], []
    for i in range(5, len(scaled)):
        x.append(scaled[i-5:i])
        y.append(scaled[i])
    x, y = np.array(x), np.array(y)
    model = Sequential()
    model.add(LSTM(50, activation='relu', input_shape=(5, 1)))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    model.fit(x, y, epochs=20, verbose=0)
    future_input = scaled[-5:].reshape(1, 5, 1)
    predicted = scaler.inverse_transform(model.predict(future_input))
    print(f"\n🔮 RNN 예측 종가: {predicted[0][0]:,.0f} KRW")

def detect_anomaly_lstm(df):
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(df[["Volume"]])
    x = [scaled[i-10:i] for i in range(10, len(scaled))]
    x = np.array(x)
    input_dim = x.shape[2]
    timesteps = x.shape[1]
    inputs = Input(shape=(timesteps, input_dim))
    encoded = LSTM_Keras(32, activation="relu", return_sequences=False)(inputs)
    repeated = RepeatVector(timesteps)(encoded)
    decoded = LSTM_Keras(32, activation="relu", return_sequences=True)(repeated)
    outputs = TimeDistributed(Dense(input_dim))(decoded)
    autoencoder = Model(inputs, outputs)
    autoencoder.compile(optimizer='adam', loss='mae')
    autoencoder.fit(x, x, epochs=20, batch_size=16, verbose=0)
    recon = autoencoder.predict(x)
    loss = np.mean(np.abs(recon - x), axis=(1, 2))
    threshold = np.mean(loss) + 2 * np.std(loss)
    anomalies = np.where(loss > threshold)[0]
    if len(anomalies) == 0:
        print("\n✅ 이상 거래 없음")
    else:
        print("\n🚨 이상 거래 발생:")
        for idx in anomalies:
            print(df.index[idx + 10])
