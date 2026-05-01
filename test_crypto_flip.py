import delta_executor
import db
import time
import requests

def test_flip():
    print(">>> SURGICAL CRYPTO FLIP TEST <<<")
    # 1. Sync
    delta_executor.sync_delta_position()
    active = db.get_param("crypto_active_symbol", "")
    print(f"Current Position detected: {active}")
    
    # 2. Force Flip to BUY (Since signal is BUY)
    asset = "BTC"
    print(f"Force Executing BUY for {asset}...")
    success = delta_executor.execute_crypto_trade(asset, "BUY")
    
    if success:
        print("SUCCESS! Order placed on Delta Exchange.")
    else:
        print("FAILURE! Check API keys or logs.")

if __name__ == "__main__":
    test_flip()
