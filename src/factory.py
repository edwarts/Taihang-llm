import json
import aiohttp

class LocalDataFactory:
    def __init__(self, tar_path=None, model_name="deepseek-r1:70b", ollama_base_url="http://localhost:11434"):
        """
        Initializes the factory.
        :param tar_path: Path to tar data (can be None if not used).
        :param model_name: The name of the Ollama model to use.
        :param ollama_base_url: The base URL for the Ollama API.
        """
        self.tar_path = tar_path
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url

    async def generate_thought(self, context_prompt, label, future_return, semaphore):
        """
        Generates a "thought" by calling a local LLM (Ollama) and formats the output.
        """
        async with semaphore:
            system_prompt = """
You are a world-class quantitative trading analyst. Your role is to analyze detailed market data and generate a structured "thought" process.
This thought process will be used as fine-tuning data for a master trading AI.

Your analysis must be concise, logical, and directly related to the data provided.
You will be given a "CONTEXT", which is a snapshot of the market for a specific stock.
You will also be given a "LABEL" (e.g., BUY, SELL, HOLD) and a "FUTURE_RETURN" that occurred after the context.

Your task is to retrospectively justify the given LABEL based ONLY on the data in the CONTEXT.
Do not use any information not present in the context.
Your output must be a JSON object containing your "thought" process.

Example thought process:
"The RSI is low (25), suggesting an oversold condition. Order flow imbalance (OFI) is strongly positive, indicating aggressive buying pressure.
A bullish Fair Value Gap (FVG) has formed, signaling a potential upward move. The combination of these factors supports the 'BUY' label."

Based on the provided CONTEXT, generate a "thought" that logically leads to the provided LABEL.
"""
            api_url = f"{self.ollama_base_url}/api/generate"
            
            payload = {
                "model": self.model_name,
                "system": system_prompt,
                "prompt": f"CONTEXT:\n{context_prompt}\n\nLABEL: {label}\nFUTURE_RETURN: {future_return:.4f}\n\nJustify the LABEL based on the CONTEXT.",
                "stream": False,
                "format": "json" # Request JSON output from Ollama
            }
            
            llm_output_str = "{}" # Default value
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, json=payload) as response:
                        response.raise_for_status()
                        response_data = await response.json()
                        
                        llm_output_str = response_data.get("response", "{}")
                        thought_json = json.loads(llm_output_str)

                        output_record = {
                            "model": self.model_name,
                            "system_prompt": system_prompt,
                            "input": context_prompt,
                            "output": thought_json.get("thought", "No thought generated."),
                            "label": label,
                            "future_return": future_return
                        }
                        return output_record
                        
            except aiohttp.ClientError as e:
                print(f"❌ An error occurred calling the Ollama API: {e}. Is Ollama running?")
                return None
            except json.JSONDecodeError:
                print(f"❌ Failed to parse JSON from LLM response: {llm_output_str}")
                return None
            except Exception as e:
                print(f"❌ An unexpected error occurred in LocalDataFactory: {e}")
                return None
