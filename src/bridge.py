import os
import requests
import pandas as pd
from datetime import datetime, timedelta

class FinnhubBridge:
    def __init__(self, api_key):
        self.api_key = api_key
        # Tick endpoint is served from a dedicated subdomain
        self.base_url = "https://tick.finnhub.io/api/v1"
        # Candle endpoint uses the main finnhub domain
        self.candle_base = "https://finnhub.io/api/v1"

    def fetch_recent_data(self, symbol, days=7):
        """
        Fetches recent stock candle data.
        Note: Finnhub free plan often provides daily resolution for longer historical data.
        The test script mentions '1分钟线数据' (1-minute data), which might require a premium plan.
        This implementation will fetch with a resolution of '1' for 1-minute candles as requested.
        """
        if not self.api_key:
            print("❌ API key is not provided.")
            return None

        to_date = datetime.now()
        # Note: Finnhub's from/to for 1-min candles can be tricky.
        # Let's fetch for the last few days to ensure we get data, e.g., market closures.
        from_date = to_date - timedelta(days=days)

        to_timestamp = int(to_date.timestamp())
        from_timestamp = int(from_date.timestamp())

        params = {
            "symbol": symbol,
            "resolution": "1", # 1-minute resolution
            "from": from_timestamp,
            "to": to_timestamp,
            "token": self.api_key,
        }
        try:
            r = requests.get(f"{self.base_url}/stock/candle", params=params)
            r.raise_for_status()

            # Check if response has content before parsing JSON
            if not r.text:
                print(f"❌ Empty response from API for {symbol}")
                return None

            try:
                data = r.json()
            except ValueError as je:
                print(f"❌ Failed to parse JSON response: {je}")
                print(f"   Response content: {r.text[:200]}")
                return None

            if data.get('s') != 'ok':
                print(f"❌ API returned an error for {symbol}: {data}")
                return None

            df = pd.DataFrame(data)
            if df.empty:
                print(f"ℹ️ No data returned for {symbol} for the given period.")
                return pd.DataFrame()

            # The test script expects 'vol_buy' and 'vol_sell', which are not in candle data.
            # We will create them here, assuming the processor can handle it or we simulate it.
            df['datetime'] = pd.to_datetime(df['t'], unit='s')
            df.set_index('datetime', inplace=True)
            df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)
            
            # Simulate vol_buy and vol_sell for compatibility with the processor
            price_change = df['close'].diff()
            df['side'] = 1
            df.loc[price_change < 0, 'side'] = -1
            df['side'] = df['side'].ffill().fillna(0)
            df['vol_buy'] = (df['volume'] / 2).where(df['side'] == 1, 0)
            df['vol_sell'] = (df['volume'] / 2).where(df['side'] == -1, 0)


            return df[['open', 'high', 'low', 'close', 'volume', 'vol_buy', 'vol_sell']]

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error {e.response.status_code}: {e.response.reason}")
            if e.response.status_code == 403:
                print("   (Likely: Invalid or insufficient premium API key)")
            elif e.response.status_code == 401:
                print("   (Likely: Invalid API key)")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ An error occurred during API request: {e}")
            return None
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            return None

class FinnhubTickBridge:
    def __init__(self, api_key):
        self.api_key = api_key
        # Tick endpoint is on the tick subdomain
        self.base_url = "https://tick.finnhub.io/api/v1"
        # Candle endpoint uses the main finnhub domain
        self.candle_base = "https://finnhub.io/api/v1"

    def fetch_real_ticks(self, symbol, date):
        """
        Fetches real-time tick data for a given symbol and date.
        This requires a premium Finnhub subscription.
        """
        if not self.api_key:
            print("❌ Premium API key is not provided.")
            return None

        params = {
            "symbol": symbol,
            "date": date,
            "token": self.api_key,
            "format": "json",  # Explicitly request JSON format
        }
        try:
            r = requests.get(f"{self.base_url}/stock/tick", params=params)
            r.raise_for_status()

            # Check if response has content before parsing JSON
            if not r.text:
                print(f"❌ Empty response from API for {symbol}")
                return None

            try:
                data = r.json()
            except ValueError as je:
                print(f"❌ Failed to parse JSON response: {je}")
                print(f"   Response content: {r.text[:200]}")
                return None

            # The API returns data directly as {'t': [...], 'p': [...], 'v': [...], 'x': [...]}
            # or as {'data': [...]} if using different format parameter
            if 'data' in data and data['data']:
                tick_list = data['data']
            elif 't' in data and 'p' in data and 'v' in data:
                # Direct format with lists - provide debug then convert to candles
                try:
                    sample_count = len(data.get('t', []))
                except Exception:
                    sample_count = 0
                print(f"   [DEBUG] Direct tick-format detected for {symbol}: {sample_count} ticks")
                ts_sample = data.get('t', [])[:3]
                print(f"   [DEBUG] Timestamp sample (first 3): {ts_sample}")
                # first-pass conversion
                candles = self._convert_ticks_to_candles(data, symbol, date)
                # If candles insufficient, try ranged/paginated fetch for full day
                try:
                    min_candles_needed = 30
                    if candles.empty or len(candles) < min_candles_needed:
                        print(f"   [DEBUG] Insufficient candles ({len(candles)}), attempting ranged fetch for full day")
                        # derive start/end from date string
                        try:
                            day_dt = datetime.strptime(date, '%Y-%m-%d')
                            start_dt = datetime(day_dt.year, day_dt.month, day_dt.day, 0, 0, 0)
                            end_dt = start_dt + timedelta(days=1) - timedelta(seconds=1)
                            ranged = self.fetch_ticks_range(symbol, start_dt, end_dt, candle_size_ms=300000)
                            if ranged is not None and not ranged.empty and len(ranged) >= min_candles_needed:
                                return ranged
                        except Exception:
                            pass
                except Exception:
                    pass

                return candles
            else:
                print(f"ℹ️ No tick data returned for {symbol} on {date}. (Is it a trading day?)")
                print(f"   [DEBUG] Full response keys: {list(data.keys())}")
                return pd.DataFrame()

            # Convert to DataFrame
            if isinstance(tick_list, list):
                df = pd.DataFrame(tick_list)
            else:
                df = pd.DataFrame(tick_list)
            
            if df.empty:
                print(f"ℹ️ No tick data returned for {symbol} on {date}. (Is it a trading day?)")
                return df

            # Convert timestamp from milliseconds to datetime
            df['datetime'] = pd.to_datetime(df['t'], unit='ms')
            df.set_index('datetime', inplace=True)
            # Ensure we have the required columns
            df = df[['p', 'v']]
            
            return df

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error {e.response.status_code}: {e.response.reason}")
            if e.response.status_code == 403:
                print("   (Likely: Invalid or insufficient premium API key)")
            elif e.response.status_code == 401:
                print("   (Likely: Invalid API key)")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ An error occurred during API request: {e}")
            return None
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            return None

    def _convert_ticks_to_candles(self, tick_data, symbol, date, candle_size_ms=300000):
        """
        Convert tick data to 5-minute candles.
        tick_data: dict with 't' (timestamps), 'p' (prices), 'v' (volumes)
        candle_size_ms: candle size in milliseconds (default 5 min = 300000 ms)
        """
        times = tick_data['t']
        prices = tick_data['p']
        volumes = tick_data['v']

        # Detect timestamp unit and normalize to milliseconds
        try:
            max_t = max(times)
        except Exception:
            max_t = 0

        # Heuristics:
        # - microseconds: ~1e15
        # - milliseconds: ~1e12
        # - seconds: ~1e9
        if max_t > 1e14:
            detected_unit = 'microseconds'
            timestamps_ms = [int(t // 1000) for t in times]
        elif max_t > 1e11:
            detected_unit = 'milliseconds'
            timestamps_ms = [int(t) for t in times]
        else:
            detected_unit = 'seconds'
            timestamps_ms = [int(t * 1000) for t in times]

        print(f"   [DEBUG] {symbol}: detected timestamp unit={detected_unit}, ticks={len(times)}")
        try:
            min_ts = min(timestamps_ms)
            max_ts = max(timestamps_ms)
            print(f"   [DEBUG] {symbol}: timestamp range -> {pd.to_datetime(min_ts, unit='ms')} to {pd.to_datetime(max_ts, unit='ms')}")
        except Exception:
            pass
        
        if not times or not prices or not volumes:
            return pd.DataFrame()
        
        # Create ticks dataframe
        ticks_df = pd.DataFrame({
            'timestamp_ms': timestamps_ms,
            'price': prices,
            'volume': volumes
        })
        
        # Group by 5-minute candles
        ticks_df['candle_time'] = (ticks_df['timestamp_ms'] // candle_size_ms) * candle_size_ms
        
        candles = []
        for candle_time, group in ticks_df.groupby('candle_time'):
            if group.empty:
                continue
            
            open_price = group['price'].iloc[0]
            high_price = group['price'].max()
            low_price = group['price'].min()
            close_price = group['price'].iloc[-1]
            total_volume = group['volume'].sum()
            
            # Estimate buy/sell volume based on price movements
            price_diffs = group['price'].diff().fillna(0)
            buy_vol = group[price_diffs >= 0]['volume'].sum()
            sell_vol = group[price_diffs < 0]['volume'].sum()
            
            candles.append({
                'datetime': pd.to_datetime(candle_time, unit='ms'),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': total_volume,
                'vol_buy': buy_vol,
                'vol_sell': sell_vol
            })
        
        print(f"   [DEBUG] {symbol}: converted to {len(candles)} candles (candle_size_ms={candle_size_ms})")
        if not candles:
            return pd.DataFrame()
        
        df = pd.DataFrame(candles)
        df.set_index('datetime', inplace=True)
        return df

    def _ticks_df_to_candles(self, ticks_df, symbol, candle_size_ms=300000):
        """
        Convert a ticks DataFrame with 'timestamp_ms', 'price', 'volume' to candles.
        """
        if ticks_df.empty:
            return pd.DataFrame()

        ticks_df = ticks_df.sort_values('timestamp_ms')
        ticks_df['candle_time'] = (ticks_df['timestamp_ms'] // candle_size_ms) * candle_size_ms

        candles = []
        for candle_time, group in ticks_df.groupby('candle_time'):
            if group.empty:
                continue
            open_price = group['price'].iloc[0]
            high_price = group['price'].max()
            low_price = group['price'].min()
            close_price = group['price'].iloc[-1]
            total_volume = group['volume'].sum()

            price_diffs = group['price'].diff().fillna(0)
            buy_vol = group[price_diffs >= 0]['volume'].sum()
            sell_vol = group[price_diffs < 0]['volume'].sum()

            candles.append({
                'datetime': pd.to_datetime(candle_time, unit='ms'),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': total_volume,
                'vol_buy': buy_vol,
                'vol_sell': sell_vol
            })

        print(f"   [DEBUG] {symbol}: converted to {len(candles)} candles (candle_size_ms={candle_size_ms})")
        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        df.set_index('datetime', inplace=True)
        return df

    def fetch_ticks_range(self, symbol, start_dt, end_dt, candle_size_ms=300000, max_ticks_per_call=25000):
        """
        Fetch ticks across a time range [start_dt, end_dt] (datetime objects) trying to retrieve as many ticks as possible.
        It will iterate over time windows and adapt window size if the API returns the maximum allowed ticks (truncation).
        Returns a candles DataFrame converted from the accumulated ticks.
        """
        if not self.api_key:
            print("❌ Premium API key is not provided.")
            return None

        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)

        # initial window: 1 hour
        window_ms = 60 * 60 * 1000
        accumulated = []

        current_start = start_ms
        attempt = 0
        while current_start < end_ms and attempt < 1000:
            current_end = min(current_start + window_ms - 1, end_ms)

            params = {
                'symbol': symbol,
                'token': self.api_key,
                'format': 'json',
                # try 'from' and 'to' in seconds - may be supported
                'from': int(current_start // 1000),
                'to': int(current_end // 1000),
            }

            try:
                # Debug: show the outgoing request params for troubleshooting
                print(f"   [DEBUG] Requesting ticks: url={self.base_url}/stock/tick params={params}")
                r = requests.get(f"{self.base_url}/stock/tick", params=params)
                r.raise_for_status()
                if not r.text:
                    # no content, advance window
                    current_start = current_end + 1
                    attempt += 1
                    continue

                try:
                    data = r.json()
                except ValueError:
                    # Not JSON; skip
                    current_start = current_end + 1
                    attempt += 1
                    continue

                # parse returned ticks
                if 'data' in data and data['data']:
                    df_chunk = pd.DataFrame(data['data'])
                    # ensure t,p,v exist
                    if {'t', 'p', 'v'}.issubset(df_chunk.columns):
                        # timestamps likely in ms
                        df_chunk['timestamp_ms'] = df_chunk['t']
                        df_chunk = df_chunk[['timestamp_ms', 'p', 'v']].rename(columns={'p': 'price', 'v': 'volume'})
                        accumulated.append(df_chunk)
                elif 't' in data and 'p' in data and 'v' in data:
                    times = data['t']
                    prices = data['p']
                    volumes = data['v']
                    # normalize timestamps unit
                    try:
                        max_t = max(times)
                    except Exception:
                        max_t = 0
                    if max_t > 1e11:
                        timestamps_ms = [int(t) for t in times]
                    else:
                        timestamps_ms = [int(t * 1000) for t in times]

                    df_chunk = pd.DataFrame({'timestamp_ms': timestamps_ms, 'price': prices, 'volume': volumes})
                    accumulated.append(df_chunk)
                else:
                    # nothing useful
                    pass

                # adjust window size heuristically if we hit max ticks
                last_count = 0
                try:
                    last_count = len(data.get('t', [])) if 't' in data else len(data.get('data', []))
                except Exception:
                    last_count = 0

                if last_count >= max_ticks_per_call:
                    # likely truncated; reduce window to capture denser slices
                    window_ms = max(window_ms // 2, 1000)
                    print(f"   [DEBUG] {symbol}: hit max ticks ({last_count}), reducing window to {window_ms}ms")
                    # move start to the last timestamp received if possible
                    try:
                        last_ts = max(data.get('t', []))
                        if last_ts:
                            if last_ts > 1e11:
                                current_start = int(last_ts) + 1
                            else:
                                current_start = int(last_ts * 1000) + 1
                        else:
                            current_start = current_end + 1
                    except Exception:
                        current_start = current_end + 1
                else:
                    # advance to next window
                    current_start = current_end + 1

            except requests.exceptions.RequestException as e:
                print(f"❌ Request error during ranged fetch: {e} -- params={params}")
                # advance to avoid infinite loop
                current_start = current_end + 1

            attempt += 1

        # merge accumulated chunks
        if not accumulated:
            print(f"ℹ️ No ticks accumulated for {symbol} in range {start_dt} - {end_dt}")
            return pd.DataFrame()

        all_ticks = pd.concat(accumulated, ignore_index=True)
        # normalize column names
        if 'p' in all_ticks.columns:
            all_ticks = all_ticks.rename(columns={'p': 'price'})
        if 'v' in all_ticks.columns:
            all_ticks = all_ticks.rename(columns={'v': 'volume'})

        # dedupe
        all_ticks = all_ticks.drop_duplicates(subset=['timestamp_ms', 'price', 'volume'])

        # limit to requested range
        all_ticks = all_ticks[(all_ticks['timestamp_ms'] >= start_ms) & (all_ticks['timestamp_ms'] <= end_ms)]

        print(f"   [DEBUG] {symbol}: accumulated total ticks after dedupe: {len(all_ticks)}")

        # convert to candles
        candles = self._ticks_df_to_candles(all_ticks, symbol, candle_size_ms=candle_size_ms)

        return candles

    def fetch_candles(self, symbol, date, resolution='5'):
        """
        Fetch candles for a given symbol and date using Finnhub's /stock/candle API.
        resolution: '1' or '5' (minutes) or other supported resolutions.
        Returns a DataFrame with columns ['open','high','low','close','volume','vol_buy','vol_sell'] indexed by datetime.
        """
        if not self.api_key:
            print("❌ Premium API key is not provided.")
            return None

        try:
            day_dt = datetime.strptime(date, '%Y-%m-%d')
        except Exception:
            print(f"❌ Invalid date format: {date}. Expected YYYY-MM-DD")
            return None

        start_dt = datetime(day_dt.year, day_dt.month, day_dt.day, 0, 0, 0)
        end_dt = datetime(day_dt.year, day_dt.month, day_dt.day, 23, 59, 59)
        params = {
            'symbol': symbol,
            'resolution': str(resolution),
            'from': int(start_dt.timestamp()),
            'to': int(end_dt.timestamp()),
            'token': self.api_key,
        }

        try:
            print(f"   [DEBUG] Requesting candles: url={self.candle_base}/stock/candle params={params}")
            r = requests.get(f"{self.candle_base}/stock/candle", params=params)
            r.raise_for_status()

            if not r.text:
                print(f"ℹ️ Empty candle response for {symbol} on {date}")
                return pd.DataFrame()

            try:
                data = r.json()
            except ValueError as je:
                print(f"❌ Failed to parse candle JSON: {je}")
                print(f"   Response content: {r.text[:200]}")
                return pd.DataFrame()

            if data.get('s') != 'ok':
                print(f"❌ Candle API returned status for {symbol} on {date}: {data.get('s')}")
                return pd.DataFrame()

            # Build DataFrame from candle arrays
            df = pd.DataFrame({
                't': data.get('t', []),
                'o': data.get('o', []),
                'h': data.get('h', []),
                'l': data.get('l', []),
                'c': data.get('c', []),
                'v': data.get('v', []),
            })

            if df.empty:
                print(f"ℹ️ No candle bars for {symbol} on {date}")
                return pd.DataFrame()

            df['datetime'] = pd.to_datetime(df['t'], unit='s')
            df.set_index('datetime', inplace=True)
            df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)

            # Estimate vol_buy / vol_sell using price changes within the bar (approximation)
            price_change = df['close'].diff().fillna(0)
            df['side'] = 1
            df.loc[price_change < 0, 'side'] = -1
            df['side'] = df['side'].ffill().fillna(0)
            df['vol_buy'] = (df['volume'] / 2).where(df['side'] == 1, 0)
            df['vol_sell'] = (df['volume'] / 2).where(df['side'] == -1, 0)

            return df[['open', 'high', 'low', 'close', 'volume', 'vol_buy', 'vol_sell']]

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error {e.response.status_code}: {e.response.reason}")
            return pd.DataFrame()
        except requests.exceptions.RequestException as e:
            print(f"❌ An error occurred during candle API request: {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"❌ Unexpected error fetching candles: {e}")
            return pd.DataFrame()
