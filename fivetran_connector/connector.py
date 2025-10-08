import json
import os
import paho.mqtt.client as mqtt

# --- Imports Confirmed by QuickStart Guide ---
from fivetran_connector_sdk import Connector
from fivetran_connector_sdk import Logging as log
from fivetran_connector_sdk import Operations as op

# NOTE: Since we don't import UpdateResponse, we must manually return a dictionary
# or rely on the SDK to wrap the result, but the documentation recommends UpdateResponse.
# For maximum compatibility with your quickstart, we will return a dictionary state.

# --- Configuration ---
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC     = os.getenv("TOPIC", "factory/demo/hello")

# --- Simplified Fivetran Update Function ---
# Removed the unnecessary 'get_schema' method
def update(configuration: dict, state: dict) -> dict:
    """
    Connects to the MQTT broker, collects a batch of messages, and uses op.upsert 
    to write them, relying on Fivetran to infer the schema.
    """
    log.warning("Starting MQTT Sync (QuickStart Style)")

    collected_messages = []
    BATCH_TIMEOUT_SEC = 10.0
    
    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            collected_messages.append(payload)
        except Exception as e:
            log.warning(f"ERROR processing message payload: {e}. Skipping record.")

    client = mqtt.Client()
    client.on_message = on_message
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.subscribe(TOPIC, qos=1)
        log.fine(f"Connected to {MQTT_HOST}:{MQTT_PORT}, subscribing to {TOPIC}")
        client.loop_forever(timeout=BATCH_TIMEOUT_SEC)
        
    except Exception as e:
        log.warning(f"MQTT operation failed. Error: {e}")
    finally:
        client.disconnect()
        log.fine("Disconnected from MQTT broker.")

    # --- Data Writing (Fivetran SDK using op.upsert) ---
    if collected_messages:
        log.fine(f"Collected {len(collected_messages)} messages. Writing to table 'hello_messages'")
        
        # We must iterate and call op.upsert for each record, 
        # as op.upsert handles only one dictionary record at a time.
        for message in collected_messages:
            # Fivetran will infer the schema and use a surrogate primary key (_fivetran_id)
            op.upsert(table="hello_messages", data=message)

    # Save the progress by checkpointing the state (mandatory for simple connectors).
    op.checkpoint(state)
    
    # Return the state dictionary
    return state


# This creates the connector object that will only use the update function.
connector = Connector(update=update)

# --- Entry Point for Debugging ---
if __name__ == "__main__":
    connector.debug()