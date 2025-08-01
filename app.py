import os
import sys
import json
import google.generativeai as genai
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()

# --- 1. Initial Configuration and Setup ---

# Load the API Key securely from an environment variable
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Error: GOOGLE_API_KEY environment variable not set.", file=sys.stderr)
    sys.exit(1)

genai.configure(api_key=api_key)

# --- Configuration ---
MODEL_ID = "gemini-2.5-flash"  # Flash model is great for fast chat/Q&A
JSON_DATA_DIR = "json" # Directory where analysis files are stored

# --- 2. Initialize Flask App and Gemini Model ---

app = Flask(__name__)

# Enable CORS for all routes, allowing requests from any origin.
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"]
    }
})

try:
    model = genai.GenerativeModel(MODEL_ID)
    print(f"✅ Gemini model '{MODEL_ID}' initialized successfully.")
except Exception as e:
    print(f"❌ FATAL ERROR: Could not initialize Gemini model. Reason: {e}", file=sys.stderr)
    sys.exit(1)

# --- 3. Helper Functions ---

def load_video_context(filename: str) -> str:
    """
    Loads and returns the video context from a specified JSON file.
    Performs security checks to prevent directory traversal.
    """
    # Security check: ensure filename is just a name, not a path
    if os.path.basename(filename) != filename:
        raise ValueError("Invalid filename provided. Directory traversal is not permitted.")
        
    filepath = os.path.join(JSON_DATA_DIR, filename)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            video_data = json.load(f)
        # Convert the loaded JSON data into a formatted string for the prompt
        return json.dumps(video_data, indent=2)
    except FileNotFoundError:
        raise FileNotFoundError(f"The requested analysis file '{filename}' was not found.")
    except json.JSONDecodeError:
        raise json.JSONDecodeError(f"The file '{filename}' contains invalid JSON.", "", 0)


def create_prompt(question: str, video_context_string: str) -> str:
    """Creates the full prompt for the Gemini model using the provided context."""
    return f"""
    You are a helpful assistant that answers questions about a video.
    Use ONLY the following JSON data as your context to answer the user's question.
    Do not make up information. If the answer is not in the data, say "I don't have information on that."
    
    **CRITICAL INSTRUCTION: When you provide information about an event or spoken word, ALWAYS include the exact timestamp(s) in MM:SS format directly from the provided JSON context.**

    --- Video Context (JSON) ---
    {video_context_string}
    --- End of Context ---

    User's Question: "{question}"
    """

def handle_preflight():
    """Centralized handler for OPTIONS preflight requests."""
    response = Response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response

# --- 4. API Endpoints ---

@app.route("/videos", methods=["GET", "OPTIONS"])
def list_videos():
    """
    Scans the JSON directory and returns a list of available video analysis files.
    """
    if request.method == "OPTIONS":
        return handle_preflight()
        
    if not os.path.isdir(JSON_DATA_DIR):
        return jsonify({"error": f"Server configuration error: Directory '{JSON_DATA_DIR}' not found."}), 500
        
    try:
        video_files = [f for f in os.listdir(JSON_DATA_DIR) if f.endswith('.json')]
        return jsonify(video_files)
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred while listing videos: {e}"}), 500

@app.route("/ask", methods=["POST", "OPTIONS"])
def ask_question():
    """
    Standard non-streaming endpoint. Accepts a question and a video_file.
    """
    if request.method == "OPTIONS":
        return handle_preflight()
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request. Expecting JSON body."}), 400
        
    question = data.get('question')
    video_file = data.get('video_file')

    if not all([question, video_file]):
        return jsonify({"error": "Both 'question' and 'video_file' must be provided."}), 400
    
    try:
        video_context = load_video_context(video_file)
        prompt = create_prompt(question, video_context)
        response = model.generate_content(prompt)
        return jsonify({"answer": response.text})
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        return jsonify({"error": str(e)}), 404 # 404 for file not found or invalid
    except Exception as e:
        print(f"ERROR in /ask: {e}", file=sys.stderr)
        return jsonify({"error": f"An internal server error occurred: {e}"}), 500

@app.route("/ask-streaming", methods=["POST", "OPTIONS"])
def ask_question_streaming():
    """
    Streaming endpoint. Returns the response as a real-time stream.
    Accepts a question and a video_file.
    """
    if request.method == "OPTIONS":
        return handle_preflight()
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request. Expecting JSON body."}), 400

    question = data.get('question')
    video_file = data.get('video_file')

    if not all([question, video_file]):
        # Cannot return JSON for a stream, but this error happens before the stream starts.
        return jsonify({"error": "Both 'question' and 'video_file' must be provided."}), 400

    try:
        # Load context before starting the stream to catch file errors early.
        video_context = load_video_context(video_file)
        prompt = create_prompt(question, video_context)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        return jsonify({"error": str(e)}), 404

    def stream_gemini_response():
        """A generator function that yields chunks from the Gemini stream."""
        try:
            response_stream = model.generate_content(prompt, stream=True)
            for chunk in response_stream:
                if chunk.text: # Ensure there's text to send
                    yield chunk.text
        except Exception as e:
            print(f"Error during streaming: {e}", file=sys.stderr)
            yield f"\nAn error occurred during streaming: {e}"

    # Return a Flask Response object that streams the generator's output.
    response = Response(stream_gemini_response(), mimetype='text/plain')
    response.headers.add("Access-Control-Allow-Origin", "*") # Redundant with CORS lib, but safe
    return response

@app.route("/", methods=["GET", "OPTIONS"])
def read_root():
    """Root endpoint to confirm the API is running."""
    if request.method == "OPTIONS":
        return handle_preflight()
    
    return jsonify({"status": "Video Chat API is running. Use the /videos, /ask or /ask-streaming endpoints."})

# This allows running the app directly with `python app.py` for development
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)