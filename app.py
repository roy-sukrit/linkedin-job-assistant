from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import openai

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/summarize', methods=['POST'])
def summarize():
    try:
        # Get the text from the request
        data = request.json
        text = data.get("text", "")

        if not text:
            return jsonify({"error": "Text field is required"}), 400

        # Call OpenAI API for summarization
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Summarize the following text:\n\n{text}"}
            ],
            max_tokens=100
        )

        # Extract the summary
        summary = response.choices[0].message.content.strip()
        # summary = response.choices[0].text.strip()

        return jsonify({"summary": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)