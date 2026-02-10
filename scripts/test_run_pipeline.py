import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, call, mock_open

import pandas as pd
from datetime import datetime

# Make sure to add the project root to the python path for src imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock pandas_ta before it's imported by other modules to avoid version conflicts
sys.modules['pandas_ta'] = MagicMock()

from scripts.run_pipeline import process_symbol, main
from src.config import TARGET_SYMBOLS

class TestRunPipeline(unittest.IsolatedAsyncioTestCase):

    @patch('scripts.run_pipeline.FINNHUB_KEY', 'test_key')
    @patch('scripts.run_pipeline.json.dumps')
    @patch('scripts.run_pipeline.process_symbol', new_callable=AsyncMock)
    @patch('scripts.run_pipeline.LocalDataFactory')
    @patch('scripts.run_pipeline.DeepFeatureEngineer')
    @patch('scripts.run_pipeline.FinnhubTickBridge')
    async def test_main_function_flow(
        self, mock_bridge, mock_engineer, mock_factory, mock_process_symbol, mock_json_dumps
    ):
        """Tests the main function orchestration"""
        # Setup
        mock_process_symbol.return_value = [{"record": 1}, {"record": 2}]
        mock_json_dumps.side_effect = lambda x, ensure_ascii: str(x)
        
        m_open = mock_open()
        with patch('scripts.run_pipeline.open', m_open):
            # Execute
            await main()

        # Assert
        mock_bridge.assert_called_with('test_key')
        mock_engineer.assert_called_with()
        mock_factory.assert_called_with(model_name="deepseek-r1:70b")

        self.assertEqual(mock_process_symbol.call_count, len(TARGET_SYMBOLS))
        
        # Check file operations
        self.assertEqual(m_open.call_count, len(TARGET_SYMBOLS))
        m_open.assert_called_with("data/training_dataset.jsonl", "a", encoding="utf-8")
        
        handle = m_open()
        # 2 records per symbol, called for each symbol
        expected_write_count = 2 * len(TARGET_SYMBOLS)
        self.assertEqual(handle.write.call_count, expected_write_count)

    async def test_process_symbol_full_flow(self):
        """Tests the process_symbol function's successful execution"""
        # Setup Mocks
        mock_bridge = MagicMock()
        mock_engineer = MagicMock()
        mock_factory = MagicMock()
        semaphore = asyncio.Semaphore(1)

        # Mock return values
        mock_ticks = pd.DataFrame({'price': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]})
        mock_bridge.fetch_real_ticks.return_value = mock_ticks
        
        mock_features = pd.DataFrame({
            'close': [101, 103, 105, 107, 109, 110],
            'vol_gk': [0.1, 0.5, 0.2, 0.8, 0.3, 0.4],
        })
        # Add a proper index to mock_features to simulate time series data
        mock_features.index = pd.to_datetime(['2023-01-01 09:30:00', '2023-01-01 09:35:00', '2023-01-01 09:40:00', '2023-01-01 09:45:00', '2023-01-01 09:50:00', '2023-01-01 09:55:00'])

        mock_engineer.process_dataframe.return_value = mock_features
        mock_engineer.generate_llm_description.return_value = "Test prompt"
        
        # Make generate_thought an async mock
        mock_factory.generate_thought = AsyncMock(return_value={"thought": "This is a test"})

        # Execute
        symbol = "TEST"
        target_date = "2023-01-01"
        results = await process_symbol(symbol, target_date, mock_bridge, mock_engineer, mock_factory, semaphore)

        # Assert
        mock_bridge.fetch_real_ticks.assert_called_with(symbol, target_date)
        mock_engineer.process_dataframe.assert_called_with(mock_ticks, timeframe='5min')
        self.assertTrue(mock_engineer.generate_llm_description.call_count > 0)
        self.assertTrue(mock_factory.generate_thought.call_count > 0)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['thought'], "This is a test")

    async def test_process_symbol_no_tick_data(self):
        """Tests the case where no tick data is returned"""
        mock_bridge = MagicMock()
        mock_bridge.fetch_real_ticks.return_value = None
        mock_engineer = MagicMock()
        mock_factory = MagicMock()
        semaphore = asyncio.Semaphore(1)

        results = await process_symbol("TEST", "2023-01-01", mock_bridge, mock_engineer, mock_factory, semaphore)
        self.assertEqual(results, [])

    async def test_process_symbol_insufficient_features(self):
        """Tests the case where feature calculation results in not enough data"""
        mock_bridge = MagicMock()
        mock_engineer = MagicMock()
        mock_factory = MagicMock()
        semaphore = asyncio.Semaphore(1)

        mock_bridge.fetch_real_ticks.return_value = pd.DataFrame({'price': [100, 101, 102]})
        mock_engineer.process_dataframe.return_value = pd.DataFrame({'close': [101]}) # Insufficient
        
        results = await process_symbol("TEST", "2023-01-01", mock_bridge, mock_engineer, mock_factory, semaphore)
        self.assertEqual(results, [])

if __name__ == '__main__':
    unittest.main()
