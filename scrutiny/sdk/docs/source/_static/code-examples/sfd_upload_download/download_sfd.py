from scrutiny.sdk.client import ScrutinyClient
client = ScrutinyClient()
with client.connect("localhost", 8765):
    req = client.download_sfd("0123456789ABCDEF0123456789ABCDEF")   # Firmware ID
    print("Downloading SFD")
    req.wait_for_completion(timeout=10) # Blocking call. A different thread could query req.get_progress()
    filename = "myfile_sfd"
    with open(filename, 'wb') as f:
        f.write(req.get())
    print(f"File downloaded to {filename}")
