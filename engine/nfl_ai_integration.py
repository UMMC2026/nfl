import os
import json
import requests
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class NFL_AIAnalyzer:
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    def get_ollama_commentary(self, game_data: Dict[str, Any], props: list) -> str:
        prompt = f"""
        As an NFL analyst, provide detailed commentary for this matchup:
        GAME: {game_data.get('away')} @ {game_data.get('home')}
        TIME: {game_data.get('datetime', 'Unknown')}
        TEAM STATS:
        - {game_data.get('away')}: {json.dumps(game_data.get('away_stats', {}), indent=2)}
        - {game_data.get('home')}: {json.dumps(game_data.get('home_stats', {}), indent=2)}
        KEY PROPS TO ANALYZE:
        {json.dumps(props, indent=2)}
        Provide 3-4 paragraphs covering:
        1. Coaching matchup and scheme implications
        2. Key player matchups to watch
        3. Weather/field conditions impact
        4. Betting angles and edges
        Format with clear sections and bullet points where appropriate.
        """
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "llama3.2:1b",  # Faster 1B model (was llama2:7b)
                    "prompt": prompt,
                    "stream": True,  # Enable streaming for faster responses
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 500  # Reduced from 1500 for speed
                    }
                },
                timeout=45,  # Increased from 30 for safety
                stream=True
            )
            
            # Process streaming response
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            full_response += chunk["response"]
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
            
            return full_response if full_response else "Ollama commentary unavailable"
        except Exception as e:
            return f"Ollama error: {str(e)}"
    def get_deepseek_analysis(self, props: list, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.deepseek_api_key:
            return {"error": "DeepSeek API key not configured"}
        client = OpenAI(
            api_key=self.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        prompt = f"""
        Analyze these NFL prop bets with Bayesian reasoning:
        CONTEXT:
        - Games: {json.dumps(context.get('games', []), indent=2)}
        - Weather: {context.get('weather', 'Normal conditions')}
        - Injuries: {json.dumps(context.get('injuries', []), indent=2)}
        PROPS:
        {json.dumps(props, indent=2)}
        For each prop, provide:
        1. Bayesian probability estimate (0-100%)
        2. Key factors influencing the probability
        3. Edge assessment (value, neutral, fade)
        4. Brief analysis (2-3 sentences)
        Return as structured JSON.
        """
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": f"DeepSeek error: {str(e)}"}
    def generate_comprehensive_analysis(self, slate: Dict[str, Any]) -> Dict[str, Any]:
        analysis = {
            "math_engine_results": {},
            "ollama_commentary": {},
            "deepseek_analysis": {},
            "combined_recommendations": []
        }
        for game in slate.get("games", []):
            key = f"{game.get('away')}@{game.get('home')}"
            game_props = [p for p in slate.get("props", []) 
                         if p.get("team") in [game.get("away"), game.get("home")]]
            analysis["ollama_commentary"][key] = self.get_ollama_commentary(game, game_props)
        analysis["deepseek_analysis"] = self.get_deepseek_analysis(
            slate.get("props", []),
            {"games": slate.get("games", []), "weather": "Clear", "injuries": []}
        )
        return analysis
