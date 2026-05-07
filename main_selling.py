import os
import sys

# Set instance to SELLING
os.environ['BOT_INSTANCE'] = 'SELLING'

# Import and run the main bot
import main

if __name__ == "__main__":
    main.main()
