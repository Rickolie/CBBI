from datetime import timedelta
from typing import List

import numpy as np
import pandas as pd
import requests
import seaborn as sns
from matplotlib import pyplot as plt
from sklearn.linear_model import LinearRegression

from globals import HTTP_TIMEOUT
from utils import add_common_markers, mark_highs_lows
from .base_metric import BaseMetric


class ReserveRiskMetric(BaseMetric):
    @property
    def name(self) -> str:
        return 'ReserveRisk'

    @property
    def description(self) -> str:
        return 'Reserve Risk'

    def calculate(self, source_df: pd.DataFrame, ax: List[plt.Axes]) -> pd.Series:
        days_shift = 2

        df = source_df.copy()

        request_data = {
            'output': 'chart.figure',
            'changedPropIds': [
                'url.pathname'
            ],
            'inputs': [
                {
                    'id': 'url',
                    'property': 'pathname',
                    'value': '/charts/reserve-risk/'
                }
            ]
        }

        response = requests.post('https://www.lookintobitcoin.com/django_plotly_dash/app/reserve_risk/_dash-update-component', json=request_data, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        response_json = response.json()
        response_x = response_json['response']['props']['figure']['data'][3]['x']
        response_y = response_json['response']['props']['figure']['data'][3]['y']

        df_risk = pd.DataFrame({
            'Date': response_x[:len(response_y)],
            'Risk': response_y,
        })
        df_risk['Date'] = pd.to_datetime(df_risk['Date']).dt.tz_localize(None)
        df_risk['Date'] += timedelta(days_shift)
        df_risk = mark_highs_lows(df_risk, 'Risk', True, round(365 * 2), 365)

        df = df.join(df_risk.set_index('Date'), on='Date')
        df.fillna({'RiskHigh': 0, 'RiskLow': 0}, inplace=True)
        df['Risk'].ffill(inplace=True)
        df['RiskLog'] = np.log(df['Risk'])

        high_rows = df.loc[df['RiskHigh'] == 1]
        high_x = high_rows.index.values.reshape(-1, 1)
        high_y = high_rows['RiskLog'].values.reshape(-1, 1)

        low_rows = df.loc[df['PriceLow'] == 1][1:]
        low_x = low_rows.index.values.reshape(-1, 1)
        low_y = low_rows['RiskLog'].values.reshape(-1, 1)

        x = df.index.values.reshape(-1, 1)

        lin_model = LinearRegression()
        lin_model.fit(high_x, high_y)
        df['RiskLogHighModel'] = lin_model.predict(x)

        lin_model.fit(low_x, low_y)
        df['RiskLogLowModel'] = lin_model.predict(x)

        df['RiskIndex'] = (df['RiskLog'] - df['RiskLogLowModel']) / \
                          (df['RiskLogHighModel'] - df['RiskLogLowModel'])

        df['RiskIndexNoNa'] = df['RiskIndex'].fillna(0)
        ax[0].set_title(self.description)
        sns.lineplot(data=df, x='Date', y='RiskIndexNoNa', ax=ax[0])
        add_common_markers(df, ax[0])

        return df['RiskIndex']
