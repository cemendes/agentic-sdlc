# Copyright 2026 Google LLC
import sys
import json
import traceback

def main():
    try:
        # Read parameters from stdin
        params = json.loads(sys.stdin.read())
        message = params["message"]
        user_id = params["user_id"]
        project_path = params["project_path"]
        
        # Inject the project path to sys.path before importing
        sys.path.insert(0, project_path)
        
        from app.agent_runtime_app import agent_runtime
        
        response = agent_runtime.stream_query(
            message=message,
            user_id=user_id
        )
        
        for chunk in response:
            if hasattr(chunk, "data"):
                # Decode chunk data to send back
                data_str = chunk.data.decode("utf-8")
                print(json.dumps({"type": "chunk", "data": data_str}), flush=True)
            elif isinstance(chunk, dict):
                print(json.dumps({"type": "dict", "data": chunk}), flush=True)
            else:
                print(json.dumps({"type": "str", "data": str(chunk)}), flush=True)
                
    except Exception as e:
        print(json.dumps({"type": "error", "error": str(e), "traceback": traceback.format_exc()}), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
