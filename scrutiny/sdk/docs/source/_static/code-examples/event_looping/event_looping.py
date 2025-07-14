from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient

client = ScrutinyClient()
client.listen_events(ScrutinyClient.Events.LISTEN_DEVICE_READY | ScrutinyClient.Events.LISTEN_DEVICE_GONE |
                     ScrutinyClient.Events.LISTEN_DATALOGGING_LIST_CHANGED)
with client.connect('localhost', 8765):
    while True:
        event = client.read_event(timeout=0.5)
        if event is not None:
            if isinstance(event, ScrutinyClient.Events.DeviceReadyEvent):
                print(f"Device connected. Session ID : {event.session_id} ")
            elif isinstance(event, ScrutinyClient.Events.DeviceGoneEvent):
                print(f"Device has disconnected. Session ID : {event.session_id} ")
            elif isinstance(event, ScrutinyClient.Events.DataloggingListChanged):
                if event.change_type == sdk.DataloggingListChangeType.NEW:
                    print(f"New Datalogging acquisition ready! {event.acquisition_reference_id}")
