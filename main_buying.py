import os
import sys

# Set instance to BUYING
os.environ['BOT_INSTANCE'] = 'BUYING'

# Import and run the main bot
import main

if __name__ == "__main__":
    main.main()
