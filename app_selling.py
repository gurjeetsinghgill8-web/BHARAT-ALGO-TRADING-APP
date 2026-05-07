import os
import sys

# Set instance to SELLING
os.environ['BOT_INSTANCE'] = 'SELLING'

# Run the streamlit app on a different port
import streamlit.web.cli as stcli

if __name__ == "__main__":
    # Selling instance runs on port 8502
    sys.argv = ["streamlit", "run", "app.py", "--server.port", "8502"]
    sys.exit(stcli.main())
